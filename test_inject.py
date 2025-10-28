import asyncio
import html
from injector import inject_get, inject_form, confirm_injection

async def test_get():
    inp = {
        'url': 'http://testphp.vulnweb.com/artists.php',
        'param': 'artist',
        'params': {'artist': '1'},
        'type': 'GET'
    }
    new_url, r, marker = await inject_get(inp)
    print("NEW URL:", new_url)
    print("MARKER:", marker)
    status = getattr(r, "status_code", None) if r is not None else None
    print("STATUS:", status)
    resp_text = (r.text if r is not None else "") or ""
    print("RESPONSE PREVIEW:", resp_text[:400].replace("\n", " "))
    present_raw = marker in resp_text
    present_unescaped = marker in html.unescape(resp_text)
    print("MARKER IN RESPONSE (raw):", present_raw)
    print("MARKER IN RESPONSE (unescaped):", present_unescaped)

if __name__ == "__main__":
    asyncio.run(test_get())