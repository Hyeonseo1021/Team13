import html
import json
from functools import lru_cache
from pathlib import Path
from ui import shell

def illustration(kind):
    grid='<defs><pattern id="grid-'+kind+'" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="#c2d2e1" stroke-width=".5" opacity=".5"/></pattern></defs><rect x="-400" y="-200" width="1200" height="560" fill="url(#grid-'+kind+')"/>'
    if kind=='classification':
        drawing='''<ellipse cx="217" cy="135" rx="99" ry="8" fill="#cfdced"/><path d="M142 58v64c0 20 142 20 142 0V58" fill="#d8e3f2" stroke="#6583aa" stroke-width="1.5"/><ellipse cx="213" cy="58" rx="71" ry="21" fill="#f4f7fc" stroke="#6583aa" stroke-width="1.5"/><ellipse cx="213" cy="57" rx="48" ry="12" fill="#e5edf7"/><path d="M164 70v54m24-48v54m25-51v53m25-56v54m24-58v53" stroke="#adbed6"/><path d="M130 45v-9h18m137 0h14v13m0 72v16h-15m-143 0h-14v-15" fill="none" stroke="#3266b6" stroke-width="2"/><rect x="268" y="82" width="85" height="31" rx="5" fill="#fff" stroke="#b7cae4"/><circle cx="284" cy="97" r="7" fill="#dcebe4"/><path d="m281 97 2 2 4-5" fill="none" stroke="#41795a" stroke-width="1.5"/><text x="299" y="101" font-family="sans-serif" font-size="10" fill="#355b83">CLASSIFY</text>'''
    elif kind=='detection':
        drawing='''<rect x="117" y="47" width="171" height="92" rx="6" fill="#d9e6e2" stroke="#809f94"/><path d="M128 93h147M203 57v70" stroke="#a6bfb5"/><g fill="#edf5f1" stroke="#739386" stroke-width="2"><path d="m143 63 14-8 14 8v16l-14 8-14-8Z"/><circle cx="157" cy="71" r="6"/><path d="m231 103 14-8 14 8v16l-14 8-14-8Z"/><circle cx="245" cy="111" r="6"/></g><path d="M185 122c0-52 91 1 91-52" fill="none" stroke="#587c70" stroke-width="7"/><path d="M185 122c0-52 91 1 91-52" fill="none" stroke="#9ab7ab" stroke-width="2"/><rect x="136" y="51" width="42" height="43" rx="2" fill="none" stroke="#2f8870" stroke-width="2"/><rect x="225" y="91" width="41" height="43" rx="2" fill="none" stroke="#2f8870" stroke-width="2"/><rect x="179" y="65" width="105" height="63" rx="2" fill="none" stroke="#3d6ba2" stroke-dasharray="4 3"/><rect x="276" y="37" width="73" height="25" rx="4" fill="white" stroke="#b6cec4"/><text x="288" y="53" font-family="sans-serif" font-size="10" fill="#34715b">DETECT</text>'''
    else:
        drawing='''<path d="M120 45h178v94H120Z" fill="#dedbea" stroke="#9184ab"/><path d="M142 45v94m25-94v94m25-94v94m25-94v94m25-94v94m25-94v94" stroke="#c6bfd5"/><path d="m157 45 13 17-5 15 18 18-5 16 20 28" fill="none" stroke="#9c82b7" stroke-width="16" opacity=".35"/><path d="m157 45 13 17-5 15 18 18-5 16 20 28" fill="none" stroke="#806299" stroke-width="3"/><path d="m230 65 24-6 13 13-2 21-24 4-18-12Z" fill="#8f78bd" fill-opacity=".45" stroke="#8060ad" stroke-width="1.5" stroke-dasharray="3 2"/><rect x="216" y="51" width="58" height="54" rx="3" fill="none" stroke="#76599f"/><path d="m272 75 19-17h27" fill="none" stroke="#8a73ab"/><rect x="287" y="38" width="66" height="25" rx="4" fill="white" stroke="#c4b7d8"/><text x="298" y="54" font-family="sans-serif" font-size="10" fill="#74558e">MASK</text>'''
    # All three drawings span about x 118-353, y 36-143 (centre 235,89). The viewBox is centred on that with even
    # margins; the grid rect is oversized so it still covers the box when the slide aspect ratio is wider or taller.
    return '<svg viewBox="51 14 320 150" preserveAspectRatio="xMidYMid meet" role="img" aria-label="'+{'classification':'탱크 표면 전체를 분류하는 검사 도식','detection':'볼트와 케이블의 사각형 탐지 도식','segmentation':'표면 결함 후보의 픽셀 영역을 표시한 도식'}[kind]+'">'+grid+drawing+'</svg>'

