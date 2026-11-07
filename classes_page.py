"""?page=classes&type=<inspection> · 판정 클래스: what each model can answer, shown as page content (not a pop-up)."""
import html

import streamlit as st

from inspection import MODES, is_defect_class
from ui import shell, icon


def class_cards(classes):
    def card(name):
        bad = is_defect_class(name)
        return (f'<li class="{"bad" if bad else "good"}"><span class="cls-badge">{"불량" if bad else "양품"}</span>'
                f'<strong>{html.escape(name)}</strong></li>')
    bad = [c for c in classes if is_defect_class(c)]
    good = [c for c in classes if not is_defect_class(c)]
    return ('<div class="cls-groups">'
            f'<section class="cls-group" aria-labelledby="cls-bad"><h3 id="cls-bad">불량 클래스 <b>{len(bad)}</b></h3><ul class="cls-list">' + ''.join(map(card, bad)) + '</ul></section>'
            f'<section class="cls-group" aria-labelledby="cls-good"><h3 id="cls-good">양품 클래스 <b>{len(good)}</b></h3><ul class="cls-list">' + ''.join(map(card, good)) + '</ul></section></div>')


def render():
    key = st.query_params.get('type')
    if key not in MODES:
        key = 'classification'
    cfg = MODES[key]
    tabs = ''.join(f'<a href="?page=classes&amp;type={k}"' + (' class="on" aria-current="page"' if k == key else '') +
                   f'><span class="cls-tab-no">{c["number"]}</span>{c["title"]}<small>{len(c["classes"])}개</small></a>' for k, c in MODES.items())
    body = (f'<main id="workspace" tabindex="-1" class="classes-main"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 판정 클래스 '
            f'<span aria-hidden="true">/</span> {cfg["number"]}. {cfg["title"]}</div>'
            '<section class="workspace-title"><div class="title-main"><h1>판정 클래스</h1><p>검사별로 AI 모델이 구분하는 판정 종류입니다. 실습 전에 어떤 결함을 찾는지 확인하세요.</p></div></section>'
            f'<nav class="cls-tabs" aria-label="검사 종류">{tabs}</nav>'
            f'<section class="cls-panel" aria-labelledby="cls-title"><div class="cls-head"><div><h2 id="cls-title"><span class="workspace-number">{cfg["number"]}</span>{cfg["title"]}</h2>'
            f'<p class="cls-meta"><span class="cls-model">{cfg["model"]}</span>{html.escape(cfg["target"])} · {html.escape(cfg["explain"])}</p></div>'
            f'<div class="cls-actions"><a class="btn btn-primary" href="?inspection={key}">이 검사 실습하기</a>'
            f'<a class="btn btn-line" href="?inspection={key}&amp;task=review">AI 판정 검토</a></div></div>'
            f'<p class="cls-lesson">{icon("book")}<span><b>관찰 포인트</b> {html.escape(cfg["lesson"])}</span></p>'
            + class_cards(cfg['classes']) + '</section></main>')
    shell(None, no_chat=True, current='classes', home=body)
