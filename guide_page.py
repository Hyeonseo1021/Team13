"""?page=guide&topic=<usage|photo|result> · 학습 가이드 shown as page content (not a pop-up)."""
import streamlit as st

from inspection import MODES
from review import MAX_PHOTOS
from ui import shell, icon
import accounts

TOPICS = {'usage': ('실습 이용 가이드', '검사 선택부터 기록 확인까지'),
          'photo': ('사진 준비 방법', '형식·크기·촬영 대상 확인'),
          'result': ('결과 해석 방법', '점수·사각형·마스크 읽는 법')}


def steps(items):
    return '<ol class="gd-steps">' + ''.join(
        f'<li><span class="gd-no">{i}</span><div><strong>{t}</strong><p>{d}</p>' + (f'<a class="gd-go" href="{href}">{label} <span aria-hidden="true">›</span></a>' if href else '') + '</div></li>'
        for i, (t, d, href, label) in enumerate(items, 1)) + '</ol>'


def note(text, kind='info'):
    return f'<p class="gd-note {kind}">{icon("book")}<span>{text}</span></p>'


def usage():
    return ('<h2>실습 이용 가이드</h2><p class="gd-lead">처음이라면 아래 순서대로 진행하세요. 각 단계의 버튼을 누르면 해당 화면으로 이동합니다.</p>'
            + steps([
                ('검사 종류 고르기', '1. 표면 상태 분류 · 2. 볼트·케이블 탐지 · 3. 결함 영역 분할 중 하나를 고릅니다. 검사마다 AI 모델이 구분하는 판정 클래스가 다릅니다.', '?page=classes', '판정 클래스 보기'),
                ('직접 판단 실습', '샘플 사진 4장 중 불량이라고 생각하는 사진을 고르고 제출합니다. 제출하면 정답과 AI 판정이 함께 공개되고, 틀린 사진은 AI 확신도와 함께 다시 볼 수 있습니다.', '?inspection=classification', '1번 검사 실습하기'),
                ('역량평가', '검사 3종 15문항을 AI 판정·챗봇 없이 혼자 풉니다. 80점 이상이면 합격이고, 결과는 마이페이지에 저장됩니다.', '?page=exam', '역량평가 응시하기'),
                ('판정 검토', f'역량평가에 합격하면 열립니다. 사진을 최대 {MAX_PHOTOS}장 올리면 AI가 한 장씩 판정을 제안하고, 근거를 직접 확인해 승인하거나 거절하고 올바른 판정을 고릅니다. 결정은 내 이름으로 저장됩니다.', '?page=judge&inspection=classification', '판정 검토하기'),
                ('마이페이지에서 기록 확인', '검토 건수, 승인·거절 비율, 최근 검토한 사진을 확인하고 전체 기록을 CSV로 내려받을 수 있습니다.', '?page=my', '마이페이지'),
            ])
            + note('AI 점수(확률)는 정답률이나 합격 판정이 아닙니다. 최종 판정은 원본 사진과 회사 검사 기준으로 직접 확인하세요.')
            + note('궁금한 점은 검사 화면의 <b class="t13-brand">LNG_NI</b> 버튼을 눌러 물어볼 수 있습니다.'))