SLIDES=[('classification','1','표면 상태 분류','탱크 클리닝과 폼스프레이 상태를 사진 전체 기준으로 판정합니다.'),
        ('detection','2','볼트·케이블 탐지','볼트 체결부와 케이블 설치 상태를 객체별 사각형으로 찾습니다.'),
        ('segmentation','3','결함 영역 분할','용접·도장·보온재 결함이 의심되는 영역을 픽셀 단위로 표시합니다.')]
# Inspections 1·2·3 are reachable from the GNB and the hero slides; these helper links sit in the 학습 순서 card.
# The home page has no learning assistant (it lives on the inspection pages).
SERVICES=[('book','실습 이용 가이드','href','?page=guide'),('list','판정 클래스 안내','href','?page=classes')]

HERO_DIR=Path(__file__).resolve().parent/'assets'/'hero'


@lru_cache(maxsize=None)
def _hero_photo(kind, mtime):
    import base64
    return base64.b64encode((HERO_DIR/f'{kind}.jpg').read_bytes()).decode('ascii')


def slide_art(kind):
    """Real inspection result photo (assets/hero, made by running the model on one sample per inspection) over the
    illustration; the SVG stays underneath as the sizing box and as a fallback when the photo is missing."""
    path=HERO_DIR/f'{kind}.jpg'
    try:meta=json.loads((HERO_DIR/'hero.json').read_text(encoding='utf-8')).get(kind)
    except (OSError,ValueError):meta=None
    if not path.is_file() or not meta:return illustration(kind)
    score=f" {meta['score']:.1f}%" if meta.get('score') is not None else ''
    alt=f"실제 검사 결과 사진: AI 판정 {meta['verdict']} · {meta['label']}{score}"
    return (illustration(kind).replace('role="img"','aria-hidden="true" focusable="false"',1)
            +f'<img class="slide-photo" src="data:image/jpeg;base64,{_hero_photo(kind,path.stat().st_mtime)}" alt="{html.escape(alt)}">'
            +f'<span class="slide-ai" aria-hidden="true"><span>AI 판정</span><b class="{"bad" if meta["verdict"]=="불량" else "good"}">{html.escape(meta["verdict"])}</b>{html.escape(meta["label"])}{score}</span>')


def hero():
    from ui import icon
    slides=''.join(f'<div class="slide slide-{k}" role="group" aria-roledescription="슬라이드" aria-label="{i+1} / {len(SLIDES)}"'+(' hidden' if i else '')+f'><a class="slide-link" href="?inspection={k}"><span class="slide-art">{slide_art(k)}<span class="beam" aria-hidden="true"></span></span><span class="slide-body"><span class="slide-num" aria-hidden="true">{n}</span><span class="slide-text"><strong>{t}</strong>{d}</span><span class="slide-go">검사 바로가기<span aria-hidden="true"> →</span></span></span></a></div>' for i,(k,n,t,d) in enumerate(SLIDES))
    return ('<section class="hero" aria-labelledby="hero-title"><div class="hero-copy">'
      '<h1 id="hero-title">현장을 이해하는 첫걸음,<br><em>LNG탱크 품질검사는 <i class="t13-brand">LNG_NI</i>&nbsp;&nbsp;와 함께</em></h1>'
      '<p class="hero-desc">직접 관찰하고, 검사하고, 비교하며 배우세요. <br>LNG 탱크 품질검사를 위한 신입직원 실습 공간입니다.</p>'
      '<div class="hero-actions"><a class="btn btn-primary" href="?inspection=classification">시작하기</a><a class="btn btn-line" href="?page=guide">이용 가이드 보기</a></div></div>'
      '<div class="hero-slider" role="region" aria-roledescription="캐러셀" aria-label="검사 종류 소개"><div class="slides" aria-live="off">'+slides+'</div>'
      '<div class="slider-ctrl"><button type="button" class="slide-prev" aria-label="이전 슬라이드">‹</button><span class="slide-count" aria-hidden="true"><b class="slide-current">1</b> / '+str(len(SLIDES))+'</span>'
      '<button type="button" class="slide-next" aria-label="다음 슬라이드">›</button></div></div></section>')

