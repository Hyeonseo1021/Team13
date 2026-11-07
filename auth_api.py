"""Login routes: browser -> POST {base}/api/t13/auth/{login,signup,logout} (JSON) -> HttpOnly session cookie.

The cookie is set by these HTTP responses (not by page JavaScript), so scripts on the page cannot read it.
Streamlit reads it on the next page load through st.context.cookies (accounts.current_user).
"""
import json

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import accounts

MAX_BODY = 4 * 1024


def same_origin(request):
    """Custom header forces a CORS preflight that is never answered; Origin, when sent, must be this host."""
    if request.headers.get('x-t13-auth') != '1':
        return False
    origin = request.headers.get('origin')
    if not origin:
        return True
    host = request.headers.get('x-forwarded-host') or request.headers.get('host', '')
    return origin.split('://', 1)[-1].rstrip('/') == host.split(',')[0].strip()


async def _body(request):
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise ValueError
    data = json.loads(raw.decode('utf-8') or '{}')
    if not isinstance(data, dict):
        raise ValueError
    return data


def _with_cookie(request, payload, token):
    resp = JSONResponse(payload)
    secure = request.headers.get('x-forwarded-proto', request.url.scheme) == 'https'
    path = request.scope.get('t13_base', '/') or '/'
    if token:
        resp.set_cookie(accounts.COOKIE, token, max_age=accounts.SESSION_DAYS * 86400, httponly=True, samesite='lax', secure=secure, path=path)
    else:
        resp.delete_cookie(accounts.COOKIE, path=path, httponly=True, samesite='lax', secure=secure)
    return resp


def _handler(kind):
    async def handle(request: Request):
        if not same_origin(request):
            return JSONResponse({'message': '허용되지 않은 요청입니다.'}, status_code=403)
        try:
            data = await _body(request)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({'message': '요청 형식이 올바르지 않습니다.'}, status_code=400)
        try:
            if kind == 'logout':
                accounts.logout(request.cookies.get(accounts.COOKIE))
                return _with_cookie(request, {'ok': True}, None)
            fn = accounts.signup if kind == 'signup' else accounts.login
            token = await _run(fn, data.get('name'), data.get('password'))
            return _with_cookie(request, {'ok': True}, token)
        except accounts.AuthError as e:
            return JSONResponse({'message': str(e)}, status_code=400 if kind == 'signup' else 401)
    return handle


async def _run(fn, *args):
    import anyio
    return await anyio.to_thread.run_sync(fn, *args)  # scrypt + sqlite off the event loop


def routes(base_url_path=''):
    base = '/' + base_url_path.strip('/') if base_url_path and base_url_path.strip('/') else ''

    def with_base(handler):
        async def wrapped(request):
            request.scope['t13_base'] = (base or '') + '/'
            return await handler(request)
        return wrapped

    return [Route(f'{base}/api/t13/auth/{k}', with_base(_handler(k)), methods=['POST']) for k in ('login', 'signup', 'logout')]
