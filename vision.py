import os
import base64
import mss
import mss.tools
import time
import threading
import requests
import math
import queue
from collections import deque
from io import BytesIO
from PIL import Image, ImageChops, ImageStat

# --- GLOBAL MEMORY STATES ---
# Short-term rolling buffer (The last 10 things she saw)
visual_short_term_memory = deque(maxlen=10)

# Long-term alert queue (main.py will grab these and put them in ChromaDB)
important_visual_events = queue.Queue()

# For the Heartbeat's instant check
latest_description = ""
last_raw_image = None
# ----------------------------

def get_rms_difference(img1, img2):
    """Calculates the root-mean-square difference between two frames. Blazing fast math."""
    if img1 is None or img2 is None:
        return 999.0
    
    # Must be the same size to compare
    if img1.size != img2.size:
        return 999.0
        
    diff = ImageChops.difference(img1, img2)
    stat = ImageStat.Stat(diff)
    rms = math.sqrt(sum(n**2 for n in stat.mean) / len(stat.mean))
    return rms

def _vision_worker():
    global latest_description, last_raw_image
    
    print("\n[Vision: Skikai's Background Vision & Memory Thread Initialized.]")
    
    # Sensitivity: 5.0 ignores a blinking cursor but catches scene changes.
    SENSITIVITY_THRESHOLD = 15.0 
    
    # Target URL for Ollama on the MacBook
    mac_vision_url = os.environ.get("MAC_OLLAMA_URL")

    while True:
        try:
            # 💥 THE DYNAMIC THROTTLE 💥
            # Record start time so we can calculate how long the Mac took to 'think'
            start_time = time.time()
            
            with mss.mss() as sct:
                # Grabs Monitor 1
                monitor = sct.monitors[1] 
                sct_img = sct.grab(monitor)
                
                # Convert raw pixels directly to RAM image (Pillow)
                current_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                # Downscale to 720p to save bandwidth/VRAM
                current_img.thumbnail((1280, 720)) 
                
            # --- THE DELTA CHECK ---
            delta = get_rms_difference(last_raw_image, current_img)
            
            if delta < SENSITIVITY_THRESHOLD:
                # Screen is static. Skip the API call to save Mac power.
                time.sleep(0.5)
                continue
                
            # Screen changed! Encode for the Mac
            last_raw_image = current_img
            buffer = BytesIO()
            current_img.save(buffer, format="JPEG", quality=50) 
            base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # --- THE MEMORY EVALUATOR ---
            vision_prompt = """Describe the contents of this computer screen in one short sentence. 
            If there is a major event or change happening on the screen that is worth commenting on, you MUST start your sentence with [IMPORTANT]. Otherwise, just describe the app or video playing or whatever else is happening on the screen."""

            payload = {
                "model": "moondream",
                "prompt": vision_prompt,
                "images": [base64_image],
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 1024
                }
            }

            try:
                # Using a 10s timeout to allow for high memory pressure on the MacBook
                response = requests.post(mac_vision_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    # Safely extract the response using .get() to avoid KeyErrors
                    description = response.json().get("response", "").strip()
                else:
                    print(f"[Vision: Mac returned Error {response.status_code}]")
                    description = ""
                    time.sleep(1)
                    continue
                    
            except requests.exceptions.Timeout:
                print("[Vision: Mac timed out. Backing off for 2s...]")
                time.sleep(2)
                continue
            except requests.exceptions.ConnectionError:
                print("[Vision: Connection Refused. Is Ollama running on the Mac with OLLAMA_HOST=0.0.0.0?]")
                time.sleep(5)
                continue
            
            # If the description is empty for whatever reason, skip the routing
            if not description:
                continue

            # --- MEMORY ROUTING ---
            # 1. Update her instant reaction state
            latest_description = description.replace("[IMPORTANT]", "").strip()
            
            # 2. Add to short term sliding memory (with a timestamp)
            memory_entry = f"[{time.strftime('%H:%M:%S')}] {latest_description}"
            visual_short_term_memory.append(memory_entry)
            
            # 3. If it's a core memory, queue it for main.py to save to ChromaDB
            if "[IMPORTANT]" in description:
                important_visual_events.put(memory_entry)
                print(f"\n[Memory: VISUAL CORE MEMORY LOGGED: {latest_description}]")

            # 💥 BACKPRESSURE CALCULATION 💥
            # Ensure we don't spam the Mac faster than it can process.
            # We target ~1 frame per second baseline, but wait if the Mac is slow.
            elapsed = time.time() - start_time
            sleep_time = max(0.2, 1.0 - elapsed) 
            time.sleep(sleep_time)

        except Exception as e:
            print(f"\n[CRITICAL Background Vision Error: {e}]")
            time.sleep(5) 

# Fire up the eye in a daemon thread
threading.Thread(target=_vision_worker, daemon=True).start()

def get_screen_description():
    """Returns the absolute latest thing she saw instantly. Non-blocking."""
    return latest_description

def get_visual_context():
    """
    Returns the narrative history of the last 10 vision captures.
    Use this in your system prompt to give Skikai 'Temporal Awareness'.
    """
    if not visual_short_term_memory:
        return "No recent visual history."
    return "\nRecent Visual History:\n" + "\n".join(visual_short_term_memory)