def services():
    from ui import icon, menu_link
    items=''.join('<li>'+(f'<a class="svc" href="{v}">' if k=='href' else f'<button type="button" class="svc" data-{k}="{v}">')+f'<span class="svc-icon">{icon(ic)}</span><span class="svc-label">{label}</span>'+('</a>' if k=='href' else '</button>')+'</li>' for ic,label,k,v in SERVICES)
    return '<section class="services" aria-labelledby="svc-title"><h2 id="svc-title" class="sr-only">자주 찾는 서비스</h2><ul class="svc-grid">'+items+'</ul></section>'

REVIEW_HREF='?page=judge&inspection=classification'
STEPS=[('1','직접 판단 실습','사진을 보고 불량을 직접 골라 정답과 비교합니다.','?inspection=classification'),
       ('2','역량평가','혼자 힘으로 15문항을 풀어 80점 이상이면 합격합니다.','?page=exam'),
       ('3','판정 검토','합격 후 AI 판정을 승인·거절하며 기록을 남깁니다.',REVIEW_HREF)]

def _ago(created):
    """'2026-11-07 20:24:17' -> '3분 전' style (KST, same clock as accounts.now_text)."""
    from datetime import datetime
    import accounts
    try:
        then=datetime.strptime(created,'%Y-%m-%d %H:%M:%S').replace(tzinfo=accounts.KST)
    except (TypeError,ValueError):
        return ''
    sec=(datetime.now(accounts.KST)-then).total_seconds()
    if sec<60:return '방금 전'
    if sec<3600:return f'{int(sec//60)}분 전'
    if sec<86400:return f'{int(sec//3600)}시간 전'
    return created[5:10].replace('-','.')

