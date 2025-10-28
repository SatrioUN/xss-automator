# poc_formatter.py
"""
POC formatter for XSSAutomatorApp

Usage:
    from poc_formatter import format_finding
    msg = format_finding(finding_dict)
    print(msg)
"""

import html
import os
from urllib.parse import unquote, urlparse, urlunparse, quote_plus

def _severity_bracket(confidence: int, evidence_type: str) -> str:
    """
    Map confidence/evidence to a short bracket tag used in the POC line.
    - dom_exec -> V (verified)
    - reflected*  -> R (reflected)
    - low/other -> S (suspicious)
    """
    et = (evidence_type or "").lower()
    if "dom_exec" in et or "dom_exec" in et or confidence >= 95:
        return "V"
    if "dom_reflection" in et or "reflected" in et or 70 <= confidence < 95:
        return "R"
    return "S"

def _severity_label(confidence: int, evidence_type: str) -> str:
    """
    Produce the leading label shown on the first line:
    [V] Triggered XSS Payload (found DOM Object)
    [W] Reflected Payload in HTML
    [I] Informational, etc.
    """
    et = (evidence_type or "").lower()
    if "dom_exec" in et:
        return "[V]"  # verified / dangerous
    if "dom_reflection" in et or "reflected" in et or 70 <= confidence < 95:
        return "[W]"  # warning/reflected
    # informational / weak
    return "[I]"

def _safe_snippet(snippet: str, maxlen: int = 160) -> str:
    if not snippet:
        return ""
    s = str(snippet).strip()
    try:
        s = html.unescape(s)
    except Exception:
        pass
    if len(s) > maxlen:
        s = s[:maxlen-3] + "..."
    return s

def _determine_method(meta: dict) -> str:
    if not isinstance(meta, dict):
        return "GET"
    m = (meta.get("method") or "")
    if m:
        return m.upper()
    if meta.get("params"):
        return "GET"
    if meta.get("form_fields"):
        return "POST"
    return "GET"

def _format_line_info(response_text: str, marker: str, max_snip_len: int = 200) -> str:
    if not response_text or not marker:
        return ""
    try:
        idx = response_text.find(marker)
        if idx == -1:
            return ""
        # compute line number
        line_no = response_text[:idx].count("\n") + 1
        lines = response_text.splitlines()
        excerpt = lines[line_no - 1] if line_no - 1 < len(lines) else response_text
        excerpt = _safe_snippet(excerpt, max_snip_len)
        return f"    {line_no} line:   syntax to use near '{excerpt}'"
    except Exception:
        return ""

def _format_poc_line(sev_short: str, method: str, tested_url: str) -> str:
    """
    Create POC line similar to:
    [POC][R][GET][inHTML-URL] http://example.com/?q=...encoded...
    Keep tested_url mostly intact, but ensure safe quoting of non-ascii by quoting path+query.
    """
    if not tested_url:
        url = ""
    else:
        try:
            # Try to preserve human-readable encoding but make it safe
            p = urlparse(tested_url)
            # quote only path and query parts to avoid double-encoding existing %
            path = quote_plus(p.path, safe="/%")
            query = p.query
            if query:
                # keep existing percent-encodings but make sure reserved chars are preserved
                query = query.replace(" ", "%20")
                # do not re-quote % sequences
            rebuilt = urlunparse((p.scheme, p.netloc, path, p.params, query, p.fragment))
            url = rebuilt
        except Exception:
            url = tested_url
    return f"[POC][{sev_short}][{method}][inHTML-URL] {url}"

def format_finding(f: dict) -> str:
    """
    Format a finding dict into multi-line human-friendly output.
    Expected keys in f:
      - confidence (int)
      - evidence: dict possibly containing 'type', 'snippet', 'screenshot'
      - marker: str
      - path: str
      - meta: dict with 'param', 'tested_url', 'response_text', etc.
    """
    if not isinstance(f, dict):
        return ""

    conf = int(f.get("confidence", 0) or 0)
    evidence = (f.get("evidence") or {}) or {}
    evidence_type = evidence.get("type", "") if isinstance(evidence, dict) else ""
    label = _severity_label(conf, evidence_type)

    # headline description text for evidence
    desc = None
    if evidence_type:
        if "dom_exec" in evidence_type:
            desc = "Triggered XSS Payload (found DOM Object)"
        elif "dom_reflection" in evidence_type:
            desc = "Reflected test param =>"
        elif "reflected_script" in evidence_type or "reflected" in evidence_type:
            desc = "Reflected Payload in HTML"
        else:
            desc = evidence_type
    else:
        desc = evidence.get("detail") or "Possible reflection"

    marker = f.get("marker") or ""
    path = f.get("path") or ""
    meta = f.get("meta") or {}
    param = meta.get("param") or ""
    tested_url = meta.get("tested_url") or ""
    method = _determine_method(meta)

    # payload preview: snippet if available else marker
    snippet = evidence.get("snippet") or ""
    payload_preview = snippet if snippet else marker
    payload_preview = _safe_snippet(payload_preview, 140)

    # line info (attempt to show where in HTTP response marker appeared)
    response_text = meta.get("response_text") or ""
    line_info = _format_line_info(response_text, marker, max_snip_len=200)

    # screenshot info if present
    screenshot_info = ""
    ss = evidence.get("screenshot") or meta.get("screenshot")
    if ss:
        screenshot_info = f"    screenshot: {ss}"

    # severity short for POC tag
    sev_short = _severity_bracket(conf, evidence_type)

    # Build message lines
    lines = []

    # First line: severity label + description + payload preview
    lines.append(f"{label} {desc}: {payload_preview}")

    # Path, param (optional)
    if path:
        lines.append(f"    path: {path}")
    if param:
        lines.append(f"    param: {param}")

    # Add line info if any
    if line_info:
        lines.append(line_info)

    # Add screenshot line if present
    if screenshot_info:
        lines.append(screenshot_info)

    # POC line and confidence
    lines.append(_format_poc_line(sev_short, method, tested_url))
    lines.append(f"    confidence: {conf}")

    # Separator (optional) - keep compact
    return "\n".join(lines)