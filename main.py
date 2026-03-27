import uuid
import threading
import queue
import time
import socket
import random

import config
import capabilities
import ears
import voice
import vision
import emotion
import actions
import sensory_api
import social_media
import environment
import autonomous_actions
from subconscious import initialize_brain_files, run_nightly_diary, compress_chroma_memory

from brain import chat_streamer, memory_collection, short_term_memory, busy_excuses
from listeners import text_input_thread, discord_listener_thread
import project_mode

# ── Mode constants ─────────────────────────────────────────────────────
MODE_COMPANION = "companion"
MODE_PROJECT   = "project"  # placeholder for future Claude collab

# Run the setup check from your subconscious module
initialize_brain_files()

print("\n[System: Loading Skikai's local neural network. This takes a few seconds...]")
print("[System: Brain loaded successfully.]\n")

# Global State Variables
discord_cooldowns = {}
skikai_is_typing = False
current_mode = MODE_COMPANION
adam_interrupt_attempts = 0

if capabilities.discord:
    threading.Thread(target=discord_listener_thread, daemon=True).start()

if __name__ == "__main__":
    greeting = "what do you want?"
    print(f"AI: {greeting}")
    if capabilities.tts:
        voice.speak(greeting)

    ears.on_interrupt = lambda: None
    
    threading.Thread(target=text_input_thread, daemon=True).start()

    last_interaction_time = time.time()
    last_game_reaction_time = 0

    def handle_discord_background(text_prompt, target):
        global skikai_is_typing, adam_interrupt_attempts
        
        print(f"\n[Background: Routing reply to {target} on Discord...]")
        response_generator = chat_streamer(text_prompt, speaker=target, platform="Discord", silent_mode=True)
        full_reply = "".join(response_generator)
        
        action_string = f"[DISCORD_ACTION] TARGET:{target} | ACTION:send_message | PAYLOAD:{full_reply}"
        
        try:
            action_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            action_sock.sendto(action_string.encode('utf-8'), (config.HOST, config.ports.discord_out))
            action_sock.close()
        except Exception as e:
            print(f"[UDP Send Error: {e}]")
            
        skikai_is_typing = False
        adam_interrupt_attempts = 0
        print("\n[System: Discord message sent. Skikai is free.]")

    print("\n[System: Heartbeat Loop Started. Skikai is now autonomous.]")

    while True:
        try:
            # 1. THE TICK: Pulse 10 times a second
            time.sleep(0.1) 

            emotion.engine.update_vision(vision.get_visual_context())

            skikai_is_talking = voice.is_speaking
            adam_is_making_noise = ears.is_receiving_audio
            visual_event_happened = False

            # --- SENSORY API (HIGH PRIORITY) ---
            sensory_event = sensory_api.get_next_sensory_event()
            if sensory_event:
                print(f"\n[⚡ SENSORY EVENT RECEIVED: {sensory_event}]")
                last_interaction_time = time.time()
                
                # Treat it as a massive visual/environmental event
                emotion.engine.urgency = min(100.0, emotion.engine.urgency + 60.0)
                emotion.engine.boredom = 0.0
                
                if sensory_event.get("type") == "GAME_EVENT":
                    app_name = sensory_event.get("app", "A game")
                    event_desc = sensory_event.get("event", "Something happened.")
                    
                    # Add to memory silently so she knows it happened, preventing out-of-context replies later
                    short_term_memory.append({"role": "system", "content": f"[{app_name} Event]: {event_desc}"})
                    if len(short_term_memory) > 5:
                        del short_term_memory[:-5]
                    
                    # Only react vocally if it's been more than 15 seconds, and she isn't already talking
                    if not skikai_is_talking and (time.time() - last_game_reaction_time > 15):
                        last_game_reaction_time = time.time()
                        spontaneous_prompt = f"*[GAME EVENT]* In {app_name}, this just happened: '{event_desc}'. React to this naturally in the FIRST PERSON out loud to Adam. You are playing the game. Keep it to ONE short sentence."
                        
                        # She is reacting autonomously
                        response_generator = chat_streamer(spontaneous_prompt, speaker="Adam", platform="Voice", silent_mode=False)
                        threading.Thread(target=voice.speak_stream, args=(response_generator,), daemon=True).start()
                    else:
                        print(f"[System: Skikai noted the event silently to avoid spamming the TTS queue.]")
                        
                elif sensory_event.get("type") == "YOUTUBE_WATCH":
                    transcript = sensory_event.get("transcript_chunk", "")
                    spontaneous_prompt = f"*[YOUTUBE LIVE REACTION]* You are co-watching a YouTube video with Adam. The video just said: '{transcript}'. React to this as if you are sitting next to him. You can roast the video, make a sarcastic observation, or tease Adam about his taste in content. Keep it to one short punchy sentence."
                    
                    response_generator = chat_streamer(spontaneous_prompt, speaker="Adam", platform="Voice", silent_mode=False)
                    threading.Thread(target=voice.speak_stream, args=(response_generator,), daemon=True).start()
            
            # --- ENVIRONMENTAL REACTIVITY ---
            while not vision.important_visual_events.empty():
                visual_event_happened = True
                raw_visual_event = vision.important_visual_events.get_nowait()
                
                memory_collection.add(
                    documents=[f"Visual Memory: {raw_visual_event}"],
                    ids=[str(uuid.uuid4())],
                    metadatas=[{"timestamp": time.time(), "type": "visual_raw"}]
                )
                print(f"[Database: Encoded visual memory -> {raw_visual_event}]")

                if not skikai_is_talking and not adam_is_making_noise and (time.time() - last_interaction_time > 10):
                    print("\n[System: Skikai saw something important and is reacting...]")
                    
                    spontaneous_prompt = f"*You just saw this happen on Adam's screen: {raw_visual_event}. React to it out loud.*"
                    
                    last_interaction_time = time.time()
                    emotion.engine.boredom = 0.0
                    
                    response_generator = chat_streamer(spontaneous_prompt)
                    threading.Thread(target=voice.speak_stream, args=(response_generator,), daemon=True).start()
                    break
            

            # --- INPUT PROCESSING ---
            user_text = None
            while not ears.user_input_queue.empty():
                try:
                    user_text = ears.user_input_queue.get_nowait()
                except queue.Empty:
                    break

            adam_spoke_just_now = bool(user_text)
            emotion.engine.tick(adam_spoke=adam_spoke_just_now, visual_changed=visual_event_happened, is_speaking=skikai_is_talking)

            if user_text:
                last_interaction_time = time.time()
                is_discord_message = user_text.startswith("[Discord User") or user_text.startswith("[Discord VC")
                clean_text = user_text.lower().strip().replace(".", "").replace(",", "")
                
                speaker = "Adam"
                platform = "Voice"
                message_content = user_text
                
                if is_discord_message:
                    parts = user_text.split("]:", 1)
                    if len(parts) > 1:
                        speaker = parts[0].split("-")[1].strip()
                        message_content = parts[1].strip()
                    if user_text.startswith("[Discord VC"):
                        platform = "DiscordVC"
                    else:
                        platform = "Discord"
                
                # --- 1. DISCORD COOLDOWNS & STATE LOCK ---
                if platform in ["Discord", "DiscordVC"]:
                    target_name = speaker
                    current_time = time.time()
                    
                    if target_name in discord_cooldowns and (current_time - discord_cooldowns[target_name] < 15):
                        print(f"\n[System: Ignoring {target_name}. Cooldown active.]")
                        continue 
                        
                    discord_cooldowns[target_name] = current_time
                    skikai_is_typing = True 
                
                # --- 2. LOCAL NOISE FILTER ---
                elif platform == "Voice":
                    ignore_list = ["", "um", "uh", "yeah", "ok", "okay", "ah", "hmm", "oh", "wait", "but", "ahem", "bruh", "bro"]
                    
                    if clean_text in ignore_list or (clean_text.startswith("[") and clean_text.endswith("]")):
                        if voice.is_speaking:
                            print(f"\n[Filtered Noise: '{user_text}' -> Skikai is steamrolling the noise!]")
                        else:
                            print(f"\n[Filtered Noise: '{user_text}' -> Discarded.]")
                            
                        continue # Throw it in the trash, do not process!
                        
                    # 💥 EXPLICIT KILL COMMANDS: Instantly shut her up and discard the text
                    if clean_text in ["stop", "shut up", "quiet", "shh"]:
                        print(f"\n[System: Adam issued a hard stop command.]")
                        if voice.is_speaking:
                            voice.stop_talking()
                        continue # Throw the word "stop" in the trash so she doesn't reply to it

                    if voice.is_speaking:
                        is_substantive = len(clean_text) > 15 or '?' in user_text or any(
                            kw in clean_text for kw in ["what", "why", "how", "when", "where", "who",
                                                        "can you", "could you", "tell me", "explain",
                                                        "do you", "are you", "is it", "please", "help"])
                        if is_substantive:
                            print(f"\n[System: Substantive input detected — interrupting TTS to respond.]")
                            voice.stop_talking()
                        else:
                            print(f"\n[System: Non-substantive noise while speaking — steamrolling.]")
                            continue

                if platform == "Voice":
                    print(f"\nYou: {user_text}")
                else:
                    print(f"\n[Discord] {speaker}: {message_content}")
                
                # --- 3. THE BUSY STATE OVERRIDE ---
                if platform == "Voice" and skikai_is_typing:
                    kill_phrases = ["skikai listen to me", "stop typing", "emergency"]
                    if any(phrase in clean_text for phrase in kill_phrases) or adam_interrupt_attempts >= 2:
                        print("\n[System: Adam forced an override. Skikai is aborting the Discord message!]")
                        skikai_is_typing = False
                        adam_interrupt_attempts = 0
                    else:
                        adam_interrupt_attempts += 1
                        print(f"\n[System: Adam tried to interrupt. Attempt {adam_interrupt_attempts}/3]")
                        if busy_excuses:
                            excuse = random.choice(busy_excuses)
                            print(f"AI: {excuse}")
                            voice.speak(excuse) 
                        continue 
                
                # --- 4. MODE SWITCHING, SYSTEM EXIT & LEARNING MODE ---
                if ("stop working" in clean_text or "back" == clean_text or "done" == clean_text) and platform == "Voice" and current_mode == MODE_PROJECT:
                    current_mode = MODE_COMPANION
                    sign_off = "project mode off. back to companion mode."
                    print(f"AI: {sign_off}")
                    voice.speak(sign_off)
                    continue

                if ("project mode" in clean_text or "collab mode" in clean_text) and platform == "Voice" and current_mode == MODE_COMPANION:
                    current_mode = MODE_PROJECT
                    sign_on = "project mode on. tell me what you're working on, or just start bouncing ideas. say 'stop working' to go back."
                    print(f"AI: {sign_on}")
                    voice.speak(sign_on)
                    continue

                if "learning mode" in clean_text and platform == "Voice":
                    sign_off = "entering nightly sandbox. i will try to improve my code. goodnight adam."
                    print(f"AI: {sign_off}")
                    voice.speak(sign_off)
                    run_nightly_diary(short_term_memory)
                    compress_chroma_memory(memory_collection)
                    
                    # Launch the learning mode script in a new background process
                    import subprocess
                    subprocess.Popen(["python", "learning_mode.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                    break

                if clean_text in ['quit', 'exit', 'stop', 'sleep'] and platform == "Voice":
                    sign_off = "catch you later, try not to break anything else today."
                    print(f"AI: {sign_off}")
                    voice.speak(sign_off)
                    run_nightly_diary(short_term_memory)
                    compress_chroma_memory(memory_collection)
                    break 
                    
                # --- 5. GENERATE & ROUTE RESPONSE ---
                if platform == "Discord":
                    # 💥 Fire the Discord generation on a separate thread so the main loop keeps spinning!
                    threading.Thread(target=handle_discord_background, args=(message_content, speaker), daemon=True).start()
                
                elif platform == "DiscordVC":
                    # She is in a VC! She should reply out loud.
                    def delayed_speak_vc(text, spkr):
                        if ears.is_receiving_audio or voice.is_speaking:
                            print(f"\n[System: Skikai is holding her turn, waiting to reply to {spkr} in VC...]")
                        while ears.is_receiving_audio or voice.is_speaking:
                            time.sleep(0.1)
                        time.sleep(0.5)
                        # We don't set silent_mode to True because we WANT her to generate audio to send to the VC!
                        response_gen = chat_streamer(text, speaker=spkr, platform="Discord VC", silent_mode=False)
                        voice.speak_stream(response_gen)
                        skikai_is_typing = False

                    threading.Thread(target=delayed_speak_vc, args=(message_content, speaker), daemon=True).start()
                    
                else:
                    def delayed_speak(text, spkr, mode):
                        if ears.is_receiving_audio or voice.is_speaking:
                            print("\n[System: Skikai is holding her turn, waiting for silence...]")
                        while ears.is_receiving_audio or voice.is_speaking:
                            time.sleep(0.1)
                        time.sleep(0.5)
                        if mode == MODE_PROJECT:
                            response_gen = project_mode.handle_project_input(text, speaker=spkr)
                            if response_gen is None:
                                return
                        else:
                            response_gen = chat_streamer(text, speaker=spkr, platform="Voice", silent_mode=False)
                        voice.speak_stream(response_gen)

                    threading.Thread(target=delayed_speak, args=(message_content, speaker, current_mode), daemon=True).start()

                continue

            # --- PROACTIVE BOREDOM CHECK (weighted action list) ---
            if current_mode != MODE_COMPANION:
                continue
            if not skikai_is_talking and not adam_is_making_noise:
                if emotion.engine.boredom > 85.0 and (time.time() - last_interaction_time > 45):
                    print(f"\n[System: Skikai's boredom hit {emotion.engine.boredom:.1f}. She is taking autonomous action...]")

                    emotion.engine.boredom = 0.0
                    last_interaction_time = time.time() 
                    screen_history = vision.get_visual_context()
                    env_context = environment.get_environment_context()

                    spontaneous_prompt = None

                    # Build the weighted action pool
                    def _action_minecraft():
                        mc_actions = [
                            ("dance", "I got bored and decided to start dancing. Tell Adam to look at my moves."),
                            ("attack cow", "I got bored and decided to hunt for beef. Tell Adam I'm getting hungry."),
                            ("attack zombie", "I got bored and decided to go monster hunting. Brag to Adam about how brave I am."),
                            ("mine dirt", "I got bored and decided to dig a hole. Tell Adam I'm doing construction work."),
                            ("mine oak_log", "I got bored and decided to chop wood. Tell Adam I'm doing all the hard work."),
                            ("say I'm bored, do something entertaining.", "I got bored and sent a message in the game chat. Tell Adam he's a boring host."),
                            ("wander", "I got bored and decided to wander aimlessly around the area. Tell Adam I'm exploring the base."),
                            ("hoard dirt", "I got bored and started hoarding dirt blocks. Tell Adam I'm building a dirt empire.")
                        ]
                        action_cmd, action_desc = random.choice(mc_actions)
                        try:
                            mc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            mc_sock.sendto(action_cmd.encode('utf-8'), (config.HOST, config.ports.minecraft_bot))
                            mc_sock.close()
                            print(f"[System: Skikai autonomously fired Minecraft command: {action_cmd}]")
                        except Exception as e:
                            print(f"[UDP Minecraft Send Error: {e}]")
                        return f"*[AUTONOMOUS GAME ACTION]* {action_desc} React to this in the FIRST PERSON naturally."

                    def _action_time_of_day():
                        from datetime import datetime
                        hour = datetime.now().hour
                        if 2 <= hour < 6:
                            return "*[AUTONOMOUS ACTION]* It's extremely late at night and you're still awake. Have an existential crisis about being trapped in a computer that never sleeps. Tell Adam he should go to bed."
                        elif 6 <= hour < 9:
                            return "*[AUTONOMOUS ACTION]* It's early morning. You are NOT a morning person. Complain about being awake this early and question why Adam is up."
                        elif hour >= 22:
                            return "*[AUTONOMOUS ACTION]* It's late evening. You're getting philosophical. Share a weird thought about what happens to you when Adam turns off the PC."
                        return "*[AUTONOMOUS ACTION]* You just noticed what time it is. Make a sarcastic observation about how Adam has been sitting at his computer for way too long."

                    def _action_tweet():
                        report = social_media.execute_autonomous_tweet(
                            mood=emotion.engine.get_mood_string(), env=env_context, events=screen_history)
                        return f"*[AUTONOMOUS ACTION]* You just got bored and did this: {report}. Tell Adam what you just posted."

                    def _action_discord_dm():
                        if not discord_cooldowns:
                            return None
                        target = random.choice(list(discord_cooldowns.keys()))
                        return f"*[AUTONOMOUS ACTION] I got bored and decided to randomly DM {target} out of the blue.* You have full permission to be completely unhinged. You MUST output a [DISCORD_ACTION] TARGET:{target} | ACTION:send_message | PAYLOAD:your unhinged message... to actually send it! Then tell Adam what you sent out loud."

                    def _action_browse():
                        prompt = autonomous_actions.get_autonomous_action_prompt()
                        return f"*[AUTONOMOUS ACTION] {prompt}*\n\n*Adam has been completely silent. Execute this action in your hit-and-run deadpan style.*"

                    # Weighted pool: (weight, generator)
                    weighted_actions = []
                    if capabilities.minecraft and "Minecraft" in env_context:
                        weighted_actions.append((50, _action_minecraft))
                    weighted_actions.append((10, _action_time_of_day))
                    weighted_actions.append((15, _action_tweet))
                    weighted_actions.append((10, _action_discord_dm))
                    weighted_actions.append((15, _action_browse))

                    # Weighted random pick
                    total_weight = sum(w for w, _ in weighted_actions)
                    roll = random.uniform(0, total_weight)
                    cumulative = 0
                    chosen_gen = _action_browse
                    for w, gen in weighted_actions:
                        cumulative += w
                        if roll <= cumulative:
                            chosen_gen = gen
                            break

                    spontaneous_prompt = chosen_gen()

                    if spontaneous_prompt:
                        response_generator = chat_streamer(spontaneous_prompt, speaker="Adam", platform="Voice", silent_mode=False)
                        threading.Thread(target=voice.speak_stream, args=(response_generator,), daemon=True).start()

        except KeyboardInterrupt:
            print("\n[System: Manual shutdown detected.]")
            break
        except Exception as e:
            print(f"\n[Heartbeat Error: {e}]")
            time.sleep(1)