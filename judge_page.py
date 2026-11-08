"""?page=judge&inspection=<mode> · 판정 검토 (실무).

AI 판정 검토 moved out of 검사 실습: it is work for people who have shown they can judge, so it opens only for
learners who passed 역량평가 at least once (accounts.can_judge) and for the admin account. 내 검토 기록 stays in 마이페이지."""
import html
from urllib.parse import urlencode

import streamlit as st

import accounts
from inspection import MODES, chat_context
from ui import shell, fragment, footer, publish_chat_context


def href(mode):
    return f'?page=judge&inspection={mode}'


def header(mode, cfg):
    tabs = ''.join(f'<a href="{href(k)}"' + (' class="on" aria-current="page"' if k == mode else '') + f'>{c["number"]}. {c["title"]}</a>'
                   for k, c in MODES.items())
    return (f'<main id="workspace" tabindex="-1" class="ws-{mode}"><div class="breadcrumb">학습 공간 <span aria-hidden="true">/</span> 판정 검토 '
            f'<span aria-hidden="true">/</span> {cfg["number"]}. {cfg["title"]}</div>'
            f'<section class="workspace-title"><div class="title-row"><div class="title-main"><h1><span class="workspace-number">{cfg["number"]}</span>{cfg["title"]} 판정 검토</h1>'
            f'<p>{cfg["target"]} — AI가 제안한 판정을 승인하거나 거절하고 올바른 판정을 기록합니다.</p></div>'
            f'<nav class="task-tabs judge-tabs" aria-label="검사 종류">{tabs}</nav></div></section></main>')


def locked(title, text, link, label):
    fragment('<div class="gd-panel judge-lock"><svg class="icon" viewBox="0 0 24 24" width="44" height="44" aria-hidden="true">'
             '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>'
             f'<h3>{title}</h3><p>{text}</p><a class="login-submit" href="{html.escape(link)}">{label}</a></div>')


def render(mode):
    if mode not in MODES:
        mode = 'classification'
    cfg = MODES[mode]
    user = accounts.current_user()
    allowed = accounts.can_judge(user)
    shell(mode=mode if allowed else None, current='judge', no_chat=not allowed)
    fragment(header(mode, cfg))
    if not user:
        locked('로그인 후 판정 검토를 이용할 수 있습니다',
               '판정 검토는 역량평가에 합격한 검사자가 이용하는 실무 화면입니다. 먼저 로그인해 주세요.',
               '?' + urlencode({'page': 'login', 'next': href(mode)}), '로그인 / 회원가입')
    elif not allowed:
        locked('역량평가 합격 후 이용할 수 있습니다',
               f'{html.escape(user["name"])} 님은 아직 역량평가 합격 기록이 없습니다. AI 판정을 검토하려면 사진을 보고 직접 판정할 수 있어야 합니다. '
               '검사 실습으로 연습한 뒤 역량평가에 응시해 보세요.', '?page=exam', '역량평가 응시하기')
    else:
        from review import render_review
        ctx = render_review(mode, cfg) or {}
        publish_chat_context(chat_context(cfg, '판정 검토 · ' + ctx.pop('단계', '진행 중'), **ctx))
    fragment('<div class="ws-foot">' + footer() + '</div>')
