"""Shared, trusted-document renderer and visual shell for every page."""
from pathlib import Path
import html,json,re
import streamlit as st
ROOT=Path(__file__).parent

def render_html(markup, script=''):
    def encoded(value):
        return json.dumps(value,ensure_ascii=True).replace('<',r'\u003c').replace('>',r'\u003e').replace('&',r'\u0026')
    # Render only developer-owned markup. User data must be escaped or use textContent.
    code='''<div data-t13-mount></div><script>(()=>{const host=document.currentScript.parentElement;const mount=host.querySelector('[data-t13-mount]');mount.innerHTML=MARKUP;const behavior=document.createElement('script');behavior.textContent=BEHAVIOR;mount.appendChild(behavior)})();</script>'''
    st.html(code.replace('MARKUP',encoded(markup)).replace('BEHAVIOR',encoded(script)),unsafe_allow_javascript=True)

ICONS={'user':'<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>','chat':'<path d="M21 4H3v14h5l4 4v-4h9ZM7 9h10M7 13h6"/>','menu':'<path d="M4 6h16M4 12h16M4 18h16"/>','arrow':'<path d="M12 20V4m-7 7 7-7 7 7"/>',
 'search':'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>','close':'<path d="M6 6l12 12M18 6 6 18"/>','chev':'<path d="m6 9 6 6 6-6"/>',
 'tank':'<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v11c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 11.5c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
 'bolt':'<path d="m12 3 7.8 4.5v9L12 21l-7.8-4.5v-9Z"/><circle cx="12" cy="12" r="3"/>',
 'mask':'<path d="M4 4h16v16H4Z"/><path d="m8 15 3-4 2 2 3-5"/><path d="M7 4v16M17 4v16" opacity=".4"/>',
 'book':'<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Z"/><path d="M4 19V5M9 8h6M9 11h4"/>',
 'list':'<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
 'building':'<path d="M4 21V5l8-2v18M12 8h8v13M8 8h.01M8 12h.01M8 16h.01M16 12h.01M16 16h.01M2 21h20"/>'}

def icon(name='chat'):
    return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+ICONS[name]+'</svg>'

SITE_TITLE='LNG 탱크 품질 검사 교육 플랫폼'
# Site-title emblem: the team's '1B' logo, recoloured light (assets/brand/team-logo-light.png, transparent; background cut at
# brightness 250 so the silver highlights stay solid) on the
# blue gradient tile (.st-emblem in site.css); inlined so it needs no static route.
def _emblem():
    import base64
    data=base64.b64encode((ROOT/'assets/brand/team-logo-light.png').read_bytes()).decode('ascii')
    return f'<span class="st-emblem" aria-hidden="true"><img src="data:image/png;base64,{data}" alt="" width="360" height="216"></span>'
EMBLEM=_emblem()
MODE_NAV=[('classification','1','표면 상태 분류'),('detection','2','볼트·케이블 탐지'),('segmentation','3','결함 영역 분할')]

