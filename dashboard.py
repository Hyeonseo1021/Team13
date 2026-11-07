"""LNG quality inspection dashboard backed by the documented API."""
import hashlib
import html
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import streamlit as st
from inspection import BASE, MODES, read_image, call_model, overlay

CSS = '''
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
:root{--ink:#142c40;--muted:#7a8b98;--teal:#008b7b}html,body,[class*="css"],h1,h2,h3,p,button,label{font-family:Pretendard,-apple-system,sans-serif!important}.stApp{background:#f5f7fa;color:var(--ink)}[data-testid="stHeader"]{background:transparent;height:0}[data-testid="stMainBlockContainer"]{max-width:1480px;padding:2.3rem 3.5rem 3rem}[data-testid="stSidebar"]{background:#122c3d;width:248px!important;min-width:248px!important}[data-testid="stSidebar"] *{color:#d8e5ec}[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:12px 9px;border-radius:9px;margin:3px 0}[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#214b59}[data-testid="stSidebar"] hr{border-color:#ffffff16}.side-brand{font-weight:800;font-size:27px;color:white;letter-spacing:-1px;margin-bottom:3px}.side-brand b{color:#52dbc0}.side-caption{font-size:11px;letter-spacing:2.2px;color:#87a6b6;margin-bottom:48px}.side-section{font-size:10px;color:#7393a4;letter-spacing:2px;margin-bottom:10px}.side-footer{padding:16px;background:#1b3a4b;border:1px solid #ffffff12;border-radius:12px;margin-top:70px}.side-footer strong{font-size:13px}.side-footer p{font-size:12px;color:#94aebb;margin:8px 0 0}.topline{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e1e7ed;padding-bottom:20px;margin-bottom:27px;font-size:12px;color:#82919e}.topline b{color:#294556;font-weight:600}.workspace{background:white;border:1px solid #e0e7ed;border-radius:7px;padding:7px 12px;color:#446071}.eyebrow{color:#008e7c;font-size:11px;letter-spacing:2px;font-weight:700;margin-bottom:9px}h1{font-size:32px!important;font-weight:750!important;letter-spacing:-1.2px;color:#183449;margin:0!important;padding:0!important}.subtitle{font-size:14px;color:#7c8b98;margin:10px 0 25px}.status{display:flex;gap:9px;align-items:center;font-size:12px;padding:10px 14px;background:#edf7f3;border:1px solid #d5ece3;border-radius:7px;color:#267b63}.status i{width:7px;height:7px;border-radius:50%;background:#2ab384}.status.off{background:#fff7e8;border-color:#f0e2c7;color:#90661d}.status.off i{background:#ca9c3c}.metric-card{background:white;border:1px solid #e2e8ee;border-radius:12px;padding:20px 22px;min-height:124px;box-shadow:0 3px 10px #233d5010}.metric-card .label{font-size:12px;color:#7c8d9b}.metric-card .value{font-size:28px;font-weight:750;letter-spacing:-.7px;margin-top:8px}.metric-card small{font-size:11px;color:#90a0ad;margin-left:8px;font-weight:400}.metric-card .mark{float:right;background:#eaf7f3;color:#009483;border-radius:8px;padding:7px 10px;font-size:16px}.section-title{font-size:17px;font-weight:700;margin:24px 0 13px;letter-spacing:-.4px}.section-title span{color:#a0adb7;font-size:11px;font-weight:400;margin-left:10px}.model-info{padding:13px 15px;border-radius:8px;background:#f0f7f8;color:#52727d;font-size:12px;line-height:1.8;margin:6px 0 12px}.empty{min-height:320px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:linear-gradient(150deg,#f7fbfc,#f2f7f9);border:1px dashed #d8e4ea;border-radius:10px;margin-top:8px;padding:30px}.empty-icon{font-size:36px;background:white;border:1px solid #e1ebee;border-radius:18px;width:76px;height:76px;display:grid;place-items:center;color:#54a297;margin-bottom:18px}.empty strong{font-size:16px;color:#3e5a6c}.empty p{font-size:12px;line-height:1.9;color:#94a3ad;margin-top:10px}.empty-steps{font-size:10px;letter-spacing:1px;color:#8da7b4;margin-top:25px}.footer-line{display:flex;justify-content:space-between;border-top:1px solid #e0e7ed;padding-top:17px;margin-top:24px;font-size:10px;color:#94a3ae}.result-label{font-size:23px;font-weight:750;color:#168a77}.tip{font-size:12px;line-height:1.8;color:#768c99;padding:13px 0} [data-testid="stVerticalBlock"]{gap:.65rem}[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#e2e8ee!important;background:white;border-radius:12px!important}[data-testid="stFileUploader"]{border-radius:9px}button[kind="primary"]{background:#008e7b!important;border-color:#008e7b!important;border-radius:8px!important}button[kind="secondary"]{border-color:#dde6eb!important;border-radius:8px!important}div[data-baseweb="select"]>div{border-color:#dfe7ed;background:#fbfcfd} [data-testid="stCaptionContainer"]{font-size:11px;color:#8a9ba8}.stButton button{font-size:13px}h3{font-size:17px!important}a{color:#008b7b} [data-testid="stSidebarNav"]{display:none} @media(max-width:850px){[data-testid="stMainBlockContainer"]{padding:1.5rem 1rem}.topline{margin-top:20px}h1{font-size:26px!important}.metric-card{padding:15px 12px}.metric-card .value{font-size:22px}.metric-card .mark{display:none}} 
'''

