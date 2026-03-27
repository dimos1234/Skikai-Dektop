import os
import requests
import urllib.parse
import pygame
import time
import threading
import queue
import uuid
import websocket
import re
import socket
import config
from animator import classify_action

pygame.mixer.init()

TTS_URL = f"http://{config.HOST}:{config.ports.tts}/tts"
REF_AUDIO = config.paths.ref_audio
REF_TEXT = "to be able to hear a vague prophecy in my dreams and move forward under its guidance"
REF_LANG = "en"

tts_queue = queue.Queue()
playback_queue = queue.Queue()

# 💥 THE GLOBAL KILL SWITCH 💥
interrupt_flag = threading.Event()

def trigger_warudo_action(action_text):
    """Sends the raw text to the Director, gets the clean trigger, and fires it to Warudo."""
    print(f"\n[Director: Analyzing action -> '*{action_text}*']...")
    
    # Ask the cloud brain to classify it
    clean_action = classify_action(action_text)
    
    if not clean_action or clean_action == "neutral":
        print("[Director: Action was neutral or unclassified.]")
        return 
        
    WS_URL = f"ws://{config.HOST}:{config.ports.warudo}"
    
    try:
        ws = websocket.create_connection(WS_URL, timeout=1)
        ws.send(clean_action)
        ws.close()
        print(f"[System: Animator translated to -> {clean_action}]")
    except Exception as e:
        print(f"[WebSocket Error: Ensure Warudo is open and port is 19190]")

def stop_talking():
    """Immediately stops all audio, flushes queues, and kills the generator."""
    interrupt_flag.set()
    pygame.mixer.music.stop()
    
    # Empty the assembly line
    while not tts_queue.empty():
        try: tts_queue.get_nowait(); tts_queue.task_done()
        except: pass
    while not playback_queue.empty():
        try: playback_queue.get_nowait(); playback_queue.task_done()
        except: pass

# 💥 FIX 6: The safe deletion loop
def cleanup(filepath):
    """Forces deletion of the temp file, retrying if Windows still has it locked."""
    for _ in range(5):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            break
        except PermissionError:
            time.sleep(0.1) # Wait for pygame to let go of the file handle

def tts_worker():
    while True:
        item = tts_queue.get()
        if item is None: break
        
        try:
            # If interrupted, drop the sentence and move on
            if interrupt_flag.is_set():
                tts_queue.task_done()
                continue
                
            text, index = item
            
            # 1. First, strip out anything between asterisks just in case the chunker missed it
            clean_text = re.sub(r'\*.*?\*', '', text)
            # 2. Strip weird formatting
            clean_text = clean_text.replace('"', '').replace('\n', '. ').replace(' - ', ',').replace('-', ' ')
            # 3. Nuke any remaining foreign characters/emojis
            clean_text = re.sub(r'[^\w\s\.,!\?\'\:]', '', clean_text)
            
            if clean_text.strip():
                safe_text = urllib.parse.quote(clean_text.strip())
                safe_ref_text = urllib.parse.quote(REF_TEXT)
                url = f"{TTS_URL}?text={safe_text}&text_lang=en&ref_audio_path={REF_AUDIO}&prompt_text={safe_ref_text}&prompt_lang={REF_LANG}"
                
                try:
                    response = requests.get(url)
                    if response.status_code == 200 and not interrupt_flag.is_set():
                        # Generate a completely unique filename for every single chunk
                        unique_id = uuid.uuid4().hex[:8]
                        filename = f"temp_skikai_{index}_{unique_id}.wav"
                        
                        with open(filename, "wb") as f:
                            f.write(response.content)
                        playback_queue.put(filename)
                        
                    # 💥 THE REVEAL: Print exactly why the API rejected the sentence!
                    elif response.status_code != 200:
                        print(f"\n[TTS API Error: Status {response.status_code} on text: '{clean_text}']")
                        
                except requests.exceptions.ConnectionError:
                    print("\n[TTS Connection Error: Is the API running?]")
        except Exception as e:
            print(f"[TTS Worker Error: {e}]")
        finally:
            tts_queue.task_done()

is_speaking = False

