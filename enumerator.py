from urllib.parse import urlparse, parse_qs, urljoin
from bs4 import BeautifulSoup

def _safe_first(v):
    if isinstance(v, list):
        return v[0] if len(v) > 0 else ""
    return v

def enumerate_inputs(url, response_text):
    inputs = []
    soup = BeautifulSoup(response_text or "", "html.parser")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    params = {k: _safe_first(v) for k, v in qs.items()}
    for k in qs.keys():
        inputs.append({"type":"GET", "url":url, "param":k, "params": dict(params)})

    for form in soup.find_all("form"):
        method = (form.get("method") or "GET").upper()
        action = form.get("action") or url
        action = urljoin(url, action)
        form_fields = {}
        for inp in form.find_all(["input","textarea","select"]):
            name = inp.get("name")
            if not name:
                continue
            if inp.name == "select":
                val = ""
                option = inp.find("option", selected=True)
                if option:
                    val = option.get("value") or option.text or ""
                else:
                    first = inp.find("option")
                    if first:
                        val = first.get("value") or first.text or ""
            else:
                val = inp.get("value") or ""
            form_fields[name] = val
        for name in list(form_fields.keys()):
            inputs.append({
                "type":"FORM",
                "url": url,
                "method": method,
                "action": action,
                "param": name,
                "form_fields": dict(form_fields)
            })
    return inputs