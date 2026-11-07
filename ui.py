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

ICONS={'chat':'<path d="M21 4H3v14h5l4 4v-4h9ZM7 9h10M7 13h6"/>','menu':'<path d="M4 6h16M4 12h16M4 18h16"/>','arrow':'<path d="M12 20V4m-7 7 7-7 7 7"/>',
 'search':'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>','close':'<path d="M6 6l12 12M18 6 6 18"/>','chev':'<path d="m6 9 6 6 6-6"/>',
 'tank':'<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v11c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 11.5c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
 'bolt':'<path d="m12 3 7.8 4.5v9L12 21l-7.8-4.5v-9Z"/><circle cx="12" cy="12" r="3"/>',
 'mask':'<path d="M4 4h16v16H4Z"/><path d="m8 15 3-4 2 2 3-5"/><path d="M7 4v16M17 4v16" opacity=".4"/>',
 'book':'<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Z"/><path d="M4 19V5M9 8h6M9 11h4"/>',
 'list':'<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
 'building':'<path d="M4 21V5l8-2v18M12 8h8v13M8 8h.01M8 12h.01M8 16h.01M16 12h.01M16 16h.01M2 21h20"/>'}

def icon(name='chat'):
    return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+ICONS[name]+'</svg>'

MODE_NAV=[('classification','1','표면 상태 분류'),('detection','2','볼트·케이블 탐지'),('segmentation','3','결함 영역 분할')]

# (id, title, description, items). item = (label, sub, kind, value): kind 'href' or an action name handled in site.js.
MENU=[
 ('inspect','검사 실습','검사 대상에 맞는 모델을 골라 사진을 관찰하고 결과를 비교합니다.',[
   ('1. 표면 상태 분류','ViT · 탱크 클리닝·폼스프레이','href','?inspection=classification'),
   ('2. 볼트·케이블 탐지','EfficientDet · 체결·설치 상태','href','?inspection=detection'),
   ('3. 결함 영역 분할','MaskDINO · 용접·표면 결함','href','?inspection=segmentation'),
   ('검사 종류 한눈에 보기','홈 화면으로 이동','href','?')]),
 ('guide','학습 가이드','처음 실습하는 신입직원을 위한 단계별 안내입니다.',[
   ('실습 이용 가이드','검사 선택부터 결과 비교까지','guide',''),
   ('사진 준비 방법','형식·크기·촬영 대상 확인','topic','photo'),
   ('결과 해석 방법','점수·사각형·마스크 읽는 법','topic','result'),
   ('학습 도우미 챗봇','궁금한 점 바로 묻기','chat','')]),
 ('classes','판정 클래스','검사별로 모델이 구분하는 판정 종류를 확인합니다.',[
   ('표면 상태 분류 클래스','4개 클래스','classes','classification'),
   ('볼트·케이블 탐지 클래스','4개 클래스','classes','detection'),
   ('결함 영역 분할 클래스','15개 클래스','classes','segmentation')]),
 ('company','기업교육','기업 신입교육 운영과 데이터 처리 안내입니다.',[
   ('기업교육 안내','교육 목적과 운영 방식','company',''),
   ('기업 계정 체험','시연용 계정','account',''),
   ('개인정보 및 데이터 안내','사진·대화 처리 방식','privacy','')])]

def menu_link(label,sub,kind,value,cls=''):
    sub_html=f'<small>{sub}</small>' if sub else ''
    if kind=='href':return f'<a class="{cls}" href="{value}"><span>{label}</span>{sub_html}</a>'
    return f'<button type="button" class="{cls}" data-{kind}="{value}"><span>{label}</span>{sub_html}</button>'