def playback_worker():
    global is_speaking 
    
    # Setup a dedicated UDP socket to send the file to Discord VC
    discord_vc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        filepath = playback_queue.get()
        if filepath is None: break
        
        try:
            if interrupt_flag.is_set():
                cleanup(filepath)
                playback_queue.task_done()
                continue
                
            # --- THE CHANGE ---
            is_speaking = True 
            
            # Tell the Discord Bot to stream this exact file into VC!
            abs_path = os.path.abspath(filepath)
            try:
                discord_vc_sock.sendto(f"[DISCORD_VOICE] {abs_path}".encode('utf-8'), (config.HOST, config.ports.discord_out))
            except Exception as udp_e:
                print(f"[UDP Send Error in Playback: {udp_e}]")
            
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if interrupt_flag.is_set():
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)
                
            pygame.mixer.music.unload()
            is_speaking = False 
            # ------------------
    
            cleanup(filepath)
        except Exception as e:
            print(f"[Playback Worker Error: {e}]")
            is_speaking = False
        finally:
            playback_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()
threading.Thread(target=playback_worker, daemon=True).start()

def _idle_sway_loop():
    """Periodically send an 'idle' trigger to Warudo so the model sways even in silence."""
    WS_URL = f"ws://{config.HOST}:{config.ports.warudo}"
    while True:
        time.sleep(25)
        if not is_speaking:
            try:
                ws = websocket.create_connection(WS_URL, timeout=1)
                ws.send("idle")
                ws.close()
            except Exception:
                pass

threading.Thread(target=_idle_sway_loop, daemon=True).start()

def speak(text):
    interrupt_flag.clear()
    tts_queue.put((text, 999))
    # Check unfinished tasks instead of empty() to bridge the download gap
    while tts_queue.unfinished_tasks > 0 or playback_queue.unfinished_tasks > 0 or is_speaking or pygame.mixer.music.get_busy():
        if interrupt_flag.is_set():
            break
        time.sleep(0.1)

def speak_stream(text_generator):
    interrupt_flag.clear()
    sentence_buffer = ""
    action_buffer = ""
    in_action = False
    
    hard_enders = ['.', '!', '?', '\n']
    soft_enders = [',', ':', ';'] 
    
    sentence_count = 0
    word_count = 0

    try:
        for chunk in text_generator:
            if interrupt_flag.is_set():
                break 
                
            for char in chunk:
                if char == '*':
                    if in_action:
                        in_action = False
                        if action_buffer.strip():
                            threading.Thread(target=trigger_warudo_action, args=(action_buffer.strip(),)).start()
                        action_buffer = "" 
                    else:
                        in_action = True
                    continue 

                if in_action:
                    action_buffer += char
                else:
                    sentence_buffer += char
                    
                    if char == ' ' or char == '\n':
                        word_count += 1
                    
                    # 💥 THE LOOK-BEHIND CHUNKER
                    is_newline = (char == '\n')
                    # Only chunk if the current char is a space AND the previous char was punctuation (preserves "...")
                    is_punc_space = (len(sentence_buffer) > 1 and char == ' ' and sentence_buffer[-2] in hard_enders + soft_enders)
                    
                    if is_newline or is_punc_space:
                        # Delay soft stops (commas) so she speaks in longer, more natural phrases
                        is_soft = is_punc_space and sentence_buffer[-2] in soft_enders
                        if not is_soft or word_count >= 3:
                            clean_text = sentence_buffer.strip()
                            
                            # 💥 REGEX FAILSAFE: Only send to TTS if there are actual letters/numbers!
                            if re.search(r'[a-zA-Z0-9]', clean_text):
                                tts_queue.put((clean_text, sentence_count))
                                sentence_count += 1
                                
                            sentence_buffer = "" 
                            word_count = 0 
                            
                    # Gracefully break up massive run-on sentences (20+ words)
                    elif word_count >= 20 and char == ' ':
                        # 💥 Inject a comma so the TTS engine knows to inflect a pause/breath!
                        clean_text = sentence_buffer.strip() + ","
                        if re.search(r'[a-zA-Z0-9]', clean_text):
                            tts_queue.put((clean_text, sentence_count))
                            sentence_count += 1
                        sentence_buffer = ""
                        word_count = 0
                
        # Catch whatever is left at the very end of her generation
        final_text = sentence_buffer.strip()
        if final_text and not interrupt_flag.is_set():
            if re.search(r'[a-zA-Z0-9]', final_text):
                tts_queue.put((final_text, sentence_count))
            
        # Check unfinished tasks instead of empty() to bridge the download gap
        while tts_queue.unfinished_tasks > 0 or playback_queue.unfinished_tasks > 0 or is_speaking or pygame.mixer.music.get_busy():
            if interrupt_flag.is_set():
                break
            time.sleep(0.1)
            
    except Exception as e:
        print(f"\n[Stream Error: {e}]")