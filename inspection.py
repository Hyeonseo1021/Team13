"""Server-side LNG inspection learning workspace. Uploaded files are not persisted."""
import hashlib
import html
import csv
import io
import json
import os
import math
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import requests
from PIL import Image, ImageOps, ImageDraw
from pycocotools import mask as mask_utils
import streamlit as st
from ui import shell, fragment, footer, render_html, publish_chat_context

BASE = 'https://aiopen-serving.jntp-ax.or.kr/jntp-gpu/SV-d4074093'
MODES = {
 'classification': {'number':'1','title':'표면 상태 분류','model':'ViT','target':'탱크 클리닝 · 폼스프레이 상태','classes':['탱크클리닝불량','표면양품','폼스프레이불량','폼스프레이양품'],'explain':'이미지 전체를 4개 클래스 중 하나로 분류합니다.','lesson':'사진 전체의 클리닝 또는 폼스프레이 상태를 먼저 관찰하세요. 이 모델에는 “해당 없음”이 없어 무관한 사진도 4개 중 하나로 분류됩니다.'},
 'detection': {'number':'2','title':'볼트·케이블 탐지','model':'EfficientDet','target':'볼트 체결 · 케이블 설치 상태','classes':['볼트체결불량','볼트체결양품','케이블설치불량','케이블설치양품'],'explain':'발견한 객체의 클래스·점수·사각형 위치를 확인합니다.','lesson':'볼트 체결 부위와 케이블 설치 위치를 먼저 찾아보세요. 객체가 검출되지 않았다는 사실만으로 사진 전체를 양품으로 판정할 수 없습니다.'},
 'segmentation': {'number':'3','title':'결함 영역 분할','model':'MaskDINO','target':'용접 · 표면 · 보온재 · 케이블 · 바인딩 · 절단','classes':['용접불량','용접양품','용접블로우홀','균열','도장흐름','도막떨어짐','도막분리','스크래치','보온재손상','케이블손상','케이블양품','바인딩불량','바인딩양품','절단불량','절단양품'],'explain':'후보별 클래스·점수·사각형·픽셀 마스크를 확인합니다.','lesson':'결함이 의심되는 위치와 범위를 먼저 예상해 보세요. 분할 후보는 겹치거나 낮은 점수를 포함할 수 있으며 후보 수는 실제 불량 개수가 아닙니다.'},
}
MAX_BYTES=10*1024*1024
MAX_PIXELS=20_000_000

def read_image(data, mode):
    if not data or len(data)>MAX_BYTES:
        raise ValueError('JPEG/PNG 사진 한 장을 10 MiB 이하로 업로드해 주세요.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image=Image.open(io.BytesIO(data))
            # MPO = phone-camera JPEG with an extra embedded frame; it is a valid JPEG file.
            if image.format not in ('JPEG','MPO','PNG'): raise ValueError('JPEG 또는 PNG만 지원합니다.')
            mime='image/png' if image.format=='PNG' else 'image/jpeg'
            if image.width*image.height>MAX_PIXELS: raise ValueError('사진 해상도는 가로×세로 20,000,000픽셀 이하여야 합니다.')
            image.load()
            # Match the API's EXIF policy; the original bytes are sent unchanged.
            shown=image if mode=='classification' else ImageOps.exif_transpose(image)
            return shown.convert('RGB'),mime
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as e:
        raise ValueError('사진 해상도가 너무 큽니다.') from e
    except (OSError,SyntaxError) as e:
        raise ValueError('사진을 읽을 수 없습니다. 정상적인 JPEG/PNG 파일을 선택해 주세요.') from e

def validate_result(body,mode):
    if not isinstance(body,dict) or not isinstance(body.get(mode),dict):
        raise ValueError('API 응답이 문서의 검사 형식과 다릅니다. 배포 모델 형식을 확인해 주세요.')
    part=body[mode]
    items=[part] if mode=='classification' else part.get('detections' if mode=='detection' else 'instances')
    if not isinstance(items,list) or len(items)>10000: raise ValueError('검사 후보 배열 형식이 올바르지 않습니다.')
    for x in items:
        if not isinstance(x,dict) or not isinstance(x.get('class'),dict) or not isinstance(x['class'].get('name'),str): raise ValueError('판정 클래스 정보가 누락되었습니다.')
        if not isinstance(x.get('score'),(float,int)) or not math.isfinite(x['score']) or not 0<=x['score']<=1: raise ValueError('모델 점수 형식이 올바르지 않습니다.')
        if mode!='classification':
            box=x.get('bbox_xyxy')
            if not isinstance(box,list) or len(box)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in box) or box[2]<box[0] or box[3]<box[1]: raise ValueError('객체 위치 형식이 올바르지 않습니다.')
        if mode=='segmentation':
            r=x.get('mask_rle',{})
            if not isinstance(r,dict) or not isinstance(r.get('counts'),str) or not isinstance(r.get('size'),list) or len(r['size'])!=2 or not all(type(v) is int and v>0 for v in r['size']): raise ValueError('분할 마스크 형식이 올바르지 않습니다.')
    if mode=='classification':
        probs=part.get('probabilities')
        if not isinstance(probs,list) or len(probs)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in probs): raise ValueError('분류 확률 배열 형식이 올바르지 않습니다.')
    return body