def gnb(active=None):
    items=''
    for mid,title,desc,links in MENU:
        cur=' is-current' if (mid=='inspect' and active) else ''
        items+=(f'<li class="gnb-item{cur}"><button type="button" class="gnb-btn" id="gnb-{mid}" aria-expanded="false" aria-controls="mega-{mid}">{title}'+icon('chev')+'</button>'
                f'<div class="mega" id="mega-{mid}" role="region" aria-labelledby="gnb-{mid}"><div class="mega-inner"><div class="mega-intro"><strong>{title}</strong><p>{desc}</p></div>'
                '<ul class="mega-links">'+''.join('<li>'+menu_link(*l,cls='mega-link')+'</li>' for l in links)+'</ul></div></div></li>')
    return '<nav class="gnb" aria-label="주 메뉴"><ul class="gnb-list">'+items+'</ul></nav>'

def allmenu():
    cols=''.join(f'<section class="allmenu-group" aria-labelledby="all-{mid}"><h3 id="all-{mid}">{title}</h3><ul>'+''.join('<li>'+menu_link(*l,cls='allmenu-link')+'</li>' for l in links)+'</ul></section>' for mid,title,desc,links in MENU)
    return ('<dialog class="allmenu" id="t13-allmenu" aria-labelledby="allmenu-title"><div class="allmenu-head"><h2 id="allmenu-title">전체메뉴</h2>'
            '<button type="button" class="allmenu-close" data-allmenu-close aria-label="전체메뉴 닫기">'+icon('close')+'</button></div><div class="allmenu-body">'+cols+'</div></dialog>')

def logo_mark():
    """Site logo: the team13 '13' mark in a white circle (assets/brand/icon-96.png, inlined so it needs no static route)."""
    import base64
    data=base64.b64encode((ROOT/'assets/brand/icon-96.png').read_bytes()).decode('ascii')
    return f'<img class="logo-mark" src="data:image/png;base64,{data}" alt="" width="48" height="48">'

def header(mode=None):
    return ('<a class="skip" href="#workspace">본문 바로가기</a><header class="site-header">'
      '<div class="hd-top"><a class="logo" href="?">'+logo_mark()+'<span><span class="logo-name">team13</span><span class="logo-note">LNG 품질검사 아카데미</span></span><span class="sr-only">홈으로 이동</span></a>'
      '<form class="hd-search" id="t13-search" role="search" autocomplete="off"><label class="sr-only" for="t13-q">통합검색</label>'
      '<input id="t13-q" type="search" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="t13-search-list" placeholder="검사 종류, 결함 클래스, 가이드 검색" maxlength="40">'
      '<button type="submit" class="hd-search-btn" aria-label="검색">'+icon('search')+'</button>'
      '<ul class="search-list" id="t13-search-list" role="listbox" aria-label="검색 결과" hidden></ul></form>'
      '<div class="hd-util"><button type="button" class="search-toggle" aria-expanded="false" aria-controls="t13-search" aria-label="통합검색 열기">'+icon('search')+'</button><button type="button" class="account-btn" data-account="">기업 계정</button>'
      '<button type="button" class="allmenu-btn" data-allmenu aria-haspopup="dialog" aria-controls="t13-allmenu">'+icon('menu')+'<span>전체메뉴</span></button></div></div>'
      +gnb(mode)+'</header>'+allmenu())

def search_index():
    """Client-side integrated search entries: pages, guide topics and every judgement class."""
    from inspection import MODES  # lazy: inspection imports ui
    out=[]
    for mid,title,desc,links in MENU:
        for label,sub,kind,value in links:out.append({'t':label,'s':title+' · '+sub,'k':kind,'v':value,'q':' '.join([label,sub,title])})
    for key,cfg in MODES.items():
        out.append({'t':f"{cfg['number']}. {cfg['title']} 검사",'s':cfg['model']+' · '+cfg['target'],'k':'href','v':'?inspection='+key,'q':' '.join([cfg['title'],cfg['model'],cfg['target'],cfg['explain']])})
        for c in cfg['classes']:out.append({'t':c,'s':f"{cfg['number']}. {cfg['title']} 판정 클래스",'k':'href','v':'?inspection='+key,'q':c+' '+cfg['title']})
    return out