def status_card(on_mypage=False):
    """내 학습 현황: progress through the three stages (직접 판단 실습 -> 역량평가 -> 판정 검토) and a next-step
    button. Same card on home and 마이페이지."""
    import html
    from urllib.parse import urlencode
    import accounts
    from ui import icon
    user=accounts.current_user()
    head='<div class="band-head"><h2 id="status-title">내 학습 현황</h2>'
    if not user:
        login='?'+html.escape(urlencode({'page':'login','next':'?page=my' if on_mypage else '?'}))
        return ('<section class="band-card status-card" aria-labelledby="status-title">'+head+'</div>'
                '<div class="status-empty"><span class="status-empty-icon">'+icon('user')+'</span><div><strong>로그인하면 내 학습 진도가 여기에 쌓입니다</strong>'
                '<p>실습 정답률, 역량평가 점수와 합격 여부, 판정 검토 건수를 한눈에 볼 수 있습니다.</p></div>'
                f'<a class="btn btn-primary status-login" href="{login}">로그인 / 회원가입</a></div></section>')
    from inspection import MODES
    name=html.escape(user['name'])
    practice=accounts.practices_for(user['id']); exams=accounts.exams_for(user['id']); reviews=accounts.reviews_for(user['id'])
    can=accounts.can_judge(user); passed=any(e['passed'] for e in exams)
    head+=('</div>' if on_mypage else '<a class="band-more" href="?page=my">마이페이지 <span aria-hidden="true">›</span></a></div>')
    pct=lambda s,t: round(s*100/t) if t else 0
    # ① 직접 판단 실습
    if practice:
        acc=pct(sum(p['score'] for p in practice),sum(p['total'] for p in practice))
        t1=('ok' if acc>=80 else '',f'{acc}<small>%</small>',f'{len(practice)}회 · 평균 정답률')
    else: t1=('','-','아직 풀지 않음')
    # ② 역량평가
    if exams:
        best=max(pct(e['score'],e['total']) for e in exams)
        t2=('ok' if passed else 'ng',f'{best}<small>점</small>',('합격' if passed else '불합격')+f' · 응시 {len(exams)}회')
    else: t2=('','-','아직 응시하지 않음')
    # ③ 판정 검토
    if not can: t3=('lock','🔒','역량평가 합격 후 열림')
    elif reviews:
        ok=sum(r['decision']=='승인' for r in reviews)
        t3=('',f'{len(reviews)}<small>건</small>',f'승인 {ok} · 거절 {len(reviews)-ok}')
    else: t3=('','0<small>건</small>','검토를 시작해 보세요')
    # ④ 다음 할 일
    if can: nxt=('판정 검토 시작',REVIEW_HREF,'AI 판정을 승인·거절하며 기록합니다')
    elif not practice: nxt=('직접 판단 실습 시작','?inspection=classification','먼저 사진을 보고 불량을 골라 보세요')
    else: nxt=('역량평가 응시하기','?page=exam','80점 이상이면 판정 검토가 열립니다')
    tiles=''.join(f'<li class="{c}"><a href="{h}"><span class="ss-label">{l}</span><b>{v}</b><span class="ss-sub">{sub}</span></a></li>'
                  for l,h,(c,v,sub) in [('① 직접 판단 실습','?inspection=classification',t1),('② 역량평가','?page=exam',t2),('③ 판정 검토',REVIEW_HREF,t3)])
    tiles+=(f'<li class="next"><a href="{nxt[1]}"><span class="ss-label">다음 할 일</span><b>{nxt[0]} <span aria-hidden="true">→</span></b>'
            f'<span class="ss-sub">{nxt[2]}</span></a></li>')
    stage='판정 검토 단계' if can else ('역량평가 단계' if practice else '실습 단계')
    return ('<section class="band-card status-card" aria-labelledby="status-title">'+head+
            f'<p class="status-who"><b>{name}</b> 님 · 지금은 <b>{stage}</b>입니다</p>'
            '<ul class="status-steps status-steps-only">'+tiles+'</ul></section>')

def steps_card():
    """학습 순서: three step cards in a row (stacked on phones), with the helper links in a footer row."""
    from ui import icon
    items=''.join(f'<li><a href="{href}"><span class="step-top"><span class="step-no">{no}</span><strong>{title}</strong></span>'
                  f'<span class="step-desc">{desc}</span><span class="step-go">바로가기<span aria-hidden="true"> →</span></span></a></li>' for no,title,desc,href in STEPS)
    links=''.join((f'<a class="band-link" href="{v}">' if k=='href' else f'<button type="button" class="band-link" data-{k}="{v}">')+f'{icon(ic)}{label}'+('</a>' if k=='href' else '</button>') for ic,label,k,v in SERVICES)
    # help links sit in the title row (not a footer row) so this card is no taller than 내 학습 현황 beside it
    return ('<section class="band-card steps-card" aria-labelledby="steps-title"><div class="band-head"><div><h2 id="steps-title">학습 순서</h2>'
            '<p class="steps-sub">세 단계로 차근차근 실습해 보세요</p></div><span class="band-links steps-links" aria-label="처음이라면 먼저 확인하세요">'+links+'</span></div>'
            '<ol class="learn-steps">'+items+'</ol></section>')

def band():
    return '<div class="home-band">'+status_card()+steps_card()+'</div>'

def render():
    shell(is_home=True,home='<main id="workspace" tabindex="-1" class="home-main">'+hero()+band()+'</main>')