# (id, title, description, items). item = (label, sub, kind, value): kind 'href' or an action name handled in site.js.
MENU=[
 ('inspect','검사 실습','검사 대상에 맞는 모델을 골라 사진을 관찰하고 결과를 비교합니다.',[
   ('1. 표면 상태 분류','ViT · 탱크 클리닝·폼스프레이','href','?inspection=classification'),
   ('2. 볼트·케이블 탐지','EfficientDet · 체결·설치 상태','href','?inspection=detection'),
   ('3. 결함 영역 분할','MaskDINO · 용접·표면 결함','href','?inspection=segmentation'),
   ('검사 종류 한눈에 보기','홈 화면으로 이동','href','?')]),
 ('exam','역량평가','실습이 아닌 평가로 혼자 힘으로 판정 능력을 확인합니다.',[
   ('수행능력 평가','검사 3종 · 15문항 · 80점 합격','href','?page=exam'),
   ('내 시험 기록','점수·합격 여부 다시 보기','href','?page=my&view=exams')]),
 ('judge','판정 검토','역량평가에 합격한 검사자가 AI 판정을 승인·거절하며 기록합니다.',[
   ('1. 표면 상태 분류 검토','AI 판정 승인·거절','href','?page=judge&inspection=classification'),
   ('2. 볼트·케이블 탐지 검토','AI 판정 승인·거절','href','?page=judge&inspection=detection'),
   ('3. 결함 영역 분할 검토','AI 판정 승인·거절','href','?page=judge&inspection=segmentation'),
   ('내 검토 기록','기록·사진 다시 보기, 시험 문제 신청','href','?page=my&view=records')]),
 ('guide','학습 가이드','처음 실습하는 신입직원을 위한 단계별 안내입니다.',[
   ('실습 이용 가이드','검사 선택부터 기록 확인까지','href','?page=guide'),
   ('판정 클래스','검사 3종 · 탭으로 골라 보기','href','?page=classes'),
   ('사진 준비 방법','형식·크기·촬영 대상 확인','href','?page=guide&topic=photo'),
   ('결과 해석 방법','점수·사각형·마스크 읽는 법','href','?page=guide&topic=result'),
   ('LNG_NI 챗봇','궁금한 점 바로 묻기','chat','')]),
 ('my','마이페이지','내 학습 현황과 검토 기록을 한곳에서 확인합니다.',[
   ('내 학습 현황','검토 건수·승인/거절 비율','href','?page=my'),
   ('내 검토 기록','기록·사진 다시 보기, CSV 내려받기','href','?page=my&view=records'),
   ('로그인 / 회원가입','검토 기록 저장','href','?page=login'),
   ('개인정보 및 데이터 안내','사진·대화 처리 방식','href','?page=privacy')])]

def brand(text):
    """Show the chatbot name LNG_NI in italics wherever it appears in visible HTML."""
    return text.replace('LNG_NI','<i class="t13-brand">LNG_NI</i>')

def menu_link(label,sub,kind,value,cls=''):
    sub_html=f'<small>{sub}</small>' if sub else ''
    if kind=='href':return f'<a class="{cls}" href="{value}"><span>{brand(label)}</span>{sub_html}</a>'
    return f'<button type="button" class="{cls}" data-{kind}="{value}"><span>{brand(label)}</span>{sub_html}</button>'

def menu(no_chat=False):
    """MENU, minus the assistant entries on pages without the assistant (home)."""
    return [(m,t,d,[l for l in links if not (no_chat and l[2]=='chat')]) for m,t,d,links in MENU]

def gnb(active=None,no_chat=False):
    items=''
    for mid,title,desc,links in menu(no_chat):
        cur=' is-current' if ((mid=='inspect' and active and active not in ('my','classes','guide','exam','judge')) or (mid==active)) else ''
        items+=(f'<li class="gnb-item{cur}"><button type="button" class="gnb-btn" id="gnb-{mid}" aria-expanded="false" aria-controls="mega-{mid}">{title}'+icon('chev')+'</button>'
                f'<div class="mega" id="mega-{mid}" role="region" aria-labelledby="gnb-{mid}"><div class="mega-inner">'
                '<ul class="mega-links">'+''.join('<li>'+menu_link(*l,cls='mega-link')+'</li>' for l in links)+'</ul></div></div></li>')
    return '<nav class="gnb" aria-label="주 메뉴"><ul class="gnb-list">'+items+'</ul></nav>'

def allmenu(no_chat=False):
    cols=''.join(f'<section class="allmenu-group" aria-labelledby="all-{mid}"><h3 id="all-{mid}">{title}</h3><ul>'+''.join('<li>'+menu_link(*l,cls='allmenu-link')+'</li>' for l in links)+'</ul></section>' for mid,title,desc,links in menu(no_chat))
    return ('<dialog class="allmenu" id="t13-allmenu" aria-labelledby="allmenu-title"><div class="allmenu-head"><h2 id="allmenu-title">전체메뉴</h2>'
            '<button type="button" class="allmenu-close" data-allmenu-close aria-label="전체메뉴 닫기">'+icon('close')+'</button></div><div class="allmenu-body">'+cols+'</div></dialog>')

def wordmark(cls):
    """'BEST TEAM' wordmark image (assets/brand/best-team.webp, transparent; inlined so it needs no static route)."""
    import base64
    data=base64.b64encode((ROOT/'assets/brand/best-team.webp').read_bytes()).decode('ascii')
    return f'<img class="{cls}" src="data:image/webp;base64,{data}" alt="BEST TEAM" width="1237" height="160">'

