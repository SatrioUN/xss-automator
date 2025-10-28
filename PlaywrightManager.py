import logging
import base64
from typing import Optional, Dict
from playwright.async_api import async_playwright, Playwright, Browser

logger = logging.getLogger(__name__)

class PlaywrightManager:
    def __init__(self, headless: bool = True):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._headless = bool(headless)
        self.started = False

    async def start(self):
        if self.started:
            return
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self._headless)
            self.started = True
            logger.info("PlaywrightManager started (browser launched)")
        except Exception:
            logger.exception("Failed to start PlaywrightManager")
            self.started = False
            raise

    async def stop(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            logger.exception("Error stopping PlaywrightManager")
        finally:
            self._browser = None
            self._playwright = None
            self.started = False

    async def verify(self, url: str, marker: str, timeout_ms: int = 10000, wait_ms: int = 800, screenshot: bool = True) -> Dict:
        """
        Render page in a new page and check for alert execution and marker presence.
        Returns dict with keys:
         - alert_executed: bool
         - marker_present: bool
         - screenshot_b64: base64 str or None
         - content: page HTML content (string)
        """
        if not self.started or not self._browser:
            raise RuntimeError("PlaywrightManager not started")
        page = None
        try:
            page = await self._browser.new_page()
            await page.add_init_script(
                """() => {
                    window.__xss_executed = false;
                    const oldAlert = window.alert;
                    window.alert = function() { window.__xss_executed = true; try { return oldAlert.apply(this, arguments); } catch(e){} }
                }"""
            )
            try:
                await page.goto(url, timeout=timeout_ms)
            except Exception:
                logger.debug("page.goto timeout/exception for %s", url, exc_info=True)
            await page.wait_for_timeout(wait_ms)
            try:
                alert_executed = await page.evaluate("() => !!window.__xss_executed")
            except Exception:
                alert_executed = False
            try:
                content = await page.content()
                marker_present = marker in (content or "")
            except Exception:
                marker_present = False
                content = ""
            ss_b64 = None
            if screenshot:
                try:
                    buf = await page.screenshot(full_page=True)
                    ss_b64 = base64.b64encode(buf).decode()
                except Exception:
                    logger.exception("Failed to take screenshot for %s", url)
                    ss_b64 = None
            return {"alert_executed": bool(alert_executed), "marker_present": bool(marker_present), "screenshot_b64": ss_b64, "content": content}
        finally:
            try:
                if page:
                    await page.close()
            except Exception:
                pass