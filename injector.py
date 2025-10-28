import random
import logging
from urllib.parse import urlsplit, urlunsplit, urlencode, urljoin
import httpx
from payloads import PAYLOADS
import time

logger = logging.getLogger(__name__)

_GLOBAL_CLIENT: httpx.AsyncClient = None

def _next_id():
    return f"{int(time.time())}_{random.randint(1000,9999)}"

def make_marker(marker_template="XSS_MARKER_{id}", id_val=None):
    if id_val is None:
        id_val = _next_id()
    return id_val, marker_template.format(id=id_val)

def choose_payload(id_val, safe=False):
    if safe:
        return f"XSS_MARKER_{id_val}"
    p = random.choice(PAYLOADS)
    try:
        return p.format(id=id_val)
    except Exception:
        return p.replace("{id}", id_val)

def get_client(timeout=20):
    global _GLOBAL_CLIENT
    if _GLOBAL_CLIENT is None:
        _GLOBAL_CLIENT = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    return _GLOBAL_CLIENT

async def close_client():
    global _GLOBAL_CLIENT
    if _GLOBAL_CLIENT is not None:
        try:
            await _GLOBAL_CLIENT.aclose()
        except Exception:
            pass
        _GLOBAL_CLIENT = None

async def _fetch_url(url, method="GET", params=None, data=None, timeout=20):
    client = get_client(timeout=timeout)
    try:
        if method == "GET":
            return await client.get(url, params=params)
        else:
            return await client.post(url, data=data)
    except Exception:
        logger.debug("HTTP fetch failed for %s (method=%s)", url, method, exc_info=True)
        return None

async def inject_get(inp, marker_template="XSS_MARKER_{id}"):
    id_val, marker = make_marker(marker_template)
    payload = choose_payload(id_val, safe=False)

    url = inp.get('url')
    param = inp.get('param')
    params = dict(inp.get('params') or {})

    for k, v in list(params.items()):
        if isinstance(v, (list, tuple)):
            params[k] = v[0] if v else ""

    if param:
        params[param] = payload

    sp = urlsplit(url)
    query = urlencode(params, doseq=True)
    new_url = urlunsplit((sp.scheme, sp.netloc, sp.path, query, sp.fragment))

    r = await _fetch_url(new_url, method="GET")
    return new_url, r, marker

async def inject_form(inp, marker_template="XSS_MARKER_{id}"):
    id_val, marker = make_marker(marker_template)
    payload = choose_payload(id_val, safe=False)

    action = inp.get('action') or inp.get('url')
    if inp.get('url') and action and not action.startswith(("http://", "https://")):
        action = urljoin(inp.get('url'), action)

    fields = dict(inp.get('form_fields') or {})
    param = inp.get('param')
    if param:
        fields[param] = payload

    method = (inp.get('method') or 'POST').upper()

    if method == "GET":
        sp = urlsplit(action)
        query = urlencode(fields, doseq=True)
        new_url = urlunsplit((sp.scheme, sp.netloc, sp.path, query, sp.fragment))
        r = await _fetch_url(new_url, method="GET")
        return new_url, r, marker
    else:
        r = await _fetch_url(action, method=method, data=fields)
        final_url = str(r.url) if r else action
        return final_url, r, marker

async def confirm_injection(inp, marker_template="XSS_MARKER_{id}", safe=True):
    id_val, marker = make_marker(marker_template)
    payload = choose_payload(id_val, safe=safe)

    itype = inp.get('type', 'GET')

    if itype == "FORM":
        action = inp.get('action') or inp.get('url')
        if inp.get('url') and action and not action.startswith(("http://", "https://")):
            action = urljoin(inp.get('url'), action)
        fields = dict(inp.get('form_fields') or {})
        param = inp.get('param')
        if param:
            fields[param] = payload
        method = (inp.get('method') or 'POST').upper()
        if method == "GET":
            sp = urlsplit(action)
            query = urlencode(fields, doseq=True)
            new_url = urlunsplit((sp.scheme, sp.netloc, sp.path, query, sp.fragment))
            r = await _fetch_url(new_url, method="GET")
            return new_url, r, payload
        else:
            r = await _fetch_url(action, method=method, data=fields)
            final_url = str(r.url) if r else action
            return final_url, r, payload
    else:
        url = inp.get('url')
        param = inp.get('param')
        params = dict(inp.get('params') or {})
        for k, v in list(params.items()):
            if isinstance(v, (list, tuple)):
                params[k] = v[0] if v else ""
        if param:
            params[param] = payload
        sp = urlsplit(url)
        query = urlencode(params, doseq=True)
        new_url = urlunsplit((sp.scheme, sp.netloc, sp.path, query, sp.fragment))
        r = await _fetch_url(new_url, method="GET")
        return new_url, r, payload