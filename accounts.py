"""Site accounts (name + password), login sessions and per-user review records, in one SQLite file.

- Passwords are stored only as scrypt hashes (random salt per user).
- A login creates a random session token; the browser keeps it in an HttpOnly cookie (set by auth_api.py) and the
  database keeps only its SHA-256, so a leaked database cannot be replayed as a login.
- Review records are text. With the reviewer's consent, a reduced copy of each reviewed photo (long edge 1600 px,
  JPEG, EXIF/GPS removed) is kept under data/photos/<user id>/ for PHOTO_DAYS days. data/ (mode 700) is outside the
  served assets, so photos are never reachable by URL; the page reads them on the server only for their owner.
"""
import hashlib
import hmac
import os
import re
import secrets
import shutil
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('T13_DB', ROOT / 'data' / 'team13.db'))
COOKIE = 't13_sid'
SESSION_DAYS = 7
NAME_RE = re.compile(r'^[0-9A-Za-z가-힣._\- ]{2,20}$')
PW_MIN, PW_MAX = 8, 64
FAIL_LIMIT, FAIL_WINDOW = 5, 300   # 5 wrong passwords per name in 5 minutes -> wait
KST = ZoneInfo('Asia/Seoul')
PHOTO_DIR = Path(os.environ.get('T13_PHOTOS', DB_PATH.parent / 'photos'))
PHOTO_DAYS = 90
PHOTO_EDGE = 1600
SIG_RE = re.compile(r'^[0-9a-f]{64}$')

_lock = threading.Lock()
_fails = {}
_DUMMY = 'scrypt$' + '00' * 16 + '$' + '00' * 32


class AuthError(ValueError):
    pass


