import logging
import os
import asyncio
from typing import Iterable, Optional, Set, Any
import httpx

logger = logging.getLogger(__name__)


def _normalize_chat_ids(ids: Optional[Iterable]) -> set[int]:
    out = set()
    if not ids:
        return out
    for v in ids:
        try:
            out.add(int(v))
        except Exception:
            logger.warning("Ignoring invalid chat id: %r", v)
    return out


class TelegramController:
    """
    Telegram bot controller: full control (if python-telegram-bot installed),
    fallback to HTTP send-only if not available.
    Compatible with async main loop.
    """

    def __init__(self, token: str, allowed_chat_ids: Iterable = None, app_ref: Any = None):
        self.token = token
        self.allowed_chat_ids = _normalize_chat_ids(allowed_chat_ids)
        self.app_ref = app_ref
        self._use_ptb = False
        self.application = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._api_base = f"https://api.telegram.org/bot{self.token}"
        self._polling_task: Optional[asyncio.Task] = None

    # ----------------------------------------------------------------
    # Utilities
    # ----------------------------------------------------------------
    def is_allowed(self, update) -> bool:
        try:
            cid = getattr(update, "effective_chat", None)
            if cid:
                cid = getattr(update.effective_chat, "id", None)
            return cid in self.allowed_chat_ids
        except Exception:
            return False

    def _ensure_http_client(self):
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

    async def _close_http_client(self):
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception:
                pass
            self._http_client = None

    # ----------------------------------------------------------------
    # Start / Stop logic
    # ----------------------------------------------------------------
    async def start(self):
        """Initialize and start Telegram bot."""
        try:
            from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
            from telegram import Update
            self._use_ptb = True
        except Exception:
            logger.info("python-telegram-bot not installed; fallback to HTTP send-only mode.")
            self._ensure_http_client()
            logger.info("Telegram controller initialized (send-only).")
            return

        try:
            app = ApplicationBuilder().token(self.token).build()

            # ---------------- Commands ----------------
            async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                text = (
                    "/scan [url] - start scan (uses config url if omitted)\n"
                    "/status - show current scan status\n"
                    "/stop - stop running scan\n"
                    "/report - get latest report\n"
                    "/confirm_active - confirm allowing active payloads\n"
                    "/help - show this help\n"
                )
                await self._reply(update, text)

            async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await cmd_help(update, context)

            async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                try:
                    status = await self.app_ref.get_status() if self.app_ref else "Status unavailable"
                    await self._reply(update, status)
                except Exception:
                    logger.exception("cmd_status failed")
                    await self._reply(update, "Failed to get status.")

            async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                try:
                    args = context.args
                    base_url = args[0] if args else None
                    msg = await self.app_ref.start_scan(
                        trigger="telegram", base_url=base_url, control_chat_id=update.effective_chat.id
                    )
                    await self._reply(update, str(msg))
                except Exception:
                    logger.exception("cmd_scan failed")
                    await self._reply(update, "Failed to start scan.")

            async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                try:
                    msg = await self.app_ref.stop_scan()
                    await self._reply(update, str(msg))
                except Exception:
                    logger.exception("cmd_stop failed")
                    await self._reply(update, "Failed to stop scan.")

            async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                try:
                    path = await self.app_ref.get_latest_report()
                    if path and os.path.exists(path):
                        await self.send_document(update.effective_chat.id, path)
                    else:
                        await self._reply(update, "No report available.")
                except Exception:
                    logger.exception("cmd_report failed")
                    await self._reply(update, "Failed to send report.")

            async def cmd_confirm_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not self.is_allowed(update):
                    await self._reply(update, "Unauthorized.")
                    return
                try:
                    msg = await self.app_ref.confirm_active_from_chat(update.effective_chat.id)
                    await self._reply(update, msg)
                except Exception:
                    logger.exception("cmd_confirm_active failed")
                    await self._reply(update, "Failed to confirm active mode.")

            # Register commands
            for cmd, handler in {
                "help": cmd_help,
                "start": cmd_start,
                "status": cmd_status,
                "scan": cmd_scan,
                "stop": cmd_stop,
                "report": cmd_report,
                "confirm_active": cmd_confirm_active,
            }.items():
                app.add_handler(CommandHandler(cmd, handler))

            # Error handler
            async def error_handler(update, context):
                logger.exception("Unhandled Telegram error: %s", context.error)
                if update and self.is_allowed(update):
                    await self._reply(update, f"⚠️ Error: {context.error}")

            app.add_error_handler(error_handler)
            self.application = app

            # Start async polling safely (without closing main loop)
            await self.application.initialize()
            await self.application.start()

            if hasattr(self.application, "updater") and self.application.updater:
                self._polling_task = asyncio.create_task(self.application.updater.start_polling())
            else:
                # fallback polling
                self._polling_task = asyncio.create_task(self.application.start_polling())

            logger.info("Telegram controller started (full control mode).")
        except Exception as e:
            logger.exception("Failed to start Telegram bot: %s", e)
            self._use_ptb = False
            self._ensure_http_client()

    async def stop(self):
        """Stop Telegram bot gracefully."""
        try:
            if self._polling_task:
                self._polling_task.cancel()
            if self._use_ptb and self.application:
                await self.application.stop()
                await self.application.shutdown()
            await self._close_http_client()
            logger.info("Telegram controller stopped.")
        except Exception:
            logger.exception("Error stopping Telegram bot")

    # ----------------------------------------------------------------
    # Messaging helpers
    # ----------------------------------------------------------------
    async def send_message(self, chat_id: int, text: str) -> bool:
        if self._use_ptb and self.application:
            try:
                await self.application.bot.send_message(chat_id=chat_id, text=text)
                return True
            except Exception:
                logger.exception("PTB send_message failed")
        try:
            self._ensure_http_client()
            await self._http_client.post(f"{self._api_base}/sendMessage", json={"chat_id": chat_id, "text": text})
            return True
        except Exception:
            logger.exception("HTTP send_message failed")
            return False

    async def send_document(self, chat_id: int, file_path: str) -> bool:
        if self._use_ptb and self.application:
            try:
                with open(file_path, "rb") as f:
                    await self.application.bot.send_document(chat_id=chat_id, document=f)
                return True
            except Exception:
                logger.exception("PTB send_document failed")
        try:
            self._ensure_http_client()
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f, "application/octet-stream")}
                await self._http_client.post(f"{self._api_base}/sendDocument", files=files, data={"chat_id": str(chat_id)})
            return True
        except Exception:
            logger.exception("HTTP send_document failed")
            return False

    async def _reply(self, update, text: str):
        try:
            if self._use_ptb and update and getattr(update, "message", None):
                await update.message.reply_text(text)
            else:
                logger.info("[Telegram Reply] %s", text)
        except Exception:
            logger.exception("Reply failed")