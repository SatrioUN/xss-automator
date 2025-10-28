import asyncio
from poc_formatter import format_finding

def is_valid_finding(finding: dict, min_confidence: int = 70) -> bool:
    confidence = int(finding.get("confidence", 0) or 0)
    if confidence < min_confidence:
        return False
    evidence = finding.get("evidence", {})
    marker = finding.get("marker") or ""
    snippet = evidence.get("snippet") or ""
    response_text = finding.get("meta", {}).get("response_text") or ""
    if marker and marker not in snippet and marker not in response_text:
        return False
    return True

async def notify_finding(bot, chat_id, finding, min_confidence=70):
    if not is_valid_finding(finding, min_confidence):
        return
    message = format_finding(finding)
    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        print(f"[!] Failed to send Telegram message: {e}")

async def notify_all(bot, chat_ids, findings, min_confidence=70):
    for finding in findings:
        for chat_id in chat_ids:
            await notify_finding(bot, chat_id, finding, min_confidence=min_confidence)