def logo_mark():
    """Site logo: the team13 '13' mark in a white circle (assets/brand/icon-96.png, inlined so it needs no static route)."""
    import base64
    data=base64.b64encode((ROOT/'assets/brand/icon-96.png').read_bytes()).decode('ascii')
    return f'<img class="logo-mark" src="data:image/png;base64,{data}" alt="" width="48" height="48">'

def account_html():
    from accounts import current_user  # lazy: keeps ui importable without the database
    from urllib.parse import urlencode
    user=current_user()
    if user:
        return f'<span class="hd-user" title="{html.escape(user["name"])} 님">'+icon('user')+f'<span>{html.escape(user["name"])}</span></span><button type="button" class="account-btn" data-logout="">로그아웃</button><a class="hd-me on" href="?page=login" aria-label="{html.escape(user["name"])} 님 계정 (로그아웃)">'+icon('user')+'</a>'
    here={k:v for k,v in st.query_params.to_dict().items() if k in ('inspection','task')}
    nxt='?'+urlencode(here) if here else '?'
    login=f'?{html.escape(urlencode({"page":"login","next":nxt}))}'
    return f'<a class="account-btn" href="{login}">로그인</a><a class="hd-me" href="{login}" aria-label="로그인">'+icon('user')+'</a>'

def header(mode=None,home=False,no_chat=None,current=None):
    """Site title (left, links home) | account, then the menu bar with the search box at its right end.
    On phones (no menu bar) the search sits under the title: open on home, behind the search icon elsewhere."""
    no_chat=home if no_chat is None else no_chat
    return ('<a class="skip" href="#workspace">본문 바로가기</a><header class="site-header'+(' is-home' if home else '')+'">'
      '<div class="hd-top"><p class="site-title"><a href="?" aria-label="'+SITE_TITLE+' 홈으로 이동">'+EMBLEM+'<span class="st-text"><span class="st-main"><b class="st-lng">LNG</b> 탱크 품질 검사</span> <span class="st-sub nowrap">교육 플랫폼</span></span></a></p>'
      '<div class="hd-util"><button type="button" class="search-toggle" aria-expanded="false" aria-controls="t13-search" aria-label="통합검색 열기">'+icon('search')+'</button>'+account_html()+
      '<button type="button" class="allmenu-btn" data-allmenu aria-haspopup="dialog" aria-controls="t13-allmenu">'+icon('menu')+'<span>전체메뉴</span></button></div></div>'
      +'<div class="hd-nav">'+gnb(current or mode,no_chat=no_chat)+'<div class="hd-search-row">'
      '<form class="hd-search" id="t13-search" role="search" autocomplete="off"><label class="sr-only" for="t13-q">통합검색</label>'
      '<input id="t13-q" type="search" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="t13-search-list" placeholder="검사 종류, 결함 클래스, 가이드 검색" maxlength="40">'
      '<button type="submit" class="hd-search-btn" aria-label="검색">'+icon('search')+'</button>'
      '<ul class="search-list" id="t13-search-list" role="listbox" aria-label="검색 결과" hidden></ul></form>'
      '</div></div></header>'+allmenu(no_chat=no_chat))

def search_index(no_chat=False):
    """Client-side integrated search entries: pages, guide topics and every judgement class."""
    from inspection import MODES  # lazy: inspection imports ui
    out=[]
    for mid,title,desc,links in menu(no_chat):
        for label,sub,kind,value in links:out.append({'t':label,'s':title+' · '+sub,'k':kind,'v':value,'q':' '.join([label,sub,title])})
    for key,cfg in MODES.items():
        out.append({'t':f"{cfg['number']}. {cfg['title']} 검사",'s':cfg['model']+' · '+cfg['target'],'k':'href','v':'?inspection='+key,'q':' '.join([cfg['title'],cfg['model'],cfg['target'],cfg['explain']])})
        for c in cfg['classes']:out.append({'t':c,'s':f"{cfg['number']}. {cfg['title']} 판정 클래스",'k':'href','v':'?inspection='+key,'q':c+' '+cfg['title']})
    return out

def class_lists():
    from inspection import MODES
    return {k:{'title':f"{c['number']}. {c['title']}",'model':c['model'],'classes':c['classes']} for k,c in MODES.items()}

