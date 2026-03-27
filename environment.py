import requests
import threading
import time
from datetime import datetime
import capabilities

current_weather = "Unknown"
last_weather_fetch = 0

def fetch_weather():
    global current_weather, last_weather_fetch
    if not capabilities.weather:
        return
    while True:
        try:
            resp = requests.get('https://wttr.in/?format=%C+%t', timeout=5)
            if resp.status_code == 200:
                current_weather = resp.text.strip()
            last_weather_fetch = time.time()
        except:
            pass
        time.sleep(1800)

threading.Thread(target=fetch_weather, daemon=True).start()

def get_active_window():
    return capabilities.get_active_window()

def get_environment_context():
    global current_weather
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    day_str = now.strftime("%A")
    
    # We can inject some natural thoughts based on time
    hour = now.hour
    time_note = ""
    if hour >= 2 and hour < 6:
        time_note = "late-night"
    elif hour >= 6 and hour < 11:
        time_note = "morning"
    
    window = get_active_window()
    if window and len(window) > 60:
        window = window[:60]
    
    note = f" {time_note}" if time_note else ""
    wx = current_weather if current_weather else "Unknown"
    win = window if window else "Unknown"
    return f"t={time_str} {day_str}{note} | wx={wx} | win={win}"
