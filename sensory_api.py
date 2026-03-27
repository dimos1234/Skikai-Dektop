import socket
import json
import time
import threading
import queue
import config

sensory_events_queue = queue.Queue()

def sensory_api_thread():
    """
    Listens for JSON packets on the sensory UDP port.
    These are high-priority game states, web browser events, or script triggers.
    """
    UDP_IP = config.HOST
    UDP_PORT = config.ports.sensory
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"[System: Sensory API online. Listening for game/web events on UDP {UDP_PORT}]")
    
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            payload = json.loads(data.decode('utf-8'))
            
            # Expected format: {"type": "GAME_EVENT", "app": "Minecraft", "event": "Adam died to a Creeper."}
            # Or {"type": "YOUTUBE_WATCH", "video_id": "...", "transcript_chunk": "..."}
            sensory_events_queue.put(payload)
            
        except json.JSONDecodeError:
            print("[Sensory API: Received invalid JSON payload]")
        except Exception as e:
            print(f"[Sensory API Error: {e}]")
            time.sleep(1)

# Start the listener immediately upon import
threading.Thread(target=sensory_api_thread, daemon=True).start()

def get_next_sensory_event():
    """Returns the next event, or None if empty."""
    try:
        return sensory_events_queue.get_nowait()
    except queue.Empty:
        return None