def photo():
    targets = ''.join(f'<li><b>{c["number"]}. {c["title"]}</b> · {c["target"]}</li>' for c in MODES.values())
    return ('<h2>사진 준비 방법</h2><p class="gd-lead">AI 판정 검토에 올릴 사진은 아래 조건을 맞춰 주세요.</p>'
            '<div class="gd-grid">'
            '<section class="gd-box"><h3>파일 조건</h3><ul class="gd-list">'
            '<li>JPEG 또는 PNG</li><li>한 장당 10 MiB 이하</li><li>가로×세로 2,000만 픽셀 이하</li>'
            f'<li>한 번에 최대 {MAX_PHOTOS}장까지 끌어다 놓기</li></ul></section>'
            f'<section class="gd-box"><h3>검사별 촬영 대상</h3><ul class="gd-list">{targets}</ul></section>'
            '<section class="gd-box"><h3>촬영 팁</h3><ul class="gd-list">'
            '<li>검사 대상이 사진에 충분히 크게 보이도록 찍습니다.</li><li>흔들림·역광·심한 반사가 있으면 결과가 불안정할 수 있습니다.</li>'
            '<li>검사 종류와 맞지 않는 사진도 모델은 판정을 내놓습니다. 대상이 맞는지 먼저 확인하세요.</li></ul></section></div>'
            + note(f'검토하는 사진은 지정된 검사 API로 전송됩니다. 사이트에는 <b>사진 보관에 동의한 경우에만</b> 축소본(긴 변 {accounts.PHOTO_EDGE}px, 위치정보 제거)을 '
                   f'{accounts.PHOTO_DAYS}일간 보관하며, 본인만 볼 수 있고 마이페이지에서 언제든 지울 수 있습니다.')
            + note('회사 보안 규정상 반출이 금지된 현장 사진은 올리지 마세요.', 'warn'))


def result():
    rows = [('1. 표면 상태 분류', 'ViT', '사진 전체를 4개 클래스 중 하나로 판정하고 클래스별 확률을 보여 줍니다.', '“해당 없음”이 없어 무관한 사진도 4개 중 하나로 분류됩니다.'),
            ('2. 볼트·케이블 탐지', 'EfficientDet', '찾은 객체마다 클래스·점수·사각형 위치를 보여 줍니다.', '아무것도 탐지되지 않았다고 양품이라는 뜻은 아닙니다.'),
            ('3. 결함 영역 분할', 'MaskDINO', '후보마다 클래스·점수와 픽셀 단위 마스크를 보여 줍니다.', '후보가 겹치거나 점수가 낮을 수 있어, 후보 수가 실제 불량 개수는 아닙니다.')]
    table = ('<table class="gd-table"><thead><tr><th scope="col">검사</th><th scope="col">모델</th><th scope="col">보여 주는 것</th><th scope="col">주의할 점</th></tr></thead><tbody>'
             + ''.join(f'<tr><th scope="row">{a}</th><td><span class="cls-model">{b}</span></td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in rows) + '</tbody></table>')
    return ('<h2>결과 해석 방법</h2><p class="gd-lead">AI 결과는 판단을 돕는 참고 자료입니다. 검사별로 무엇을 보여 주는지와 주의할 점을 확인하세요.</p>'
            + table +
            '<div class="gd-grid two"><section class="gd-box"><h3>AI 확신도 막대</h3><p>클래스별 확률(분류) 또는 상위 후보의 점수(탐지·분할)를 막대로 보여 줍니다. 가장 높은 항목이 AI 제안입니다.</p></section>'
            '<section class="gd-box"><h3>사각형과 마스크</h3><p>탐지·분할 결과는 사진 위에 사각형과 색칠된 영역으로 표시됩니다. 점수가 일정 기준 이상인 후보만 그립니다.</p></section></div>'
            + note('점수가 높아도 정답을 보장하지 않습니다. 사진에서 근거를 직접 확인한 뒤 승인하거나 거절하세요.'))


def render():
    topic = st.query_params.get('topic')
    if topic not in TOPICS:
        topic = 'usage'
    tabs = ''.join(f'<a href="?page=guide&amp;topic={k}"' + (' class="on" aria-current="page"' if k == topic else '') + f'>{t}<small>{s}</small></a>'
                   for k, (t, s) in TOPICS.items())
    body = {'usage': usage, 'photo': photo, 'result': result}[topic]()
    html_ = (f'<main id="workspace" tabindex="-1" class="guide-main"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 학습 가이드 '
             f'<span aria-hidden="true">/</span> {TOPICS[topic][0]}</div>'
             '<section class="workspace-title"><div class="title-main"><h1>학습 가이드</h1><p>처음 실습하는 신입직원을 위한 단계별 안내입니다.</p></div></section>'
             f'<nav class="gd-tabs" aria-label="가이드 주제">{tabs}</nav><article class="gd-panel">{body}</article></main>')
    shell(None, no_chat=True, current='guide', home=html_)