def _drop_mpf(jpeg):
    """Remove APP2 'MPF' segments so decoders see a plain JPEG (the scan data is untouched)."""
    out,i=bytearray(jpeg[:2]),2
    while i+4<=len(jpeg) and jpeg[i]==0xFF and jpeg[i+1]!=0xDA:
        end=i+2+int.from_bytes(jpeg[i+2:i+4],'big')
        if not (jpeg[i+1]==0xE2 and jpeg[i+4:i+8]==b'MPF\x00'):out+=jpeg[i:end]
        i=end
    return bytes(out+jpeg[i:])

def api_bytes(data):
    """The inspection API accepts plain JPEG/PNG only. For phone-camera MPO files send the primary JPEG
    frame as-is (no re-encoding, EXIF kept); everything else is sent unchanged."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format!='MPO':return data
            size=im.mpinfo[0xB002][0]['Size']
    except (OSError,KeyError,IndexError,TypeError):return data
    return _drop_mpf(data[:size])

def call_model(mode,data,mime):
    if mode not in MODES: raise ValueError('지원하지 않는 검사입니다.')
    try:
        response=requests.post(BASE+'/predict/'+mode,files={'file':('inspection.jpg' if mime=='image/jpeg' else 'inspection.png',api_bytes(data),mime)},timeout=(10,300))
    except requests.Timeout as e: raise ValueError('응답 대기 시간이 초과됐습니다. 서버에서는 작업이 계속될 수 있으므로 즉시 반복 실행하지 말고 잠시 후 확인해 주세요.') from e
    except requests.RequestException as e: raise ValueError('검사 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.') from e
    try: body=response.json()
    except ValueError as e: raise ValueError(f'검사 서버가 JSON이 아닌 응답을 반환했습니다 (HTTP {response.status_code}).') from e
    if not response.ok:
        detail=body.get('detail','검사 요청 처리 실패') if isinstance(body,dict) else '검사 요청 처리 실패'
        if not isinstance(detail,str): detail=json.dumps(detail,ensure_ascii=False)
        retry=response.headers.get('Retry-After')
        suffix=f' {retry}초 이상 기다린 뒤 다시 시도해 주세요.' if response.status_code==429 and retry else ''
        raise ValueError(f'HTTP {response.status_code}: {detail[:600]}'+suffix)
    return validate_result(body,mode)

def overlay(image,items,with_mask=False,numbers=None):
    # Draw on a bounded preview while mapping original-resolution boxes and masks.
    out=image.copy();out.thumbnail((1200,1200));out=out.convert('RGBA')
    sx,sy=out.width/image.width,out.height/image.height
    colors=['#1d65c1','#b34332','#34764d','#8a4aab','#8c5a12']
    for n,item in enumerate(items):
        color=colors[n%len(colors)]
        if with_mask:
            r=item['mask_rle']
            if r['size']!=[image.height,image.width]: raise ValueError('마스크 크기가 방향 보정된 원본 사진과 다릅니다. 오버레이를 표시하지 않습니다.')
            mask=mask_utils.decode({'size':r['size'],'counts':r['counts'].encode('ascii')})
            alpha=Image.fromarray((mask.astype(np.uint8)*105),'L').resize(out.size,Image.Resampling.NEAREST)
            layer=Image.new('RGBA',out.size,color);layer.putalpha(alpha);out=Image.alpha_composite(out,layer)
        draw=ImageDraw.Draw(out)
        x1,y1,x2,y2=item['bbox_xyxy'];box=(max(0,x1*sx),max(0,y1*sy),min(out.width,x2*sx),min(out.height,y2*sy))
        if box[2]>=box[0] and box[3]>=box[1]:
            draw.rectangle(box,outline=color,width=3)
            draw.text((box[0]+3,box[1]+3),f'#{numbers[n] if numbers else n+1}',fill='white',stroke_width=2,stroke_fill=color)
    return out.convert('RGB')

KIND={'classification':'CLASSIFICATION','detection':'DETECTION','segmentation':'SEGMENTATION'}

def task_tabs(mode,task):
    tabs=[('judge','직접 판단 실습',f'?inspection={mode}'),('review','AI 판정 검토',f'?inspection={mode}&task=review')]
    return ('<nav class="task-tabs" aria-label="실습 종류">'+''.join(
        f'<a href="{href}"'+(' class="on" aria-current="page"' if k==task else '')+f'>{label}</a>' for k,label,href in tabs)+'</nav>')

def workspace_header(mode,cfg,task='judge'):
    side=task_tabs(mode,task)
    return (f'<main id="workspace" tabindex="-1" class="ws-{mode}"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 검사 실습 <span aria-hidden="true">/</span> {cfg["number"]}. {cfg["title"]}</div>'
        f'<section class="workspace-title"><div class="title-row"><div class="title-main"><h1><span class="workspace-number">{cfg["number"]}</span>{cfg["title"]}</h1>'
        f'<p>{cfg["target"]} — {cfg["explain"]}</p></div>{side}</div></section></main>')

def run_row(label,disabled,key=None):
    """Primary run button with the assistant button on its right. Returns True when run is clicked."""
    run,chat=st.container(key='t13runrow_'+(key or 'x')).columns([4,1.4],gap='small',vertical_alignment='center')
    clicked=run.button(label,type='primary',disabled=disabled,width='stretch',key=key)
    with chat:
        fragment('<button type="button" class="run-chat-btn" data-chat aria-controls="chat-panel" aria-label="LNG_NI 챗봇 열기"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 4H3v14h5l4 4v-4h9ZM7 9h10M7 13h6"/></svg>챗봇</button>')
    return clicked

def step(num,title):
    return f'<div class="step-head"><b>STEP {num}</b><h3>{title}</h3></div>'

# Full format rules live in the AgentStream system prompt; this line only reinforces them per question.
ANSWER_FORMAT = '핵심은 맨 위에 표로 정리하고, 판정·점수·개수·사진 이름은 이 검사 정보의 값만 그대로 쓰세요.'


def model_mark(view, case):
    """'맞음'/'틀림' for the model's verdict on a revealed case, so the chatbot never has to work it out."""
    return '-' if not view else ('맞음' if view['defect'] == case['defect'] else '틀림')