def chat_markup(no_chat=False):
    return '''<div class="t13 t13-chat-root'''+(' no-chat' if no_chat else '')+'''" id="t13-chat-root"><button class="chat-launcher" id="chat-launcher" aria-controls="chat-panel" aria-expanded="false" aria-label="LNG_NI 대화창 열기">'''+icon()+'''<span class="chat-launcher-label"><i class="t13-brand">LNG_NI</i></span></button><aside class="chat-panel" id="chat-panel" role="dialog" aria-modal="false" aria-labelledby="chat-title" hidden><div class="chat-head"><span class="chat-avatar">'''+icon()+'''</span><div><h2 id="chat-title"><i class="t13-brand">LNG_NI</i></h2><p id="chat-context-label">검사 선택부터 결과 이해까지</p></div><div class="chat-actions"><button id="chat-reset" aria-label="새 대화 시작">↻</button><button id="chat-close" aria-label="대화창 닫기">×</button></div></div><p class="chat-disclaimer">AI 답변은 틀릴 수 있습니다 · 실제 판정은 검사 기준과 담당자 검토가 필요합니다</p><div class="chat-log" id="chat-log" role="log" aria-live="polite" aria-relevant="additions" aria-label="대화 내역" tabindex="0"></div><div class="chat-bottom"><div class="chat-prompts"><button data-prompt="검사 종류를 알려주세요">검사 선택</button><button data-prompt="사진을 어떻게 준비하나요?">사진 준비</button><button data-prompt="검사 결과를 어떻게 이해하나요?">결과 이해</button></div><form class="chat-compose" id="chat-form"><label class="sr-only" for="chat-input">질문 입력</label><textarea id="chat-input" rows="2" maxlength="1000" placeholder="궁금한 내용을 물어보세요"></textarea><button id="chat-send" type="submit" aria-label="메시지 보내기" disabled>'''+icon('arrow')+'''</button></form></div></aside><dialog id="site-dialog" aria-labelledby="site-dialog-title"><div class="dialog-top"><h2 id="site-dialog-title"></h2><button id="dialog-close" aria-label="닫기">×</button></div><div class="dialog-copy" id="site-dialog-copy"></div></dialog></div>'''

def footer():
    return '<footer class="footer"><strong>'+wordmark('footer-logo')+'</strong><p>© 2026 team13 · LNG 탱크 품질검사 신입교육</p><div class="footer-links"><a href="?page=privacy">개인정보 및 데이터 안내</a><button type="button" data-company="">기업교육 문의</button><a href="?page=guide">이용 가이드</a></div></footer>'

def styles():
    return '<style>'+(ROOT/'assets/site.css').read_text()+'</style>'

def shell(mode=None,home=None,is_home=False,no_chat=None,current=None):
    """Header + shared assistant. Home/login pass their body; inspection pages add native widgets after it.
    is_home: the main home page, which shows the search open under the menu.
    no_chat: hide the learning assistant (default: on home). The login page passes True as well."""
    no_chat=is_home if no_chat is None else no_chat
    content=styles()+'<div class="t13" id="t13-shell">'+header(mode,home=is_home,no_chat=no_chat,current=current)
    if home is not None:content+=home+footer()
    content+='</div>'+chat_markup(no_chat=no_chat)
    base=st.config.get_option('server.baseUrlPath').strip('/')
    chat_api=('/'+base if base else '')+'/api/t13'
    import accounts
    import knowledge
    user = accounts.current_user()
    chat_scope = knowledge.scope(user['id'] if user else None)
    script='(()=>{const T13_CONTEXT='+json.dumps({'mode':mode,'noChat':no_chat,'search':search_index(no_chat=no_chat),'classes':class_lists(),'chatApi':chat_api,'chatScope':chat_scope},ensure_ascii=True)+';\n'+(ROOT/'assets/site.js').read_text()+'})();'
    render_html(content,script)
    if mode is None:publish_chat_context(None)

def fragment(markup):render_html('<div class="t13">'+markup+'</div>')

def publish_chat_context(context):
    """Hand the current inspection situation to the assistant panel. It is sent with each question as
    <inspection_context>; pass only what the learner may see (answer labels only after they are revealed)."""
    data=json.dumps(context,ensure_ascii=True).replace('<',r'\u003c')
    render_html('<span hidden></span>','window.T13_INSPECTION_CONTEXT='+data+';')
