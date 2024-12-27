from plyer import notification
import threading
from datetime import datetime, timedelta
import time
import pyttsx3  # For voice notifications

def set_alarm(med_name, time_str):
    """Sets a system alarm for the medication reminder."""
    now = datetime.now()
    reminder_time = datetime.strptime(time_str, "%H:%M")
    if reminder_time < now:
        reminder_time += timedelta(days=1)
    delay = (reminder_time - now).total_seconds()

    def alarm_thread():
        time.sleep(delay)
        notification.notify(
            title="Medication Reminder",
            message=f"Time to take {med_name}",
            timeout=10
        )
        pyttsx3.speak(f"Time to take {med_name}")

    threading.Thread(target=alarm_thread, daemon=True).start()

def check_stock_alert(med_name, stock):
    """Check if stock is low and alert the user."""
    if stock <= 2:
        notification.notify(
            title="Low Stock Alert",
            message=f"Stock for {med_name} is low. Please refill.",
            timeout=10
        )
        pyttsx3.speak(f"Stock for {med_name} is low. Please refill.")

def add_to_history(med_name):
    """Logs the medication history."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"Name": med_name, "Taken At": now}