@st.cache_data(ttl=30,show_spinner=False)
def health():
    try:
        r=requests.get(BASE+'/health',timeout=(4,8))
        return r.status_code==200 and r.json().get('status')=='ready'
    except (requests.RequestException,ValueError,AttributeError):
        return False

def render(initial=None):
    st.html('<style>'+CSS+'</style>')
    history=st.session_state.setdefault('tank_history',[])
    with st.sidebar:
        st.html('<div class="side-brand">◈ tank<span style="font-weight:400">view</span><b>.</b></div><div class="side-caption">AI QUALITY INSPECTION</div><div class="side-section">WORKSPACE</div>')
        page=st.radio('메뉴',['품질 검사','검사 이력','API 가이드'],label_visibility='collapsed')
        st.divider()
        st.caption('연결된 서비스')
        st.markdown('**LNG Tank Inspection**')
        st.caption('SV-d4074093 · API v0.4.0')
        st.link_button('API 문서 ↗',BASE+'/docs',width='stretch')
        st.html('<div class="side-footer"><strong>검사의 시작부터, 더 정확하게.</strong><p>사진 한 장으로 확인하는<br>LNG 탱크 AI 품질 검사</p></div>')
    st.html('<div class="topline"><span>워크스페이스 &nbsp; / &nbsp; <b>'+page+'</b></span><span class="workspace">◈ &nbsp; LNG 탱크 품질관리</span></div>')
    if page=='검사 이력':
        st.title('검사 이력')
        st.caption('현재 세션에서 완료한 최근 30건입니다. 새 세션에서는 유지되지 않습니다. 원본 사진은 저장하지 않습니다.')
        if not history:
            st.info('아직 완료한 검사가 없습니다. 품질 검사 메뉴에서 첫 검사를 시작하세요.')
        else:
            st.dataframe([{'검사 시각 (KST)':x['time'],'파일명':x['file'],'검사 종류':MODES[x['mode']]['title'],'처리 시간':f"{x['seconds']:.1f}초"} for x in reversed(history)],hide_index=True,width='stretch')
            st.download_button('전체 결과 JSON 다운로드',json.dumps(history,ensure_ascii=False,indent=2),'tankview-history.json','application/json')
            if st.button('세션 이력 지우기'):
                st.session_state.tank_history=[];st.rerun()
        return
    if page=='API 가이드':
        st.title('API 가이드')
        st.caption('제공된 Swagger v0.4.0 명세에 연결되어 있습니다.')
        st.code(BASE,language=None)
        st.dataframe([{'메서드':'GET','경로':'/health','설명':'모델 준비 상태'}, {'메서드':'POST','경로':'/predict','설명':'세 모델을 순서대로 실행'}]+[{'메서드':'POST','경로':'/predict/'+k,'설명':v['title']+' · '+v['model']} for k,v in MODES.items()],hide_index=True,width='stretch')
        st.code("curl -X POST '"+BASE+"/predict/detection' -F 'file=@tank.jpg'",language='bash')
        st.info('JPEG/PNG 한 장 · 최대 10 MiB · 20,000,000픽셀. multipart/form-data의 file 필드로 전송합니다. 서버가 API를 호출하므로 브라우저 CORS 제한을 피합니다.')
        for cfg in MODES.values():
            with st.expander(cfg['title']+' · '+cfg['model']):
                st.write(cfg['lesson']);st.write('지원 클래스: '+', '.join(cfg['classes']))
        st.warning('모델별 점수는 서로 비교하지 않습니다. 전체 검사도 최종 양품·불량을 자동으로 종합 판정하지 않습니다. 점수 필터는 화면 표시용이며 검증된 판정 기준이 아닙니다.')
        st.link_button('Swagger 원문 보기 ↗',BASE+'/docs')
        return
    st.html('<div class="eyebrow">AI-POWERED INSPECTION</div>')
    a,b=st.columns([3,1])
    with a:
        st.title('품질의 차이를, 한눈에.')
        st.html('<div class="subtitle">LNG 탱크 이미지를 업로드하고 AI와 함께 품질을 확인하세요.</div>')
    with b:
        ready=health()
        st.html('<div class="status'+('' if ready else ' off')+'"><i></i>'+('검사 모델 준비 완료' if ready else '서비스 연결 확인 필요')+'</div>')
        if st.button('연결 새로고침',width='stretch'):
            health.clear();st.rerun()
    for col,label,value,unit,mark in zip(st.columns(3),['이번 세션 검사','사용 가능한 검사 모델','지원하는 검사 클래스'],[str(len(history)),'3','23'],['건 · 완료한 요청','종 · 검사 대상에 맞게 선택','개 · 모델별 클래스 합계'],['↗','◈','⌗']):
        with col:
            st.html(f'<div class="metric-card"><span class="mark">{mark}</span><div class="label">{label}</div><div class="value">{value}<small>{unit}</small></div></div>')
    left,right=st.columns([1,1.22],gap='large')
    with left:
        st.html('<div class="section-title">01 &nbsp; 검사 설정 <span>INSPECTION SETUP</span></div>')
        with st.container(border=True):
            keys=list(MODES)
            mode=st.selectbox('검사 모델',keys,index=keys.index(initial) if initial in keys else 0,format_func=lambda k:MODES[k]['title']+'  /  '+MODES[k]['model'])
            cfg=MODES[mode]
            st.html('<div class="model-info"><b>'+cfg['target']+'</b><br>'+cfg['explain']+'</div>')
            file=st.file_uploader('검사 이미지',type=['jpg','jpeg','png'],help='JPEG 또는 PNG · 최대 10 MiB · 20,000,000픽셀',key='tank_upload')
            image=None;data=None;sig=None;mime=None
            if file:
                try:
                    data=file.getvalue();image,mime=read_image(data,mode);sig=mode+hashlib.sha256(data).hexdigest()
                    st.image(image,width='stretch')
                    st.caption(f'{image.width:,} × {image.height:,} px · {len(data)/1024/1024:.2f} MiB')
                except ValueError as e: st.error(str(e))
            else: st.caption('JPEG, PNG · 최대 10 MiB · 한 번에 한 장')
            st.caption('검사 시작 시 사진을 지정된 검사 API로 전송합니다.')
            if st.button('AI 검사 시작  →',type='primary',disabled=image is None,width='stretch'):
                st.session_state.pop('tank_result',None)
                with st.spinner('이미지 분석 중입니다. 서버 대기와 추론이 완료될 때까지 기다려 주세요…'):
                    start=time.monotonic()
                    try:
                        body=call_model(mode,data,mime)
                        item={'time':datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S'),'file':file.name,'mode':mode,'seconds':time.monotonic()-start,'body':body}
                        st.session_state.tank_history=(history+[item])[-30:]
                        st.session_state.tank_result={'sig':sig,**item}
                        st.rerun()
                    except ValueError as e: st.error(str(e))
        with st.expander('이 모델로 무엇을 검사할 수 있나요?'):
            st.write(cfg['lesson']);st.write('지원 클래스: '+', '.join(cfg['classes']))
    with right:
        st.html('<div class="section-title">02 &nbsp; 분석 결과 <span>INSPECTION RESULTS</span></div>')
        with st.container(border=True):
            saved=st.session_state.get('tank_result')
            if not saved or sig is None or saved['sig']!=sig:
                st.html('<div class="empty"><div class="empty-icon">⌗</div><strong>새로운 검사를 시작해 보세요</strong><p>검사 목적에 맞는 모델을 선택하고<br>이미지를 업로드하면 분석 결과가 여기에 표시됩니다.</p><div class="empty-steps">모델 선택 &nbsp; ─ &nbsp; 이미지 업로드 &nbsp; ─ &nbsp; AI 분석</div></div>')
            else:
                part=saved['body'][mode]
                st.caption(f"검사 완료 · {saved['time']} KST · {saved['seconds']:.1f}초")
                if mode=='classification':
                    st.html('<div class="result-label">'+html.escape(part['class']['name'])+'</div>')
                    st.metric('모델 점수',f"{part['score']*100:.1f}%")
                    for name,score in zip(cfg['classes'],part['probabilities']):
                        st.write(name+'  ·  '+f'{score*100:.1f}%');st.progress(float(score))
                    st.caption('분류에는 ‘해당 없음’이 없습니다. 높은 점수가 정답이나 대상 적합성을 보장하지 않습니다.')
                else:
                    items=part['detections' if mode=='detection' else 'instances']
                    threshold=st.slider('최소 표시 점수',0.,1.,.5,.05,key='tank_threshold_'+mode)
                    chosen=st.multiselect('표시할 클래스',sorted({x['class']['name'] for x in items}),placeholder='모든 클래스')
                    visible=[x for x in items if x['score']>=threshold and (not chosen or x['class']['name'] in chosen)]
                    st.caption(f'전체 후보 {len(items)}개 · 표시 {len(visible)}개. 점수 필터는 표시용이며 합격 기준이 아닙니다.')
                    if visible:
                        selected=0;target=visible
                        if mode=='segmentation':
                            selected=st.selectbox('확인할 분할 후보',range(len(visible)),format_func=lambda i:f"#{i+1} {visible[i]['class']['name']} · {visible[i]['score']*100:.1f}%")
                            target=[visible[selected]]
                        try:
                            st.image(overlay(image,target,mode=='segmentation',[selected+1] if mode=='segmentation' else None),width='stretch')
                        except (ValueError,TypeError,OverflowError) as e: st.error('오버레이 생성 실패: '+str(e))
                        st.dataframe([{'번호':i+1,'클래스':x['class']['name'],'점수':f"{x['score']*100:.1f}%",'원본 좌표':str(x['bbox_xyxy'])} for i,x in enumerate(visible)],hide_index=True,width='stretch')
                    else: st.info('표시 조건에 맞는 후보가 없습니다. 검출이 없다고 전체 양품을 의미하지는 않습니다.')
                    if mode=='segmentation': st.caption('후보에는 중복과 낮은 점수가 포함될 수 있습니다. 후보 수는 실제 불량 개수가 아닙니다.')
                st.download_button('결과 JSON 다운로드 ↓',json.dumps(saved['body'],ensure_ascii=False,indent=2),'tankview-'+mode+'.json','application/json',width='stretch')
                with st.expander('API 원본 응답'): st.json(saved['body'],expanded=False)
        st.html('<div class="tip">ⓘ &nbsp; 모델의 분석은 품질 검토를 돕는 참고 자료입니다.<br>&nbsp;&nbsp;&nbsp;&nbsp; 최종 판정은 검사 기준과 원본 이미지를 함께 확인하세요.</div>')
    st.html('<div class="footer-line"><span>tankview. &nbsp; AI 기반 LNG 탱크 품질 검사</span><span>Powered by ViT · EfficientDet · MaskDINO</span></div>')
