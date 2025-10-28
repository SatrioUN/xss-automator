import sys
import asyncio
import base64
from playwright.async_api import async_playwright

async def debug_visit(url, marker, headless=False, wait_ms=3000, timeout_ms=20000, screenshot_path="debug_playwright.png"):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        page = await browser.new_page()
        # override alert before page loads
        await page.add_init_script(
            """() => {
                window.__xss_executed = false;
                const oldAlert = window.alert;
                window.alert = function() { window.__xss_executed = true; try { return oldAlert.apply(this, arguments); } catch(e){} }
            }"""
        )
        try:
            await page.goto(url, timeout=timeout_ms)
        except Exception as e:
            print("goto() exception:", e)
        # wait extra time for deferred scripts / onload
        await page.wait_for_timeout(wait_ms)
        try:
            alert_executed = await page.evaluate("() => !!window.__xss_executed")
        except Exception:
            alert_executed = False
        try:
            content = await page.content()
        except Exception:
            content = ""
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
            with open(screenshot_path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
        except Exception as e:
            print("screenshot failed:", e)
            b64 = None
        await browser.close()
        return {"alert_executed": bool(alert_executed), "marker_present": (marker in content), "content_snippet": content[:1000], "screenshot_b64": b64}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_playwright.py <url> <marker> [headless(false|true)]")
        sys.exit(1)
    url = sys.argv[1]
    marker = sys.argv[2]
    headless_flag = False
    if len(sys.argv) >= 4 and sys.argv[3].lower() in ("true","1"):
        headless_flag = True
    res = asyncio.run(debug_visit(url, marker, headless=headless_flag, wait_ms=4000))
    print("RESULT:", res)