"""?page=login: name + password login and sign-up. The forms post to auth_api.py, which sets the session cookie."""
import html
import re

import streamlit as st

import accounts
from ui import shell

NEXT_RE = re.compile(r'^\?[A-Za-z0-9_=&%.\-]*$')


def safe_next(value):
    """Only same-page query strings (no scheme, host or path) are allowed as the return address."""
    value = str(value or '')
    return value if NEXT_RE.match(value) and 'page=login' not in value else '?'


def render():
    nxt = safe_next(st.query_params.get('next'))
    user = accounts.current_user()
    if user:
        body = (f'<div class="login-card"><h1 id="login-title">로그인되어 있습니다</h1><p class="login-lead"><b>{html.escape(user["name"])}</b> 님으로 학습 중입니다.</p>'
                f'<a class="login-submit" href="{html.escape(nxt)}">계속하기</a><button type="button" class="login-link" data-logout="">다른 이름으로 로그인 (로그아웃)</button></div>')
    else:
        body = f'''<div class="login-card" data-next="{html.escape(nxt)}">
<h1 id="login-title">로그인</h1>
<p class="login-lead">AI 판정 검토 기록은 로그인한 이름으로 저장됩니다.</p>
<div class="login-tabs" role="tablist" aria-label="로그인 또는 회원가입">
 <button type="button" role="tab" id="tab-login" aria-selected="true" aria-controls="form-login">로그인</button>
 <button type="button" role="tab" id="tab-signup" aria-selected="false" aria-controls="form-signup" tabindex="-1">회원가입</button>
</div>
<form class="login-form" id="form-login" role="tabpanel" aria-labelledby="tab-login" data-kind="login" novalidate>
 <label for="li-name">이름</label><input id="li-name" name="name" autocomplete="username" maxlength="20" required>
 <label for="li-pw">비밀번호</label><input id="li-pw" name="password" type="password" autocomplete="current-password" maxlength="64" required>
 <p class="login-error" role="alert" aria-live="assertive"></p>
 <button type="submit" class="login-submit">로그인</button>
</form>
<form class="login-form" id="form-signup" role="tabpanel" aria-labelledby="tab-signup" data-kind="signup" novalidate hidden>
 <label for="su-name">이름</label><input id="su-name" name="name" autocomplete="username" maxlength="20" required aria-describedby="su-name-help">
 <p class="login-help" id="su-name-help">2~20자 한글·영문·숫자. 같은 이름이 있으면 사번이나 소속을 붙여 주세요. (예: 홍길동_1234)</p>
 <label for="su-pw">비밀번호</label><input id="su-pw" name="password" type="password" autocomplete="new-password" maxlength="64" required aria-describedby="su-pw-help">
 <p class="login-help" id="su-pw-help">8자 이상, 문자와 숫자를 함께 사용하세요. 회사 비밀번호는 쓰지 마세요.</p>
 <label for="su-pw2">비밀번호 확인</label><input id="su-pw2" name="password2" type="password" autocomplete="new-password" maxlength="64" required>
 <p class="login-error" role="alert" aria-live="assertive"></p>
 <button type="submit" class="login-submit">가입하고 로그인</button>
</form>
<p class="login-note">이름과 검토 기록은 이 서버에 저장됩니다. 비밀번호는 복원할 수 없는 형태로만 저장합니다. 검토한 사진은 동의한 경우에만 축소본으로 90일간 보관하며 본인만 볼 수 있습니다.</p>
</div>'''
    shell(None, no_chat=True, home=f'<main id="workspace" tabindex="-1" class="login-main" aria-labelledby="login-title">{body}</main>')
