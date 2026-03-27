import os
import queue
import threading
import speech_recognition as sr
from groq import Groq

client = Groq()

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False 
recognizer.energy_threshold = 400           
recognizer.pause_threshold = 0.7

user_input_queue = queue.Queue()
on_interrupt = None 

# Add this near the top of ears.py
is_receiving_audio = False

def _listen_loop():
    global is_receiving_audio
    try:
        with sr.Microphone() as source:
            print("\n[🎙️ Skikai's Ears are online. Speak anytime to interrupt.]")
            while True:
                try:
                    # She is listening, but hasn't heard anything yet
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=30)
                    
                    # THE CHANGE: If we pass the line above, you made a noise!
                    is_receiving_audio = True 
                    print("\n[🎙️ Audio caught! Transcribing via Groq...]", end="", flush=True)
                    
                    # 💥 THE FIX: Nuke the queue! Delete any old prompts so she only answers the newest one.
                    with user_input_queue.mutex:
                        user_input_queue.queue.clear()
                    
                    # Trigger the interrupt immediately so she shuts up BEFORE Groq processes
                    if on_interrupt:
                        on_interrupt()
                        
                    temp_file = "temp_mic.wav"
                    with open(temp_file, "wb") as f:
                        f.write(audio.get_wav_data())
                    
                    with open(temp_file, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            file=(temp_file, audio_file.read()),
                            model="whisper-large-v3-turbo", 
                            response_format="text",
                            language="en"
                        )
                    
                    text = transcription.strip()
                    
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        
                    hallucinations = [
                        "thank you", "thanks", "thanks for watching", 
                        "thank you for watching", "bye", "you", "please subscribe"
                    ]
                    cleaned_check = text.lower().replace(".", "").replace(",", "").strip()
                    
                    if cleaned_check in hallucinations:
                        text = "" 
                        
                    if text:
                        user_input_queue.put(text)
                    else:
                        print("\r" + " " * 50 + "\r", end="", flush=True)
                        
                    # THE CHANGE: We are done processing, she is back to idle
                    is_receiving_audio = False 
                        
                except sr.WaitTimeoutError:
                    is_receiving_audio = False 
                    continue
                except Exception as inner_e:
                    is_receiving_audio = False 
                    print(f"\n[Mic Processing Error: {inner_e}]")
                    
    except Exception as outer_e:
        print(f"\n[CRITICAL HARDWARE ERROR: PyAudio could not open your microphone! Details: {outer_e}]")

threading.Thread(target=_listen_loop, daemon=True).start()

def get_next_input():
    return user_input_queue.get()