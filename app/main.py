import time
import requests
import subprocess
import os

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def handle_update(update):
    if "message" in update:
        print("Test log")
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        if chat_id != CHAT_ID:
            print(f"Unauthorized access from chat_id: {chat_id}")
            return
        if text == "/backup":
            output = subprocess.getoutput("scripts/backup.sh")
            send_message(chat_id, f"执行结果：\n{output}")
        else:
            send_message(chat_id, "未知指令。试试 /run_example")


def run_polling():
    offset = None
    while True:
        try:
            res = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 60, "offset": offset},
                timeout=65  # extra safe to avoid stuck
            )
            res.raise_for_status()  # Throw error if response_code!=200
            updates = res.json().get("result", [])
            for update in updates:
                handle_update(update)
                offset = update["update_id"] + 1
        except requests.exceptions.RequestException as e:
            print(f"[Polling error] {e}")
        except Exception as e:
            print(f"[Unknown error] {e}")
        time.sleep(3)

if __name__ == "__main__":
    run_polling()
