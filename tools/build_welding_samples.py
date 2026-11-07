"""Build demo_cases/raw/team13_welding in the same layout as team13_pipe / team13_samples:

    team13_welding/samples.csv          클래스명, 이미지 파일, 라벨 파일, 원본 정보, 크기, 용량
    team13_welding/<클래스>/<stem>.jpg   photo and its AI Hub label JSON side by side
    team13_welding/<클래스>/<stem>.json

Source: the class-folder zip (클래스별/<클래스>/이미지|라벨/...) plus the pair index
demo_cases/incoming/welding_tmp/samples.csv (English columns, one row per pair, class_names as a JSON list).
Only single-class pairs are used: in multi-class labels annotations[0] decides the answer, which can be the
wrong class (e.g. a scratch photo whose first annotation is 용접양품).

The zip may still be uploading: an rsync temp file is read entry by entry up to the last complete one, so the
script can run early and be re-run later. Pairs already in the output are kept; each class is topped up to
--per-class from a fixed seeded order. Re-running is safe.

    ~/venv/bin/python tools/build_welding_samples.py [--zip PATH] [--per-class 20] [--dry-run]
"""
import argparse, csv, json, os, random, struct, sys, zipfile, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCOMING = ROOT / 'demo_cases/incoming'
OUT = ROOT / 'demo_cases/raw/team13_welding'
INDEX = INCOMING / 'welding_tmp/samples.csv'
CLASSES = ['용접불량', '용접양품', '용접블로우홀']
HEADER = ['클래스명', '이미지 파일', '라벨 파일', '이미지 원본(아카이브)', '라벨 원본(아카이브)', '이미지 크기(px)', '용량(MB)']


def find_zip():
    base = INCOMING / 'LNG_클래스별_데이터_20261107'
    done = base / 'LNG_클래스별_전체.zip'
    if done.is_file() and zipfile.is_zipfile(done):
        return done
    temps = sorted(base.glob('.LNG_클래스별_전체.zip.*'), key=lambda p: p.stat().st_mtime)
    if temps:
        return temps[-1]
    sys.exit('zip not found under ' + str(base))


class PartialZip:
    """Complete local entries of a zip that may still be growing (no central directory needed)."""

    def __init__(self, path):
        self.f = open(path, 'rb')
        self.entries = {}
        size, pos = os.path.getsize(path), 0
        while True:
            self.f.seek(pos)
            h = self.f.read(30)
            if len(h) < 30 or h[:4] != b'PK\x03\x04':
                break
            _, flag, meth, _, _, crc, cs, us, nl, el = struct.unpack('<HHHHHIIIHH', h[4:])
            name = self.f.read(nl).decode('utf-8' if flag & 0x800 else 'cp437')
            extra = self.f.read(el)
            if flag & 8:  # sizes only after the data: cannot skip safely
                break
            if cs == 0xFFFFFFFF or us == 0xFFFFFFFF:
                i = 0
                while i + 4 <= len(extra):
                    hid, hs = struct.unpack('<HH', extra[i:i + 4])
                    if hid == 1:
                        us, cs = struct.unpack('<QQ', extra[i + 4:i + 20])
                        break
                    i += 4 + hs
            data_at = pos + 30 + nl + el
            if data_at + cs > size:
                break
            self.entries[name] = (data_at, cs, meth, crc)
            pos = data_at + cs

    def names(self):
        return self.entries.keys()

    def read(self, name):
        at, cs, meth, crc = self.entries[name]
        self.f.seek(at)
        raw = self.f.read(cs)
        data = raw if meth == 0 else zlib.decompressobj(-15).decompress(raw) if meth == 8 else None
        if data is None or zlib.crc32(data) != crc:
            raise ValueError('bad entry ' + name)
        return data


def open_zip(path):
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        return z, True
    return PartialZip(path), False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', type=Path)
    ap.add_argument('--per-class', type=int, default=20)
    ap.add_argument('--seed', type=int, default=13)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    path = a.zip or find_zip()
    z, complete = open_zip(path)
    names = set(z.namelist() if complete else z.names())
    print(f'zip: {path.name} ({"complete" if complete else "partial upload"}, {len(names)} entries readable)')

    rows = list(csv.DictReader(INDEX.open(encoding='utf-8-sig', newline='')))
    meta = {}
    for cls in CLASSES:
        single = sorted((r for r in rows if json.loads(r['class_names']) == [cls]), key=lambda r: r['stem'])
        random.Random(f'{a.seed}:{cls}').shuffle(single)
        # count only complete pairs: other tools may leave labels without photos in the class folder
        have = {p.stem for p in (OUT / cls).glob('*.json') if any(q.suffix.lower() in ('.jpg', '.jpeg', '.png') for q in p.parent.glob(p.stem + '.*'))} if (OUT / cls).is_dir() else set()
        added = 0
        for r in single:
            if len(have) >= a.per_class:
                break
            if r['stem'] in have:
                continue
            img, lab = f'클래스별/{cls}/이미지/{r["image_filename"]}', f'클래스별/{cls}/라벨/{r["json_filename"]}'
            if img not in names or lab not in names:
                continue
            if not a.dry_run:
                (OUT / cls).mkdir(parents=True, exist_ok=True)
                (OUT / cls / r['image_filename']).write_bytes(z.read(img))
                (OUT / cls / r['json_filename']).write_bytes(z.read(lab))
            have.add(r['stem']); added += 1
        print(f'  {cls}: {len(have)}/{a.per_class} (+{added}, single-class pairs in index {len(single)})')
        for r in single:
            meta[r['stem']] = r
    if a.dry_run:
        return

    out_rows = []
    for cls in CLASSES:
        for lab in sorted((OUT / cls).glob('*.json')) if (OUT / cls).is_dir() else []:
            r = meta.get(lab.stem)
            imgs = [p for p in lab.parent.glob(lab.stem + '.*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
            if not r or not imgs:
                continue
            img = imgs[0]
            try:
                info = json.loads(lab.read_text(encoding='utf-8'))['images'][0]
                px = f"{info['width']}x{info['height']}"
            except (ValueError, KeyError, IndexError):
                px = ''
            out_rows.append([cls, img.name, lab.name, f"{r['image_archive']}!/{r['image_archive_member'].lstrip('/')}",
                             f"{r['json_archive']}!/{r['json_archive_member'].lstrip('/')}", px, f'{img.stat().st_size / 1e6:.3f}'])
    with (OUT / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(out_rows)
    print(f'samples.csv: {len(out_rows)} rows')


if __name__ == '__main__':
    main()
