import time
import requests
import subprocess
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID_STR = os.environ.get("TELEGRAM_CHAT_ID")
try:
    CHAT_ID = int(CHAT_ID_STR) if CHAT_ID_STR else None
    if CHAT_ID is None:
        logger.error("TELEGRAM_CHAT_ID environment variable is not set")
        raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")
except ValueError as e:
    logger.error(f"Invalid TELEGRAM_CHAT_ID format: {CHAT_ID_STR}. Must be a valid integer.")
    raise

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def handle_update(update):
    logger.info(f"Update: {update}")
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        if chat_id != CHAT_ID:
            logger.error(f"Unauthorized access from chat_id: {chat_id}, CHAT_ID: {CHAT_ID}")
            return
        if text == "/backup":
            output = subprocess.getoutput("scripts/backup.sh")
            send_message(chat_id, f"Result:\n{output}")
        else:
            send_message(chat_id, "Unknown command. Try /backup")

def run_polling():
    offset = None
    while True:
        try:
            res = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 5, "offset": offset},
                timeout=10  # extra safe to avoid stuck
            )
            res.raise_for_status()  # Throw error if response_code!=200
            updates = res.json().get("result", [])
            for update in updates:
                handle_update(update)
                offset = update["update_id"] + 1
        except requests.exceptions.RequestException as e:
            logger.error(f"[Polling error] {e}")
        except Exception as e:
            logger.error(f"[Unknown error] {e}")
        time.sleep(3)

if __name__ == "__main__":
    try:
        logger.info("Starting Telegram bot polling...")
        run_polling()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
