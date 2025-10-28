import logging
import asyncio
import base64

logger = logging.getLogger(__name__)


async def Analyzer_stub_analyze(url, response_text, marker, meta):
    findings = []
    if marker and marker in (response_text or ""):
        findings.append({
            "timestamp": int(asyncio.get_event_loop().time()),
            "url": url,
            "marker": marker,
            "confidence": 90,
            "evidence": {"type": "reflected_text", "snippet": marker},
            "meta": meta
        })
    return findings


async def verify_dom_execution(url: str, marker: str, timeout_ms: int = 8000, headless: bool = True):
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {"alert_executed": False, "marker_present": False, "playwright_available": False}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            page = await browser.new_page()
            await page.goto(url, timeout=timeout_ms)
            content = await page.content()
            marker_present = marker in content
            screenshot_b64 = base64.b64encode(await page.screenshot()).decode("ascii")
            await browser.close()
            return {"alert_executed": False, "marker_present": marker_present, "screenshot_b64": screenshot_b64, "playwright_available": True}
    except Exception:
        return {"alert_executed": False, "marker_present": False, "playwright_available": True}