def class_lists():
    from inspection import MODES
    return {k:{'title':f"{c['number']}. {c['title']}",'model':c['model'],'classes':c['classes']} for k,c in MODES.items()}

def chat_markup():
    return '''<div class="t13 t13-chat-root" id="t13-chat-root"><button class="chat-launcher" id="chat-launcher" aria-controls="chat-panel" aria-expanded="false" aria-label="학습 도우미 대화창 열기">'''+icon()+'''<span class="chat-launcher-label">학습 도우미</span></button><aside class="chat-panel" id="chat-panel" role="dialog" aria-modal="false" aria-labelledby="chat-title" hidden><div class="chat-head"><span class="chat-avatar">'''+icon()+'''</span><div><h2 id="chat-title">team13 학습 도우미</h2><p id="chat-context-label">검사 선택부터 결과 이해까지</p></div><div class="chat-actions"><button id="chat-reset" aria-label="새 대화 시작">↻</button><button id="chat-close" aria-label="대화창 닫기">×</button></div></div><p class="chat-disclaimer">AI 답변은 틀릴 수 있습니다 · 실제 판정은 검사 기준과 담당자 검토가 필요합니다</p><div class="chat-log" id="chat-log" role="log" aria-live="polite" aria-relevant="additions" aria-label="대화 내역" tabindex="0"></div><div class="chat-bottom"><div class="chat-prompts"><button data-prompt="검사 종류를 알려주세요">검사 선택</button><button data-prompt="사진을 어떻게 준비하나요?">사진 준비</button><button data-prompt="검사 결과를 어떻게 이해하나요?">결과 이해</button></div><form class="chat-compose" id="chat-form"><label class="sr-only" for="chat-input">질문 입력</label><textarea id="chat-input" rows="2" maxlength="1000" placeholder="궁금한 내용을 물어보세요"></textarea><button id="chat-send" type="submit" aria-label="메시지 보내기" disabled>'''+icon('arrow')+'''</button></form><p class="chat-hint">Enter 전송 · Shift+Enter 줄바꿈 · 질문과 답변은 챗봇 서버에 기록될 수 있습니다.</p></div></aside><dialog id="site-dialog" aria-labelledby="site-dialog-title"><div class="dialog-top"><h2 id="site-dialog-title"></h2><button id="dialog-close" aria-label="닫기">×</button></div><div class="dialog-copy" id="site-dialog-copy"></div></dialog></div>'''

def footer():
    return '<footer class="footer"><strong>team13</strong><p>© 2026 team13 · LNG 탱크 품질검사 신입교육</p><div class="footer-links"><button type="button" data-privacy="">개인정보 및 데이터 안내</button><button type="button" data-company="">기업교육 문의</button><button type="button" data-guide="">이용 가이드</button></div></footer>'

def styles():
    return '<style>'+(ROOT/'assets/site.css').read_text()+'</style>'

def shell(mode=None,home=None):
    """Header + shared assistant. Home passes its body; inspection pages add native widgets after it."""
    content=styles()+'<div class="t13" id="t13-shell">'+header(mode)
    if home is not None:content+=home+footer()
    content+='</div>'+chat_markup()
    base=st.config.get_option('server.baseUrlPath').strip('/')
    chat_api=('/'+base if base else '')+'/api/t13'
    script='(()=>{const T13_CONTEXT='+json.dumps({'mode':mode,'search':search_index(),'classes':class_lists(),'chatApi':chat_api},ensure_ascii=True)+';\n'+(ROOT/'assets/site.js').read_text()+'})();'
    render_html(content,script)
    if mode is None:publish_chat_context(None)

def fragment(markup):render_html('<div class="t13">'+markup+'</div>')

def publish_chat_context(context):
    """Hand the current inspection situation to the assistant panel. It is sent with each question as
    <inspection_context>; pass only what the learner may see (answer labels only after they are revealed)."""
    data=json.dumps(context,ensure_ascii=True).replace('<',r'\u003c')
    render_html('<span hidden></span>','window.T13_INSPECTION_CONTEXT='+data+';')
