import time
import requests
import subprocess
import os
import logging
import json
from datetime import datetime, timedelta

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

# Script configurations
SCRIPTS = {
    "backup": {
        "path": "scripts/backup.sh",
        "description": "Backup",
        "schedule": {
            "day_of_week": [1],  # Tuesday (0=Monday, 1=Tuesday, etc.)
            "hour": 0,           # 12 AM (integer)
            "minute": 0,         # 0 minutes (integer)
            "weeks_of_month": [1],  # Run on 1st Tuesday of the month
            "months_of_year": [1, 4, 7, 10]  # Run in January, April, July, October
        }
    }
}

# State file path
STATE_FILE = "data/last_runs.json"

def load_state():
    """Load the last run times from the state file"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading state file: {e}")
    return {}

def save_state(state):
    """Save the last run times to the state file"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Error saving state file: {e}")

# Load initial state
last_runs = load_state()

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def run_script(script_name):
    """Run a script and send the result to Telegram"""
    if script_name not in SCRIPTS:
        send_message(CHAT_ID, f"❌ Unknown script: {script_name}")
        return

    script = SCRIPTS[script_name]
    try:
        output = subprocess.getoutput(script["path"])
        send_message(CHAT_ID, f"🔄 {script['description']}\nResult:\n{output}")
    except Exception as e:
        send_message(CHAT_ID, f"❌ Error running {script['description']}:\n{str(e)}")

def get_week_of_month(now):
    """Get which week of the month the current date is (1st, 2nd, 3rd, etc.)"""
    first_day = now.replace(day=1)
    days_ahead = (now.weekday() - first_day.weekday() + 7) % 7
    first_occurrence = first_day + timedelta(days=days_ahead)
    return (now.day - first_occurrence.day) // 7 + 1

def should_run_script(script_name):
    """Check if a script should be run based on its schedule"""
    if script_name not in SCRIPTS:
        return False

    script = SCRIPTS[script_name]
    schedule = script["schedule"]
    
    # Get current time
    now = datetime.now()
    
    # Check if it's the right day, hour, and minute
    if ((not schedule["day_of_week"] or now.weekday() in schedule["day_of_week"]) and
        now.hour == schedule["hour"] and
        now.minute == schedule["minute"]):
        
        # Check if we haven't run it in the last minute
        last_run = last_runs.get(script_name, 0)
        if now.timestamp() - last_run > 60:  # 60 seconds cooldown
            # Check if it's the right month
            if schedule["months_of_year"] and now.month not in schedule["months_of_year"]:
                return False
            
            # Check if it's the right week of the month
            if schedule["weeks_of_month"]:
                current_week = get_week_of_month(now)
                if current_week not in schedule["weeks_of_month"]:
                    return False
            
            last_runs[script_name] = now.timestamp()
            save_state(last_runs)  # Save state after updating
            return True
    
    return False

def format_schedule_display(schedule):
    """Format the schedule for display in the /scripts command"""
    parts = []
    
    # Format days
    if not schedule["day_of_week"]:
        parts.append("Every day")
    else:
        days = [['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][d] for d in schedule["day_of_week"]]
        parts.append(f"Every {', '.join(days)}")
    
    # Format time (required)
    parts.append(f"at {schedule['hour']:02d}:{schedule['minute']:02d}")
    
    # Format weeks of month
    if not schedule["weeks_of_month"]:
        parts.append("(every week of month)")
    else:
        weeks = [f"{w}{'th' if w not in [1,2,3] else ['st','nd','rd'][w-1]}" for w in schedule["weeks_of_month"]]
        parts.append(f"({', '.join(weeks)} of month)")
    
    # Format months
    if not schedule["months_of_year"]:
        parts.append("in every month")
    else:
        months = [datetime(2000, m, 1).strftime('%B') for m in schedule["months_of_year"]]
        parts.append(f"in {', '.join(months)}")
    
    return " ".join(parts)

def handle_update(update):
    logger.info(f"Update: {update}")
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        if chat_id != CHAT_ID:
            logger.error(f"Unauthorized access from chat_id: {chat_id}, CHAT_ID: {CHAT_ID}")
            return
        
        # Handle commands
        if text == "/backup":
            run_script("backup")
        elif text == "/scripts":
            script_list = "\n".join([
                f"- {name}: {script['description']} ({format_schedule_display(script['schedule'])})"
                for name, script in SCRIPTS.items()
            ])
            send_message(chat_id, f"📋 Available Scripts:\n{script_list}")
        else:
            send_message(chat_id, "Unknown command. Try /backup or /scripts")

def run_polling():
    offset = None
    while True:
        try:
            # Check for scheduled tasks
            for script_name in SCRIPTS:
                if should_run_script(script_name):
                    logger.info(f"Running scheduled task: {script_name}")
                    run_script(script_name)

            # Check for Telegram updates
            res = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 5, "offset": offset},
                timeout=10
            )
            res.raise_for_status()
            updates = res.json().get("result", [])
            for update in updates:
                handle_update(update)
                offset = update["update_id"] + 1
        except requests.exceptions.RequestException as e:
            logger.error(f"[Polling error] {e}")
        except Exception as e:
            logger.error(f"[Unknown error] {e}")
        time.sleep(5)  # Poll every 5 seconds

if __name__ == "__main__":
    try:
        logger.info("Starting Telegram bot polling...")
        run_polling()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
