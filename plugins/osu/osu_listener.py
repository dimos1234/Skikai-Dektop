import websocket
import json
import socket
import time
import threading

# --- UDP SETUP ---
SKIKAI_HOST = '127.0.0.1'
SKIKAI_PORT = 5007
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_sensory_event(event_text):
    payload = json.dumps({
        "type": "GAME_EVENT",
        "app": "osu!",
        "event": event_text
    })
    try:
        udp_sock.sendto(payload.encode('utf-8'), (SKIKAI_HOST, SKIKAI_PORT))
        print(f"[Sent to Skikai]: {event_text}")
    except Exception as e:
        print(f"[UDP Send Error]: {e}")

# State tracking to prevent spam
last_state = 0
last_misses = 0
last_combo = 0
song_name = ""

def on_message(ws, message):
    global last_state, last_misses, last_combo, song_name
    
    try:
        data = json.loads(message)
        
        # Depending on gosumemory vs StreamCompanion, the JSON structure might vary.
        # This assumes standard gosumemory output format.
        menu = data.get('menu', {})
        gameplay = data.get('gameplay', {})
        
        current_state = menu.get('state', 0)
        bm_info = menu.get('bm', {})
        current_song = bm_info.get('metadata', {}).get('title', 'a song')
        
        hits = gameplay.get('hits', {})
        misses = hits.get('0', 0)
        combo = gameplay.get('combo', {}).get('current', 0)
        
        # State changed (e.g. Menu -> Playing)
        if current_state != last_state:
            if current_state == 2: # Playing state in gosumemory
                send_sensory_event(f"Adam just started playing the map '{current_song}' in osu!mania.")
                song_name = current_song
                last_misses = 0
                last_combo = 0
            elif current_state == 7: # Results screen
                acc = gameplay.get('accuracy', 0)
                send_sensory_event(f"Adam just finished playing '{song_name}' with an accuracy of {acc}%.")
            
            last_state = current_state

        # Playing logic
        if current_state == 2:
            # Combo breaking
            if combo == 0 and last_combo > 50:
                send_sensory_event(f"Adam just broke his combo at {last_combo}x!")
            
            # Missing notes
            if misses > last_misses:
                # Only send a message if they are rapidly missing (e.g. dying on a hard part)
                if misses % 10 == 0: 
                    send_sensory_event(f"Adam is missing a lot! He just hit {misses} misses on this map.")
                last_misses = misses
                
            last_combo = combo
            
    except json.JSONDecodeError:
        pass
    except Exception as e:
        # Ignore minor parsing errors as the websocket spams 10 times a second
        pass

def on_error(ws, error):
    print(f"[osu! Listener Error]: {error}")

def on_close(ws, close_status_code, close_msg):
    print("[osu! Listener Closed] Retrying in 5 seconds...")
    time.sleep(5)
    connect_to_osu()

def on_open(ws):
    print("✅ [osu! Listener Connected] Monitoring gosumemory on ws://localhost:24050/ws")

def connect_to_osu():
    ws = websocket.WebSocketApp("ws://localhost:24050/ws",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    print("Starting osu! Background Listener...")
    print("Make sure 'gosumemory' or an equivalent data extractor is running!")
    connect_to_osu()
