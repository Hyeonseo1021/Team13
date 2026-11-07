from ui import shell

def illustration(kind):
    grid='<defs><pattern id="grid-'+kind+'" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="#c2d2e1" stroke-width=".5" opacity=".5"/></pattern></defs><rect width="400" height="160" fill="url(#grid-'+kind+')"/>'
    if kind=='classification':
        drawing='''<ellipse cx="217" cy="135" rx="99" ry="8" fill="#cfdced"/><path d="M142 58v64c0 20 142 20 142 0V58" fill="#d8e3f2" stroke="#6583aa" stroke-width="1.5"/><ellipse cx="213" cy="58" rx="71" ry="21" fill="#f4f7fc" stroke="#6583aa" stroke-width="1.5"/><ellipse cx="213" cy="57" rx="48" ry="12" fill="#e5edf7"/><path d="M164 70v54m24-48v54m25-51v53m25-56v54m24-58v53" stroke="#adbed6"/><path d="M130 45v-9h18m137 0h14v13m0 72v16h-15m-143 0h-14v-15" fill="none" stroke="#3266b6" stroke-width="2"/><rect x="268" y="82" width="85" height="31" rx="5" fill="#fff" stroke="#b7cae4"/><circle cx="284" cy="97" r="7" fill="#dcebe4"/><path d="m281 97 2 2 4-5" fill="none" stroke="#41795a" stroke-width="1.5"/><text x="299" y="101" font-family="sans-serif" font-size="10" fill="#355b83">CLASSIFY</text>'''
    elif kind=='detection':
        drawing='''<rect x="117" y="47" width="171" height="92" rx="6" fill="#d9e6e2" stroke="#809f94"/><path d="M128 93h147M203 57v70" stroke="#a6bfb5"/><g fill="#edf5f1" stroke="#739386" stroke-width="2"><path d="m143 63 14-8 14 8v16l-14 8-14-8Z"/><circle cx="157" cy="71" r="6"/><path d="m231 103 14-8 14 8v16l-14 8-14-8Z"/><circle cx="245" cy="111" r="6"/></g><path d="M185 122c0-52 91 1 91-52" fill="none" stroke="#587c70" stroke-width="7"/><path d="M185 122c0-52 91 1 91-52" fill="none" stroke="#9ab7ab" stroke-width="2"/><rect x="136" y="51" width="42" height="43" rx="2" fill="none" stroke="#2f8870" stroke-width="2"/><rect x="225" y="91" width="41" height="43" rx="2" fill="none" stroke="#2f8870" stroke-width="2"/><rect x="179" y="65" width="105" height="63" rx="2" fill="none" stroke="#3d6ba2" stroke-dasharray="4 3"/><rect x="276" y="37" width="73" height="25" rx="4" fill="white" stroke="#b6cec4"/><text x="288" y="53" font-family="sans-serif" font-size="10" fill="#34715b">DETECT</text>'''
    else:
        drawing='''<path d="M120 45h178v94H120Z" fill="#dedbea" stroke="#9184ab"/><path d="M142 45v94m25-94v94m25-94v94m25-94v94m25-94v94m25-94v94" stroke="#c6bfd5"/><path d="m157 45 13 17-5 15 18 18-5 16 20 28" fill="none" stroke="#9c82b7" stroke-width="16" opacity=".35"/><path d="m157 45 13 17-5 15 18 18-5 16 20 28" fill="none" stroke="#806299" stroke-width="3"/><path d="m230 65 24-6 13 13-2 21-24 4-18-12Z" fill="#8f78bd" fill-opacity=".45" stroke="#8060ad" stroke-width="1.5" stroke-dasharray="3 2"/><rect x="216" y="51" width="58" height="54" rx="3" fill="none" stroke="#76599f"/><path d="m272 75 19-17h27" fill="none" stroke="#8a73ab"/><rect x="287" y="38" width="66" height="25" rx="4" fill="white" stroke="#c4b7d8"/><text x="298" y="54" font-family="sans-serif" font-size="10" fill="#74558e">MASK</text>'''
    return '<svg viewBox="0 0 400 160" role="img" aria-label="'+{'classification':'탱크 표면 전체를 분류하는 검사 도식','detection':'볼트와 케이블의 사각형 탐지 도식','segmentation':'표면 결함 후보의 픽셀 영역을 표시한 도식'}[kind]+'">'+grid+drawing+'</svg>'