def chat_context(cfg, screen, **extra):
    """What the assistant chatbot is told about the learner's current screen (sent as <inspection_context>)."""
    return {'검사 종류': f"{cfg['number']}. {cfg['title']}", '모델': cfg['model'], '판정 클래스': cfg['classes'], '화면': screen, **extra,
            '답변 형식': ANSWER_FORMAT}


def model_summary(mode, body):
    part = body[mode]
    if mode == 'classification':
        return {'선택 클래스': part['class']['name'], '모델 점수': round(part['score'], 4),
                '클래스별 확률': {n: round(v, 4) for n, v in zip(MODES[mode]['classes'], part['probabilities'])}}
    items = part['detections' if mode == 'detection' else 'instances']
    top = sorted(items, key=lambda x: -x['score'])[:15]
    return {'전체 후보 수': len(items), '후보(점수순, 최대 15개)': [{'클래스': x['class']['name'], '점수': round(x['score'], 4)} for x in top]}


def render(mode):
    if mode not in MODES: mode='classification'
    cfg=MODES[mode]
    shell(mode=mode)
    cases=load_cases(mode)
    task='review' if st.query_params.get('task')=='review' else 'judge'
    fragment(workspace_header(mode,cfg,task))
    if task=='review':
        from review import render_review
        ctx=render_review(mode,cfg) or {}
        publish_chat_context(chat_context(cfg,'AI 판정 검토 · '+ctx.pop('단계','진행 중'),**ctx))
        fragment('<div class="ws-foot">'+footer()+'</div>');return
    if cases:
        render_quiz(mode,cfg,cases)
        fragment('<div class="ws-foot">'+footer()+'</div>');return
    left,right=st.columns([1,1.2],gap='large')
    with left, st.container(border=True, key='t13step1u'):
        fragment(step(1,'사진을 관찰하고 검사하기'))
        file=st.file_uploader('검사 대상의 JPEG / PNG 사진 한 장',type=['jpg','jpeg','png'],key='upload_'+mode,help='최대 10 MiB, 최대 20,000,000픽셀. 사진은 검사 실행 시 지정된 외부 API로 전송됩니다.')
        data=None;image=None;sig=None;mime=None
        if file:
            try:
                data=file.getvalue();image,mime=read_image(data,mode);sig=mode+':'+hashlib.sha256(data).hexdigest()
            except ValueError as e: st.error(str(e))
        if image:
            st.image(image,caption='입력 사진 · '+('EXIF 방향 보정 없이 표시' if mode=='classification' else 'EXIF 방향을 적용해 표시'),width='stretch')
        guess=st.selectbox('검사 전 내 예상 (선택)', ['아직 판단하지 않음']+cfg['classes'],key='guess_'+mode)
        confirmed=st.checkbox('사진의 대상이 선택한 검사 목적과 일치합니다.',key='confirm_'+mode)
        st.caption('실행하면 업로드 사진을 지정된 검사 API에 전송합니다. 이 사이트는 사진·결과를 파일로 저장하지 않습니다.')
        if run_row(cfg['number']+'번 검사 실행',image is None or not confirmed,key='run_single_'+mode):
            st.session_state.pop('inspection_result',None)
            with st.spinner('검사 대기·분석 중입니다. 완료될 때까지 기다려 주세요…'):
                try:
                    result=call_model(mode,data,mime)
                    st.session_state.inspection_result={'signature':sig,'body':result,'time':datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S'),'guess':guess}
                except ValueError as e: st.error(str(e))
    has_result=bool(st.session_state.get('inspection_result')) and sig is not None and st.session_state['inspection_result'].get('signature')==sig
    with right, st.container(border=True, key=None if has_result else 't13emptystep'):
        fragment(step(2,'모델 결과와 내 관찰 비교하기'))
        render_result(mode,cfg,image,sig)
    if has_result:
        saved=st.session_state['inspection_result']
        extra={'내 예상':saved['guess'],'모델 결과':model_summary(mode,saved['body']),'검사 시각':saved['time'],'정답 라벨':'없음 (직접 올린 사진이라 정답 라벨이 없습니다)'}
        if mode!='classification':extra['화면 표시 점수 필터']=st.session_state.get('threshold_'+mode,0.5)
        publish_chat_context(chat_context(cfg,'사진 업로드 검사 · 결과 확인',**extra))
    else:
        publish_chat_context(chat_context(cfg,'사진 업로드 검사 · 검사 전',**{'내 예상':guess,'사진 업로드':'예' if image else '아니요'}))
    fragment('<div class="ws-foot">'+footer()+'</div>')

def render_result(mode,cfg,image,sig):
    saved=st.session_state.get('inspection_result')
    if not saved or image is None or saved['signature']!=sig:
        fragment('<div class="empty-result"><svg viewBox="0 0 96 96" aria-hidden="true"><rect x="14" y="20" width="68" height="52" rx="6"/><path d="m22 62 18-18 12 12 8-8 14 14"/><circle cx="62" cy="36" r="6"/></svg><h3>사진을 올리고 검사를 실행해 주세요</h3><p>왼쪽에서 사진을 업로드하고 예상을 기록한 뒤 검사를 실행하면, 모델 결과가 이곳에 표시됩니다.</p></div>')
        return
    body=saved['body'];part=body[mode]
    st.caption('검사 시각 '+saved['time']+' (한국시간) · 실제 API 응답')
    st.caption('검사 전 내 예상: '+saved['guess'])
    if mode=='classification':
        st.metric('모델이 선택한 클래스',part['class']['name'])
        st.metric('모델 점수',f"{part['score']*100:.1f}%")
        st.dataframe([{'클래스':name,'모델 확률':f'{v*100:.1f}%'} for name,v in zip(cfg['classes'],part['probabilities'])],hide_index=True,width='stretch')
        st.info('“해당 없음” 클래스가 없습니다. 높은 점수가 검사 대상 적합성이나 정답을 보장하지 않습니다.')
    else:
        items=part['detections' if mode=='detection' else 'instances']
        threshold=st.slider('화면에 표시할 최소 모델 점수',0.0,1.0,0.5,0.05,key='threshold_'+mode)
        st.caption('0.5는 표시 필터의 초기값이며 검증된 합격·불량 판정 기준이 아닙니다. 필터 변경은 API를 다시 호출하지 않습니다.')
        chosen=st.multiselect('표시할 클래스',options=sorted({x['class']['name'] for x in items}),key='classes_'+sig,placeholder='선택하지 않으면 모든 클래스 표시')
        visible=[x for x in items if x['score']>=threshold and (not chosen or x['class']['name'] in chosen)]
        st.write(f'전체 후보 {len(items)}개 · 표시 후보 {len(visible)}개')
        if visible:
            target=visible
            if mode=='segmentation':
                selected=st.selectbox('오버레이로 확인할 후보',range(len(visible)),format_func=lambda i:f"#{i+1} {visible[i]['class']['name']} · {visible[i]['score']*100:.1f}%",key='mask_'+sig)
                target=[visible[selected]]
            try: st.image(overlay(image,target,mode=='segmentation', [selected+1] if mode=='segmentation' else None),caption='선택 후보의 픽셀 마스크·사각형' if mode=='segmentation' else '객체별 사각형 · 번호는 아래 목록과 대응',width='stretch')
            except (ValueError,TypeError,OverflowError) as e: st.error('오버레이 생성 실패: '+str(e))
            st.dataframe([{'번호':i+1,'클래스':x['class']['name'],'모델 점수':f"{x['score']*100:.1f}%",'원본 좌표':str(x['bbox_xyxy'])} for i,x in enumerate(visible)],hide_index=True,width='stretch',height=210)
        else: st.info('표시 조건에 맞는 후보가 없습니다. 후보가 없다는 이유만으로 전체 양품으로 판정하지 마세요.')
        if mode=='segmentation': st.caption('중복·낮은 점수 후보가 포함될 수 있습니다. 후보 수는 실제 불량 개수가 아닙니다.')
    st.caption('교육용 관찰 보조 결과입니다. 실제 현장 판정에는 기업 검사 기준과 담당자의 검토가 필요합니다.')
    st.download_button('검사 결과 JSON 내려받기',json.dumps(body,ensure_ascii=False,indent=2),file_name='team13-'+mode+'-result.json',mime='application/json')
    with st.expander('관찰 기록 · 교육 복습'):
        st.text_area('예상과 모델 결과의 차이, 추가 확인할 내용을 적어 보세요.',key='reflection_'+sig)
        st.caption('기록은 현재 세션에서만 유지되며 서버 파일로 저장하지 않습니다.')

# ---------------------------------------------------------------- defect-picking quiz (demo_cases)
CASES_DIR = Path(__file__).parent / 'demo_cases' / 'raw'  # every sub-folder with a samples.csv is a case set
CASES_ROOT = Path(os.environ['T13_CASES']) if os.environ.get('T13_CASES') else None  # optional single set (tests)
SHOW_SCORE = 0.5  # detection/segmentation: candidates at/above this count as "found"
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def is_defect_class(name):
    """Every class that is not a '...양품' class is a defect class (불량, 균열, 스크래치, 손상 ...)."""
    return '양품' not in name


def case_roots():
    if CASES_ROOT: return [CASES_ROOT]
    return sorted(d for d in CASES_DIR.iterdir() if (d / 'samples.csv').is_file()) if CASES_DIR.is_dir() else []


def load_cases(mode, root=None):
    """Photos this inspection's model can judge, from one case set or (default) every set under demo_cases/raw/
    (team13_samples: foam spray -> 1, team13_welding: welding -> 3). Classes decide the inspection."""
    if root is None:
        return [c for r in case_roots() for c in load_cases(mode, r)]
    return _load_set(mode, Path(root))


def _load_set(mode, root):
    """Read samples.csv (클래스명, 이미지 파일, 라벨 파일) and keep the photos this inspection's model can judge.
    Ground truth: the label JSON's attributes.quality ('불량품'/'양품'), else the class name."""
    index = root / 'samples.csv'
    if not index.is_file(): return []
    cases = []
    with index.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            cls, img = (row.get('클래스명') or '').strip(), (row.get('이미지 파일') or '').strip()
            if cls not in MODES[mode]['classes'] or not img: continue
            path = root / cls / img
            if not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png'): continue
            quality, place = None, ''
            label = root / cls / (row.get('라벨 파일') or '').strip()
            if label.is_file() and label.suffix == '.json':
                try:
                    attrs = json.loads(label.read_text(encoding='utf-8'))['annotations'][0].get('attributes', {})
                    quality = attrs.get('quality')
                    place = ' · '.join(str(attrs[k]) for k in ('location', 'sub_location', 'part') if attrs.get(k))
                except (ValueError, KeyError, IndexError, TypeError, OSError): pass
            defect = quality == '불량품' if quality in ('불량품', '양품') else is_defect_class(cls)
            cases.append({'id': path.stem, 'path': str(path), 'cls': cls, 'defect': defect, 'place': place})
    return cases


@st.cache_data(show_spinner=False, max_entries=64)
def case_bytes(path, mtime):
    return Path(path).read_bytes()


@st.cache_data(show_spinner=False, max_entries=64)
def case_thumb(path, mtime, mode, side=900):
    """Small JPEG for display (originals are 3~5 MB). Same EXIF policy as read_image."""
    with Image.open(path) as im:
        shown = im if mode == 'classification' else ImageOps.exif_transpose(im)
        shown = shown.convert('RGB'); shown.thumbnail((side, side))
        buf = io.BytesIO(); shown.save(buf, format='JPEG', quality=85)
        return buf.getvalue()


def model_view(mode, body):
    """Reduce an API body to label / score / defect verdict."""
    part = body[mode]
    if mode == 'classification':
        name = part['class']['name']
        return {'label': name, 'score': part['score'], 'defect': is_defect_class(name)}
    items = part['detections' if mode == 'detection' else 'instances']
    found = sorted((x for x in items if x['score'] >= SHOW_SCORE), key=lambda x: -x['score'])
    bad = [x for x in found if is_defect_class(x['class']['name'])]
    top = (bad or found or [None])[0]
    label = f"{top['class']['name']} 외 {len(found)-1}개" if top and len(found) > 1 else (top['class']['name'] if top else f'점수 {SHOW_SCORE} 이상 후보 없음')
    return {'label': label, 'score': top['score'] if top else None, 'defect': bool(bad)}


def verdict(defect):
    return '불량' if defect else '양품'


QUIZ_SIZE = 4


def pick_round(cases, n=QUIZ_SIZE, rng=None):
    """Draw n photos in random order with at least one 불량 and one 양품 when both exist
    (how many of each varies, so the count itself is no hint)."""
    import random
    rng = rng or random.SystemRandom()
    bad = [c['id'] for c in cases if c['defect']]; good = [c['id'] for c in cases if not c['defect']]
    n = min(n, len(cases))
    if bad and good and n >= 2:
        k = rng.randint(max(1, n - len(good)), min(n - 1, len(bad)))
        ids = rng.sample(bad, k) + rng.sample(good, n - k)
    else:
        ids = rng.sample(bad + good, n)
    rng.shuffle(ids)
    return ids


def render_quiz(mode, cfg, cases):
    import random
    key = 'quiz_' + mode
    state = st.session_state.setdefault(key, {})
    by_id = {c['id']: c for c in cases}
    if not state.get('order') or any(i not in by_id for i in state['order']):  # new round, or the photo set changed
        state.clear(); state['order'] = pick_round(cases)
    order = [by_id[i] for i in state['order']]
    cases = order  # only this round's photos are shown, sent to the API and scored
    names = {c['id']: '사진 ' + LETTERS[n] for n, c in enumerate(order)}
    submitted = 'results' in state
    defects = sum(c['defect'] for c in cases)

    if not submitted:
        with st.container(border=True, key='t13step1'):
            fragment(step(1, '불량 사진을 모두 골라 보세요'))
            st.caption(f"사진 {len(cases)}장 중 불량이라고 생각하는 사진에 체크하세요. 체크하지 않은 사진은 양품으로 판단한 것으로 봅니다.")
            with st.container(key='t13quizgrid'):  # one wrapping row: 3 per line on PC, 2 on phones (CSS)
                for col, c in zip(st.columns(len(order), gap='small'), order):
                    with col, st.container(border=True):
                        mtime = Path(c['path']).stat().st_mtime
                        st.image(case_thumb(c['path'], mtime, mode), width='stretch')
                        st.checkbox(f"{names[c['id']]} 불량", key=f"{key}_pick_{c['id']}", disabled=False)
            picks = {c['id']: bool(st.session_state.get(f"{key}_pick_{c['id']}")) for c in cases}
            st.caption(f'불량으로 고른 사진 {sum(picks.values())}장 · 실행하면 사진 {len(cases)}장을 검사 API에 전송합니다.')
            if run_row(f"{cfg['number']}번 검사 실행 · 내 선택 제출", False, key='run_quiz_' + mode):
                state['picks'] = picks
                results, progress = {}, st.progress(0.0, text='검사 준비 중…')
                for n, c in enumerate(order):
                    progress.progress(n / len(order), text=f"{n+1}/{len(order)} · {names[c['id']]} 검사 중…")
                    data = case_bytes(c['path'], Path(c['path']).stat().st_mtime)
                    try:
                        _, mime = read_image(data, mode)
                        body = call_model(mode, data, mime)
                        results[c['id']] = {'view': model_view(mode, body), 'body': body}
                    except ValueError as e: results[c['id']] = {'error': str(e)}
                state['results'] = results
                state['time'] = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%H:%M:%S')
                state['scroll'] = True  # bring STEP 2 into view after the rerun
                st.rerun()
        publish_chat_context(chat_context(cfg, '직접 판단 실습 · 불량 사진 고르기 (제출 전)', **{
            '사진 수': len(cases), '내가 불량으로 고른 사진': [names[i] for i, v in picks.items() if v], '정답 공개': '아니요 (제출 후 공개)'}))
        return

    with st.container(border=True, key='t13step2'):
        picks, results = state['picks'], state['results']
        judged = [c for c in order if 'view' in results[c['id']]]
        mine = sum(picks[c['id']] == c['defect'] for c in order)
        model_ok = sum(results[c['id']]['view']['defect'] == c['defect'] for c in judged)
        fragment('<div class="step-row">' + step(2, '정답 · 내 선택 · 모델 판정 비교') + '<ul class="q-summary" aria-label="결과 요약">'
                 f'<li>실제 불량 <b>{defects}</b> / {len(cases)}장</li>'
                 f'<li>내 정답 <b>{mine}</b> / {len(cases)}</li>'
                 f'<li>모델 정답 <b>{model_ok if judged else "-"}</b> / {len(judged)}</li></ul></div>')
        for c in order:
            r = results[c['id']]
            if 'error' in r: st.error(f"{names[c['id']]}: {r['error']}")
        with st.container(key='t13quizres'):  # 3 per line on PC, 1 on phones (CSS)
            for col, c in zip(st.columns(len(order), gap='small'), order):
                r, pick = results[c['id']], picks[c['id']]
                with col, st.container(border=True):
                    st.image(case_thumb(c['path'], Path(c['path']).stat().st_mtime, mode), width='stretch')
                    me_ok = pick == c['defect']
                    lines = [f'<p class="q-title" title="{html.escape(c["cls"] + (" · " + c["place"] if c["place"] else ""))}">{names[c["id"]]}<span class="q-truth {"bad" if c["defect"] else "good"}">정답 {verdict(c["defect"])}</span></p>']
                    lines.append(f'<p class="q-line"><span>내 선택</span><b>{verdict(pick)}</b><i class="{"ok" if me_ok else "ng"}">{"맞음" if me_ok else "틀림"}</i></p>')
                    if 'view' in r:
                        v = r['view']; ok = v['defect'] == c['defect']
                        # three lines: verdict / class label / score  (e.g. 양품 / 볼트체결 / 97.3%)
                        parts = [verdict(v['defect']), html.escape(v['label'])] + ([f"{v['score']*100:.1f}%"] if v['score'] is not None else [])
                        lines.append(f'<p class="q-line"><span>모델 판정</span><b class="q-multi">{"<br>".join(parts)}</b><i class="{"ok" if ok else "ng"}">{"맞음" if ok else "틀림"}</i></p>')
                    else: lines.append('<p class="q-line"><span>모델 판정</span><b>검사 실패</b></p>')
                    fragment('<div class="q-card">' + ''.join(lines) + '</div>')
        st.caption(f"검사 {state['time']} · 모델 점수는 정답률이 아닙니다." + ('' if mode == 'classification' else f' 점수 {SHOW_SCORE} 이상 후보에 불량 클래스가 있으면 불량으로 봅니다.'), help=None)
        entries = []
        for c in order:
            r, pick = results[c['id']], picks[c['id']]
            v = r.get('view')
            entries.append({'name': names[c['id']], 'path': c['path'], 'truth': f"{verdict(c['defect'])} · {c['cls']}", 'truth_defect': c['defect'],
                            'mine': verdict(pick), 'ok': pick == c['defect'], 'body': r.get('body'),
                            'ai': f"{verdict(v['defect'])} · {v['label']}" + (f" {v['score']*100:.1f}%" if v and v['score'] is not None else '') if v else '검사 실패',
                            'tip': None if pick == c['defect'] else (f"실제로는 {c['cls']}입니다. 사진에서 불량 근거를 다시 찾아보세요." if c['defect'] else '실제로는 양품입니다. 불량으로 본 근거가 무엇이었는지 다시 확인해 보세요.')})
        wrong = sum(not e['ok'] for e in entries)
        rev, again, chat = st.container(key='t13runrow_again').columns([2.2, 2.2, 1.2], gap='small', vertical_alignment='center')
        if rev.button(f'오답 복습 · {wrong}장' if wrong else 'AI 확신도 보기', icon=':material/school:', width='stretch', key='quiz_dialog_' + mode):
            from review import open_review
            open_review('오답 복습 · 정답과 AI 확신도', entries, mode)
        if again.button('새 문제 풀기', icon=':material/refresh:', width='stretch', key='quiz_again_' + mode):
            for c in cases: st.session_state.pop(f"{key}_pick_{c['id']}", None)
            st.session_state.pop(key, None); st.rerun()
        with chat:
            fragment('<button type="button" class="run-chat-btn" data-chat aria-controls="chat-panel" aria-label="LNG_NI 챗봇 열기"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 4H3v14h5l4 4v-4h9ZM7 9h10M7 13h6"/></svg>챗봇</button>')
        marks = [(e['name'], e['ok'], model_mark(results[c['id']].get('view'), c)) for e, c in zip(entries, order)]
        listed = lambda keep: ', '.join(n for n, mine_ok, ai in marks if keep(mine_ok, ai)) or '없음'
        publish_chat_context(chat_context(cfg, '직접 판단 실습 · 결과 비교 (제출 후)', **{
            '정답 공개': '예', '요약': {'사진 수': len(cases), '실제 불량': defects, '내 정답': mine, '모델 정답': f'{model_ok}/{len(judged)}' if judged else '검사 실패',
                                    '내가 틀린 사진': listed(lambda m, a: not m), '모델이 맞힌 사진': listed(lambda m, a: a == '맞음'),
                                    '모델이 틀린 사진': listed(lambda m, a: a == '틀림'), '둘 다 틀린 사진': listed(lambda m, a: not m and a == '틀림')},
            '사진별 결과': [{'사진': e['name'], '정답': e['truth'], '촬영 위치': c['place'] or None, '내 선택': e['mine'], '내 선택 정오': '맞음' if e['ok'] else '틀림',
                          '모델 판정': e['ai'], '모델 판정 정오': model_mark(results[c['id']].get('view'), c)} for e, c in zip(entries, order)]}))
    if state.pop('scroll', False):
        render_html('<span hidden></span>', "setTimeout(()=>document.querySelector('[data-testid=stMain]')?.scrollTo({top:0}),150)")
