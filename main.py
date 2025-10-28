import asyncio
import argparse
import logging
import yaml
import sys
import os
import re
import base64

from injector import inject_get, inject_form, confirm_injection
from analyzer import Analyzer_stub_analyze, verify_dom_execution
from reporter import Reporter
from poc_formatter import format_finding
from utils import now_ts, ensure_dir
from crawler import Crawler
from enumerator import enumerate_inputs

try:
    from telegram_bot import TelegramController
except Exception:
    TelegramController = None

print("main.py started, argv:", sys.argv)


def setup_logging(cfg: dict):
    """Setup logging configuration"""
    log_cfg = cfg.get("logging") or {}
    level_name = (log_cfg.get("level") or ("DEBUG" if cfg.get("debug") else "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    ch = logging.StreamHandler(sys.__stderr__)
    ch.setFormatter(logging.Formatter(fmt))
    ch.setLevel(level)
    root.addHandler(ch)

    log_file = log_cfg.get("file")
    if log_file:
        parent = os.path.dirname(log_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8", errors="replace")
        fh.setFormatter(logging.Formatter(fmt))
        fh.setLevel(level)
        root.addHandler(fh)

    root.setLevel(level)


class XSSAutomatorApp:
    """Core scanning and analysis app"""

    def __init__(self, cfg):
        self.cfg = cfg or {}
        self.findings = []
        self._running = False
        self._active_confirmed = False
        self._last_report = None
        self._scan_task = None
        self.telegram_controller = None

        self.reporter = Reporter(
            out_dir=cfg.get('report', {}).get('out_dir', './reports'),
            json_out=cfg.get('report', {}).get('json', True),
            html_out=cfg.get('report', {}).get('html', True)
        )
        ensure_dir(cfg.get('report', {}).get('screenshot_dir', "./reports/screenshots"))

    async def start_scan(self, trigger="cli", base_url=None, control_chat_id=None, active=False, playwright=False):
        """Start scanning process"""
        if self._running:
            return "Scan already running."
        if active and self.cfg.get('safety', {}).get('require_telegram_confirm_for_active', True) and not self._active_confirmed:
            return "Active mode requires Telegram confirmation."

        base = base_url or self.cfg.get('target', {}).get('base_url')
        allow_hosts = self.cfg.get('target', {}).get('allow_hosts') or [base]
        max_pages = int(self.cfg.get('crawler', {}).get('max_pages', 200))
        rps = int(self.cfg.get('crawler', {}).get('rate_limit_rps', 5))
        use_playwright = playwright or self.cfg.get('verification', {}).get('use_playwright', False)

        self._scan_task = asyncio.create_task(
            self._run_scan(base, allow_hosts, max_pages, rps, active, use_playwright, control_chat_id)
        )
        return f"Scan started for {base}"

    async def stop_scan(self):
        """Stop running scan"""
        if not self._scan_task:
            return "No scan task running."
        try:
            self._scan_task.cancel()
            await self._scan_task
        except Exception:
            pass
        self._scan_task = None
        self._running = False
        return "Scan stopped."

    async def get_status(self):
        if self._running:
            return f"Scan running. Findings so far: {len(self.findings)}"
        return f"Idle. Last report: {self._last_report or 'none'}"

    async def confirm_active_from_chat(self, chat_id: int):
        if not self.telegram_controller:
            return "Telegram controller not configured."
        if chat_id not in self.telegram_controller.allowed_chat_ids:
            return "Chat not authorized."
        self._active_confirmed = True
        return "Active mode confirmed."

    async def _run_scan(self, base, allow_hosts, max_pages, rps, active, use_playwright, control_chat_id):
        self._running = True
        self.findings = []
        try:
            logging.info("Starting crawler for %s", base)
            crawler = Crawler(base, allow_hosts, max_pages=max_pages, rps=rps)
            pages = await crawler.crawl()
            logging.info("Pages crawled: %d", len(pages))
            marker_tpl = self.cfg.get('injection', {}).get('marker_template', 'XSS_MARKER_{id}')

            for url, resp in pages:
                html_text = getattr(resp, "text", "") or ""
                inputs = enumerate_inputs(url, html_text)
                injections_done = 0

                for inp in inputs:
                    if injections_done >= int(self.cfg.get('injection', {}).get('max_injections_per_page', 6)):
                        break

                    try:
                        # inject payload
                        if inp.get('type') == 'GET':
                            new_url, r, marker = await inject_get(inp, marker_template=marker_tpl)
                        else:
                            new_url, r, marker = await inject_form(inp, marker_template=marker_tpl)

                        resp_text = getattr(r, "text", "") or ""
                        meta = {**inp, "tested_url": new_url, "response_text": resp_text}
                        results = await Analyzer_stub_analyze(new_url, resp_text, marker, meta)

                        # filter valid positives only
                        min_conf = int(self.cfg.get('verification', {}).get('min_confidence', 70))
                        positives = [f for f in results if f.get("confidence", 0) >= min_conf]

                        for f in positives:
                            formatted = format_finding(f)
                            print(formatted)
                            self.findings.append(f)

                            # Telegram notify
                            if self.telegram_controller:
                                chat = control_chat_id or next(iter(self.telegram_controller.allowed_chat_ids), None)
                                if chat:
                                    await self.telegram_controller.send_message(chat, formatted)

                        injections_done += 1
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logging.exception("Error testing input")

            paths = self.reporter.save(self.findings, meta_name="report")
            logging.info("Report saved: %s", paths)
            self._last_report = paths.get('json') or paths.get('html')
        except Exception:
            logging.exception("Scan failed")
        finally:
            self._running = False


async def run_with_telegram(cfg_path, run_cli_args):
    """Main orchestration with Telegram support"""
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}

    setup_logging(cfg)
    app = XSSAutomatorApp(cfg)

    tg_cfg = cfg.get('telemetry', {}).get('telegram', {}) or {}
    tg_token = os.getenv(tg_cfg.get('bot_token_env') or "") or tg_cfg.get('bot_token')
    tc = None

    if tg_token and TelegramController:
        try:
            tc = TelegramController(token=tg_token, allowed_chat_ids=tg_cfg.get('allowed_chat_ids', []), app_ref=app)
            await tc.start()
            app.telegram_controller = tc
            logging.info("Telegram controller started")
        except Exception:
            logging.exception("Telegram controller startup failed")

    if run_cli_args and getattr(run_cli_args, "scan", False):
        resp = await app.start_scan(base_url=run_cli_args.base_url)
        print(resp)

    try:
        while True:
            if (tc is None) and not (hasattr(app, "_scan_task") and app._scan_task and not app._scan_task.done()):
                break
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[!] Scan interrupted. Cleaning up...")
    finally:
        if tc:
            await tc.stop()
        if hasattr(app, "_scan_task") and app._scan_task:
            app._scan_task.cancel()


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--scan", action="store_true")
    p.add_argument("--base-url", default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(run_with_telegram(args.config, args))
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
    except Exception as e:
        logging.exception("Fatal error: %s", e)