SLIDES=[('classification','1','표면 상태 분류','탱크 클리닝과 폼스프레이 상태를 사진 전체 기준으로 판정합니다.'),
        ('detection','2','볼트·케이블 탐지','볼트 체결부와 케이블 설치 상태를 객체별 사각형으로 찾습니다.'),
        ('segmentation','3','결함 영역 분할','용접·도장·보온재 결함이 의심되는 영역을 픽셀 단위로 표시합니다.')]
# Inspections 1·2·3 are reachable from the GNB and the hero slides, so the quick links keep only the helpers.
SERVICES=[('book','실습 이용 가이드','guide',''),('list','판정 클래스 안내','classes','segmentation'),('chat','학습 도우미','chat','')]

def hero():
    from ui import icon
    slides=''.join(f'<div class="slide slide-{k}" role="group" aria-roledescription="슬라이드" aria-label="{i+1} / {len(SLIDES)}"'+(' hidden' if i else '')+f'><a class="slide-link" href="?inspection={k}"><span class="slide-art">{illustration(k)}<span class="beam" aria-hidden="true"></span></span><span class="slide-body"><span class="slide-num" aria-hidden="true">{n}</span><span class="slide-text"><strong>{n}. {t}</strong>{d}</span><span class="slide-go">검사 바로가기<span aria-hidden="true"> →</span></span></span></a></div>' for i,(k,n,t,d) in enumerate(SLIDES))
    return ('<section class="hero" aria-labelledby="hero-title"><div class="hero-copy"><p class="eyebrow">LNG QUALITY ACADEMY</p>'
      '<h1 id="hero-title">현장을 이해하는 첫걸음,<br><em>AI와 함께하는 품질검사</em></h1>'
      '<p class="hero-desc">직접 관찰하고, 검사하고, 비교하며 배우세요. <br>LNG 탱크 품질검사를 위한 신입직원 실습 공간입니다.</p>'
      '<div class="hero-actions"><a class="btn btn-primary" href="?inspection=classification">1번 검사부터 시작하기</a><button type="button" class="btn btn-line" data-guide="">이용 가이드 보기</button></div></div>'
      '<div class="hero-slider" role="region" aria-roledescription="캐러셀" aria-label="검사 종류 소개"><div class="slides" aria-live="off">'+slides+'</div>'
      '<div class="slider-ctrl"><button type="button" class="slide-prev" aria-label="이전 슬라이드">‹</button><span class="slide-count" aria-hidden="true"><b class="slide-current">1</b> / '+str(len(SLIDES))+'</span>'
      '<button type="button" class="slide-next" aria-label="다음 슬라이드">›</button></div></div></section>')

def services():
    from ui import icon, menu_link
    items=''.join('<li>'+(f'<a class="svc" href="{v}">' if k=='href' else f'<button type="button" class="svc" data-{k}="{v}">')+f'<span class="svc-icon">{icon(ic)}</span><span class="svc-label">{label}</span>'+('</a>' if k=='href' else '</button>')+'</li>' for ic,label,k,v in SERVICES)
    return '<section class="services" aria-labelledby="svc-title"><h2 id="svc-title" class="sr-only">자주 찾는 서비스</h2><ul class="svc-grid">'+items+'</ul></section>'

def render():
    shell(home='<main id="workspace" tabindex="-1" class="home-main">'+hero()+services()+'</main>')