def _connect():
    DB_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
      CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        pw TEXT NOT NULL, created TEXT NOT NULL, last_login TEXT);
      CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, mode TEXT NOT NULL, file TEXT NOT NULL, sig TEXT, ai TEXT, score TEXT, decision TEXT NOT NULL, mine TEXT);
      CREATE INDEX IF NOT EXISTS reviews_user ON reviews(user_id, id);
      CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL, passed INTEGER NOT NULL, seconds INTEGER, detail TEXT);
      CREATE INDEX IF NOT EXISTS exams_user ON exams(user_id, id);
      CREATE TABLE IF NOT EXISTS practices(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created TEXT NOT NULL, mode TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS practices_user ON practices(user_id, id);
      CREATE TABLE IF NOT EXISTS exam_requests(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        review_id INTEGER, created TEXT NOT NULL, mode TEXT NOT NULL, file TEXT NOT NULL, label TEXT NOT NULL, defect INTEGER NOT NULL,
        photo TEXT NOT NULL, status TEXT NOT NULL DEFAULT '대기', decided TEXT, decided_by TEXT, note TEXT);
      CREATE INDEX IF NOT EXISTS exam_requests_status ON exam_requests(status, id);''')
    if 'photo' not in [r[1] for r in con.execute('PRAGMA table_info(reviews)')]:
        con.execute('ALTER TABLE reviews ADD COLUMN photo TEXT')   # older databases: records saved before photos were kept
    columns = {r[1] for r in con.execute('PRAGMA table_info(reviews)')}
    for column in ('reason', 'criterion'):
        if column not in columns:
            con.execute(f"ALTER TABLE reviews ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    return con


def now_text():
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


# ------------------------------------------------------------------ passwords
def hash_password(pw):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f'scrypt${salt.hex()}${digest.hex()}'


def check_password(pw, stored):
    try:
        _, salt, digest = stored.split('$')
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got.hex(), digest)
    except (ValueError, TypeError):
        return False


def clean_name(name):
    name = ' '.join(str(name or '').split())
    if not NAME_RE.match(name):
        raise AuthError('이름은 2~20자의 한글·영문·숫자로 입력하세요. (공백 . _ - 사용 가능)')
    return name


def check_new_password(pw):
    if not isinstance(pw, str) or not PW_MIN <= len(pw) <= PW_MAX:
        raise AuthError(f'비밀번호는 {PW_MIN}~{PW_MAX}자로 입력하세요.')
    if pw.isdigit() or pw.isalpha():
        raise AuthError('비밀번호에는 문자와 숫자를 함께 넣어 주세요.')


# ------------------------------------------------------------------ accounts and sessions
def _new_session(con, user_id):
    token = secrets.token_urlsafe(32)
    con.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
    con.execute('INSERT INTO sessions(token, user_id, expires) VALUES(?,?,?)',
                (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + SESSION_DAYS * 86400))
    con.execute('UPDATE users SET last_login=? WHERE id=?', (now_text(), user_id))
    return token


def signup(name, pw):
    """Create an account and return a session token."""
    name = clean_name(name); check_new_password(pw)
    if name.lower() in RESERVED_NAMES:  # the admin account is never self-registered (see create_admin)
        raise AuthError('사용할 수 없는 이름입니다. 다른 이름을 입력해 주세요.')
    with _lock, _connect() as con:
        if con.execute('SELECT 1 FROM users WHERE name=?', (name,)).fetchone():
            raise AuthError('이미 사용 중인 이름입니다. 이름 뒤에 사번이나 소속을 붙여 구분해 주세요.')
        cur = con.execute('INSERT INTO users(name, pw, created) VALUES(?,?,?)', (name, hash_password(pw), now_text()))
        return _new_session(con, cur.lastrowid)


# Early test build: a shared guest account, prefilled on the login page (login.py).
GUEST_NAME, GUEST_PW = 'guest', 'guest123'


def ensure_guest():
    """Create the shared guest account if it does not exist yet."""
    with _lock, _connect() as con:
        if not con.execute('SELECT 1 FROM users WHERE name=?', (GUEST_NAME,)).fetchone():
            con.execute('INSERT INTO users(name, pw, created) VALUES(?,?,?)', (GUEST_NAME, hash_password(GUEST_PW), now_text()))


def login(name, pw):
    """Return a session token, or raise AuthError with a message that does not reveal which part was wrong."""
    name = ' '.join(str(name or '').split())
    key = name.lower()
    with _lock:
        recent = [t for t in _fails.get(key, []) if t > time.time() - FAIL_WINDOW]
        _fails[key] = recent
        if len(recent) >= FAIL_LIMIT:
            raise AuthError('로그인 실패가 많아 잠시 막혔습니다. 5분 뒤에 다시 시도하세요.')
    with _connect() as con:
        row = con.execute('SELECT id, pw FROM users WHERE name=?', (name,)).fetchone()
        ok = check_password(str(pw or ''), row['pw'] if row else _DUMMY)  # same work whether or not the name exists
        if not row or not ok:
            with _lock:
                _fails.setdefault(key, []).append(time.time())
            raise AuthError('이름 또는 비밀번호가 맞지 않습니다.')
        _fails.pop(key, None)
        return _new_session(con, row['id'])


def user_for_token(token):
    if not token or len(token) > 100:
        return None
    with _connect() as con:
        row = con.execute('SELECT u.id, u.name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',
                          (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    return {'id': row['id'], 'name': row['name']} if row else None


def user_info(user_id):
    with _connect() as con:
        row = con.execute('SELECT name, created, last_login FROM users WHERE id=?', (user_id,)).fetchone()
    return dict(row) if row else None


def logout(token):
    if token:
        with _connect() as con:
            con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))


def current_user():
    """The logged-in user of this Streamlit session (from the HttpOnly cookie), or None."""
    import streamlit as st
    token = st.context.cookies.get(COOKIE)
    cached = st.session_state.get('t13_user')
    if cached and cached.get('_t') == token:
        return cached['user']
    user = user_for_token(token)
    st.session_state['t13_user'] = {'_t': token, 'user': user}
    return user


# ------------------------------------------------------------------ reviewed photos
def shrink_photo(data):
    """Reduced JPEG copy: upright, long edge <= PHOTO_EDGE, no EXIF (camera, GPS) or other metadata."""
    from PIL import Image, ImageOps
    import io
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((PHOTO_EDGE, PHOTO_EDGE))
        out = io.BytesIO(); im.save(out, 'JPEG', quality=85, optimize=True)   # no exif= / icc_profile= -> metadata dropped
    return out.getvalue()


def _user_dir(user_id):
    return PHOTO_DIR / str(int(user_id))


def save_photo(user_id, sig, data):
    """Store the reduced copy as <user id>/<sha256 of the original>.jpg (one file per photo per user); return that name."""
    if not SIG_RE.match(str(sig or '')):
        raise ValueError('bad photo id')
    folder = _user_dir(user_id)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(PHOTO_DIR, 0o700)
    target = folder / f'{sig}.jpg'
    if not target.exists():
        tmp = folder / f'.{sig}.{secrets.token_hex(4)}.tmp'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(shrink_photo(data))
        os.replace(tmp, target)
    return f'{int(user_id)}/{sig}.jpg'


def photo_file(user_id, name):
    """Path of a stored photo only if it belongs to user_id (the name must sit in that user's own folder)."""
    if not name:
        return None
    path = (PHOTO_DIR / name).resolve()
    if path.parent != _user_dir(user_id).resolve() or not SIG_RE.match(path.stem) or path.suffix != '.jpg':
        return None
    return path if path.is_file() else None


def _drop_unused(con, rows):
    for user_id, name in {(r['user_id'], r['photo']) for r in rows}:
        if not con.execute('SELECT 1 FROM reviews WHERE user_id=? AND photo=?', (user_id, name)).fetchone():
            path = photo_file(user_id, name)
            if path:
                path.unlink(missing_ok=True)


def purge_old_photos(days=PHOTO_DAYS):
    """Delete photos of records older than `days`; the text records stay. Returns how many records lost their photo."""
    cutoff = (datetime.now(KST) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    with _connect() as con:
        rows = con.execute('SELECT user_id, photo FROM reviews WHERE photo IS NOT NULL AND created < ?', (cutoff,)).fetchall()
        if rows:
            con.execute('UPDATE reviews SET photo=NULL WHERE photo IS NOT NULL AND created < ?', (cutoff,))
            _drop_unused(con, rows)
    return len(rows)


def delete_photos(user_id):
    """The user removes all of their stored photos (records stay). Returns how many records had a photo."""
    with _connect() as con:
        n = con.execute('UPDATE reviews SET photo=NULL WHERE user_id=? AND photo IS NOT NULL', (user_id,)).rowcount
    shutil.rmtree(_user_dir(user_id), ignore_errors=True)
    return n


def delete_reviews(user_id, review_ids):
    """The user deletes chosen review records outright (text + their kept photo when no other record uses it).
    Only the user's own rows are touched. Exam-question copies already requested stay with the admin. Returns count."""
    ids = [int(i) for i in review_ids]
    if not ids:
        return 0
    marks = ','.join('?' * len(ids))
    with _lock, _connect() as con:
        rows = con.execute(f'SELECT user_id, photo FROM reviews WHERE user_id=? AND id IN ({marks})', [user_id] + ids).fetchall()
        n = con.execute(f'DELETE FROM reviews WHERE user_id=? AND id IN ({marks})', [user_id] + ids).rowcount
        _drop_unused(con, [r for r in rows if r['photo']])
    return n


# ------------------------------------------------------------------ review records
def add_review(user_id, mode, rec, photo=None):
    """Save one decision; `photo` (original bytes, with the reviewer's consent) is stored as a reduced copy."""
    name = save_photo(user_id, rec.get('sig'), photo) if photo else None
    with _connect() as con:
        cur = con.execute('INSERT INTO reviews(user_id, created, mode, file, sig, ai, score, decision, mine, photo, reason, criterion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (user_id, now_text(), mode, rec['file'], rec.get('sig'), rec['ai'], rec['score'], rec['decision'], rec['mine'], name,
                     str(rec.get('reason') or '')[:1500], str(rec.get('criterion') or '')[:300]))
        review_id = cur.lastrowid
    purge_old_photos()
    return review_id


def reviews_for(user_id, mode=None):
    q = 'SELECT id, created, mode, file, ai, score, decision, mine, photo, reason, criterion FROM reviews WHERE user_id=?' + (' AND mode=?' if mode else '') + ' ORDER BY id DESC'
    with _connect() as con:
        return [dict(r) for r in con.execute(q, (user_id, mode) if mode else (user_id,))]


# ------------------------------------------------------------------ exam (수행능력 평가) results
def add_exam(user_id, score, total, passed, seconds, detail):
    """Save one finished exam; detail = per-question answers (JSON-able list)."""
    with _connect() as con:
        con.execute('INSERT INTO exams(user_id, created, score, total, passed, seconds, detail) VALUES(?,?,?,?,?,?,?)',
                    (user_id, now_text(), int(score), int(total), int(bool(passed)), int(seconds), json.dumps(detail, ensure_ascii=False)))


def exams_for(user_id):
    with _connect() as con:
        rows = [dict(r) for r in con.execute('SELECT created, score, total, passed, seconds, detail FROM exams WHERE user_id=? ORDER BY id DESC', (user_id,))]
    for r in rows:
        try: r['detail'] = json.loads(r['detail'] or '[]')
        except ValueError: r['detail'] = []
    return rows


# ------------------------------------------------------------------ exam question requests (검토 기록 -> 시험 문제)
# A learner picks reviewed photos in 마이페이지 and asks for them to become exam questions; the admin account
# approves or rejects each one. The photo is copied into POOL_DIR when requested, so it outlives the 90-day
# review-photo purge and the learner's "delete my photos" button.
ADMIN_NAME = 'admin'
POOL_DIR = Path(os.environ.get('T13_POOL', DB_PATH.parent / 'exam_pool'))
REQ_WAIT, REQ_OK, REQ_NO = '대기', '승인', '반려'


RESERVED_NAMES = {ADMIN_NAME, 'administrator', '관리자', '운영자'}


def create_admin(pw):
    """Server-side only (python -c): create the admin account on a fresh database."""
    check_new_password(pw)
    with _lock, _connect() as con:
        if not con.execute('SELECT 1 FROM users WHERE name=?', (ADMIN_NAME,)).fetchone():
            con.execute('INSERT INTO users(name, pw, created) VALUES(?,?,?)', (ADMIN_NAME, hash_password(pw), now_text()))


def is_admin(user):
    return bool(user) and str(user.get('name', '')).lower() == ADMIN_NAME


def can_judge(user):
    """판정 검토 자격: the admin account, or anyone who passed 역량평가 at least once."""
    if not user:
        return False
    if is_admin(user):
        return True
    with _connect() as con:
        return con.execute('SELECT 1 FROM exams WHERE user_id=? AND passed=1 LIMIT 1', (user['id'],)).fetchone() is not None


def label_of(mine):
    """'양품 · 폼스프레이양품' / '탱크클리닝불량' -> (class label, is_defect)."""
    cls = str(mine or '').split(' · ')[-1].strip()
    return cls, '양품' not in cls


def request_exam(user_id, review_ids):
    """Queue the user's own reviews (with a kept photo) as exam-question requests. Returns (added, skipped)."""
    added = skipped = 0
    POOL_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with _lock, _connect() as con:
        for rid in review_ids:
            r = con.execute('SELECT id, mode, file, mine, photo FROM reviews WHERE id=? AND user_id=?', (int(rid), user_id)).fetchone()
            src = photo_file(user_id, r['photo']) if r else None
            dup = src and con.execute("SELECT 1 FROM exam_requests WHERE user_id=? AND photo LIKE ? AND status!=?",
                                    (user_id, f"%{Path(r['photo']).stem}%", REQ_NO)).fetchone()
            if not src or dup:
                skipped += 1; continue
            label, defect = label_of(r['mine'])
            cur = con.execute('INSERT INTO exam_requests(user_id, review_id, created, mode, file, label, defect, photo) VALUES(?,?,?,?,?,?,?,?)',
                              (user_id, r['id'], now_text(), r['mode'], r['file'], label, int(defect), ''))
            name = f'{cur.lastrowid}_{src.stem}.jpg'
            shutil.copyfile(src, POOL_DIR / name); os.chmod(POOL_DIR / name, 0o600)
            con.execute('UPDATE exam_requests SET photo=? WHERE id=?', (name, cur.lastrowid))
            added += 1
    return added, skipped


def pool_file(name):
    path = (POOL_DIR / str(name or '')).resolve()
    return path if name and path.parent == POOL_DIR.resolve() and path.suffix == '.jpg' and path.is_file() else None


def exam_requests(user_id=None, status=None):
    q = ('SELECT q.id, q.user_id, u.name AS requester, q.review_id, q.created, q.mode, q.file, q.label, q.defect, q.photo, q.status, '
         'q.decided, q.decided_by, q.note FROM exam_requests q JOIN users u ON u.id=q.user_id WHERE 1=1')
    args = []
    if user_id is not None: q += ' AND q.user_id=?'; args.append(user_id)
    if status: q += ' AND q.status=?'; args.append(status)
    with _connect() as con:
        return [dict(r) for r in con.execute(q + ' ORDER BY q.id DESC', args)]


def decide_exam_request(admin, req_id, approve, defect=None, note=None):
    """Admin only: approve (optionally correcting the 양품/불량 answer) or reject one waiting request."""
    if not is_admin(admin):
        raise AuthError('관리자만 승인할 수 있습니다.')
    with _lock, _connect() as con:
        sets, args = ['status=?', 'decided=?', 'decided_by=?', 'note=?'], [REQ_OK if approve else REQ_NO, now_text(), admin['name'], note]
        old = con.execute('SELECT defect FROM exam_requests WHERE id=?', (int(req_id),)).fetchone()
        if approve and defect is not None and old and bool(old['defect']) != bool(defect):
            sets += ['defect=?', 'label=?']; args += [int(bool(defect)), ('불량' if defect else '양품') + ' (관리자 정정)']
        con.execute(f"UPDATE exam_requests SET {', '.join(sets)} WHERE id=? AND status=?", args + [int(req_id), REQ_WAIT])
        if not approve:
            row = con.execute('SELECT photo FROM exam_requests WHERE id=?', (int(req_id),)).fetchone()
            path = pool_file(row['photo']) if row else None
            if path: path.unlink(missing_ok=True)


def exam_pool(mode):
    """Approved requests as exam cases (same shape as inspection.load_cases)."""
    out = []
    for r in exam_requests(status=REQ_OK):
        path = pool_file(r['photo'])
        if r['mode'] == mode and path:
            out.append({'id': f"pool{r['id']}", 'path': str(path), 'cls': r['label'], 'defect': bool(r['defect']), 'place': '', 'pool': True})
    return out


# ------------------------------------------------------------------ 직접 판단 실습 results (score only, no photos)
def add_practice(user_id, mode, score, total):
    with _connect() as con:
        con.execute('INSERT INTO practices(user_id, created, mode, score, total) VALUES(?,?,?,?,?)',
                    (user_id, now_text(), mode, int(score), int(total)))


def practices_for(user_id):
    with _connect() as con:
        return [dict(r) for r in con.execute('SELECT created, mode, score, total FROM practices WHERE user_id=? ORDER BY id DESC', (user_id,))]
