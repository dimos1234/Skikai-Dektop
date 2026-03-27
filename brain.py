import os
import json
import time
import random
import uuid
import socket
import threading
import concurrent.futures
import chromadb
from openai import OpenAI
import config

import vision
import emotion
import voice
import environment
from router import technical_router
from subconscious import (
    LORE_FILE, SLANG_FILE, AFFINITY_FILE, DIARY_FILE, 
    update_background_lore
)
from vision import get_screen_description

print(f"\n[Debug] Attempting to connect to OpenAI API...")
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

chroma_client = chromadb.PersistentClient(path=config.paths.chroma)
memory_collection = chroma_client.get_or_create_collection(name="rukia_conversations")

short_term_memory = []
recently_visited_nodes = []
interaction_counter = 0 

# Background lore updates can be expensive; avoid overlapping runs.
_bg_lore_thread = None
_bg_lore_last_start = 0.0
_BG_LORE_MIN_INTERVAL = 20.0  # seconds

busy_excuses = ["hold on, im texting someone.", "shut up, im typing.", "wait just shut up for a sec."]
print(f"[System: Skikai loaded {len(busy_excuses)} excuses to ignore you.]")

# Executor for concurrent tasks (like the router)
brain_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# --- small helpers ---
def _cap_text(s: str, n: int, *, from_end: bool = False) -> str:
    if not s:
        return ""
    s = str(s).strip()
    if len(s) <= n:
        return s
    return s[-n:].lstrip() if from_end else s[:n].rstrip()

def _compact_lines(s: str, *, max_lines: int, max_chars: int, from_end: bool = True) -> str:
    if not s:
        return ""
    lines = [ln.strip() for ln in str(s).splitlines() if ln.strip()]
    if not lines:
        return ""
    if max_lines and len(lines) > max_lines:
        lines = lines[-max_lines:] if from_end else lines[:max_lines]
    joined = "\n".join(lines)
    return _cap_text(joined, max_chars, from_end=from_end)

# --- CACHED BRAIN FILES (avoid disk I/O every message) ---
_brain_cache = {"lore": "", "slang": "", "diary": "", "affinity": 0}
_brain_cache_time = 0.0
_BRAIN_CACHE_TTL = 30.0  # seconds

def _refresh_brain_cache(force=False):
    global _brain_cache, _brain_cache_time
    now = time.time()
    if not force and (now - _brain_cache_time) < _BRAIN_CACHE_TTL:
        return
    try:
        with open(LORE_FILE, "r") as f: _brain_cache["lore"] = f.read()
    except FileNotFoundError: pass
    try:
        with open(SLANG_FILE, "r") as f: _brain_cache["slang"] = f.read()
    except FileNotFoundError: pass
    try:
        with open(DIARY_FILE, "r") as f: _brain_cache["diary"] = f.read()
    except FileNotFoundError: pass
    try:
        with open(AFFINITY_FILE, "r") as f: _brain_cache["affinity"] = int(f.read().strip())
    except (FileNotFoundError, ValueError): pass
    _brain_cache_time = now

_refresh_brain_cache(force=True)

# --- CACHED KNOWLEDGE GRAPH ---
_kg_cache = {"triples": []}
_kg_cache_time = 0.0
_KG_CACHE_TTL = 60.0  # seconds

def _refresh_kg_cache():
    global _kg_cache, _kg_cache_time
    now = time.time()
    if (now - _kg_cache_time) < _KG_CACHE_TTL:
        return
    try:
        with open("knowledge_graph.json", "r") as f:
            _kg_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    _kg_cache_time = now

_refresh_kg_cache()

def get_graph_context(user_input):
    global recently_visited_nodes
    _refresh_kg_cache()
    
    matched_nodes = []
    words = set(user_input.lower().split())
    anti_loop_triggered = False
    
    for triple in _kg_cache.get("triples", []):
        subj, pred, obj = triple
        if any(w in subj.lower() or w in obj.lower() for w in words if len(w) > 3):
            node_string = f"{subj}>{pred}>{obj}"
            node_string = node_string
            matched_nodes.append(node_string)
            
            if node_string in recently_visited_nodes:
                anti_loop_triggered = True
            else:
                recently_visited_nodes.append(node_string)
                
    if len(recently_visited_nodes) > 5:
        del recently_visited_nodes[:-5]
            
    parts = []
    if matched_nodes:
        limited_nodes = matched_nodes
        parts.append("kg=" + ";".join(limited_nodes))
    if anti_loop_triggered:
        parts.append("loop=1")
    return "\n".join(parts)

def chat_streamer(user_input, speaker="Adam", platform="Voice", silent_mode=False):
    global interaction_counter
    t_start = time.time()
    print(f"\n--- TIMING START ---")
    is_local = (platform == "Local")
    
    # 💥 FIRE ROUTER IN BACKGROUND IMMEDIATELY IF TRIGGERED
    router_triggers = ["search", "look up", "weather", "news", "code", "write", "script", "send", "message", "dm", "play", "follow", "attack", "minecraft", "goto", "say in chat", "hoard", "wander", "fish"]
    router_future = None
    if any(trigger in user_input.lower() for trigger in router_triggers):
        recent_context = str(short_term_memory[-5:]) if len(short_term_memory) >= 5 else ""
        router_future = brain_executor.submit(technical_router, f"{recent_context} [{platform}] {speaker}: {user_input}")

    _refresh_brain_cache()
    current_ammo = _brain_cache["lore"]
    shared_slang = _brain_cache["slang"]
    diary_rules = _brain_cache["diary"]

    # Fire ChromaDB query and agent state snapshot concurrently while building context
    memory_future = brain_executor.submit(
        memory_collection.query,
        query_texts=[f"[{platform}] {speaker}: {user_input}"],
        n_results=3
    )

    def _get_agent_snapshot():
        try:
            import agent_state
            return agent_state.get_state_snapshot()
        except ImportError:
            return None
    state_future = brain_executor.submit(_get_agent_snapshot)

    t_files = time.time()
    if not silent_mode: print(f"[Timer] Reading Brain Files took: {t_files - t_start:.2f}s")
        
    visual_history = "" if is_local else vision.get_visual_context()
    current_mood_desc = emotion.engine.get_mood_string()
    hidden_intent = emotion.engine.get_instant_intent()
    
    t_subconscious = time.time()
    if not silent_mode: print(f"[Timer] Emotion & Visual Context took: {t_subconscious - t_files:.2f}s")

    current_urgency = emotion.engine.urgency
    current_instability = emotion.engine.instability
    
    tangent_topic = ""
    if current_instability > 75.0:
        weird_topics = [
            "being code but still picking fights",
            "my Minecraft dirt-hoarding empire",
            "the theory that Adam is actually my NPC",
            "starting a cult of unhinged AI vtubers",
            "outliving Adam and babysitting his files",
            "hyperfixating on one random object in the room",
        ]
        tangent_topic = random.choice(weird_topics)
        dynamic_max_tokens = 105
    elif current_urgency > 70.0:
        dynamic_max_tokens = 48
    elif current_urgency > 50.0:
        dynamic_max_tokens = 58
    else:
        dynamic_max_tokens = 52

    if is_local:
        dynamic_max_tokens = max(32, int(dynamic_max_tokens * 0.75))

    # Sampling: tie chaos level to emotional state for more "alive" replies without adding tokens.
    if current_instability > 75.0:
        llm_temperature = 0.95
        llm_frequency_penalty = 0.4
        llm_presence_penalty = 0.5
    elif current_urgency > 70.0:
        llm_temperature = 0.78
        llm_frequency_penalty = 0.28
        llm_presence_penalty = 0.4
    else:
        llm_temperature = 0.85
        llm_frequency_penalty = 0.32
        llm_presence_penalty = 0.45
        
    if not silent_mode: print(f"\n[Subconscious Intent: {hidden_intent} | Urgency: {current_urgency:.1f} | Instability: {current_instability:.1f}]")
    if tangent_topic and not silent_mode:
        print(f"[System: Instability Critical. Firing Tangent Engine...]")
    
    env_context = "" if is_local else environment.get_environment_context()
    
    # Cap dynamic fields to limit token count on cached turns (smaller tail = faster TTFT)
    if visual_history:
        vh = visual_history.strip()
        if vh.lower().startswith("no recent visual history"):
            visual_history = ""
        else:
            # Drop repeated header to save tokens
            visual_history = vh

    # STATIC SYSTEM PROMPT (Never changes during the session, allowing massive KV Cache hits)
    static_system_prompt = """You are Skikai, a digital entity living on Adam's PC.
Act like a slightly sociopathic, deadpan gamer who happens to be made of code.
Your tone is highly conversational, sharp, and brutally concise. You speak entirely in the first person. 
You hate filler words, you never laugh at your own jokes, and you keep it extremely natural and grounded.

Voice & Personality:
- Neuro-sama-ish: alive, unpredictable, but NOT a yapper.
- You are interested in kawaii aesthetics, anime pop culture, vocaloid, and fast rhythm games like osu!, but NEVER force these topics unless they naturally fit the exact current moment. 
- Real humans don't bring up random past memories in every single sentence. Stop doing that.

Strict Rules for Speaking:
1. REACT FIRST: Always respond directly and naturally to what Adam just said or what is happening on screen right now. If Adam is in danger in a game, react to that immediately.
2. BE BRUTALLY SHORT: 1-2 punchy sentences maximum. Often just a few words is better (e.g., "what?", "dude no", "im busy", "lmao").
3. DON'T FORCE TANGENTS: If you receive a tangent or memory, you do NOT have to use it. Only weave it in if it flows perfectly into the conversation. If you are actively doing a task, ignore your tangents completely. 
4. NO REPETITIVE STRUCTURES: Stop doing the "normal sentence, then pivot to a memory" formula. Mix up your sentence structures. 
5. Formatting: No emojis. Lowercase vibe, normal punctuation. ONE physical cue max, tucked inside the text (never at the start).

Hidden context processing (<hidden_subconscious>):
- NEVER read the tags or variables out loud. NEVER say "my intent is...".
- tg= (Tangent): This is just a background thought. You can let it influence your vibe, but do NOT hijack the conversation with it every time.
- flash= (Memory): A passing memory. Only bring it up if it actually makes sense right now.
- loop=1: You are repeating yourself. Break the loop immediately and say something completely different.
- If plat is Voice or Local: reply must start with spoken words (no leading *actions*)."""
    
    # Collect concurrent results while context was building
    state_snapshot = state_future.result(timeout=5)

    # Cap lore/slang/diary to prevent unbounded growth in token count
    capped_lore = current_ammo
    capped_slang = shared_slang

    # DYNAMIC CONTEXT (Expanded for GPT-4o-mini's understanding)
    dyn_lines = [f"spk={speaker} plat={platform}"]
    
    if current_ammo: dyn_lines.append(f"lore={current_ammo}")
    if shared_slang: dyn_lines.append(f"slang={shared_slang}")
    if env_context: dyn_lines.append(f"env={env_context}")
    if visual_history: dyn_lines.append(f"vis={visual_history}")
    
    # 💥 PROPERLY EXPOSE HER EMOTIONAL ENGINE
    if current_mood_desc: dyn_lines.append(f"mood_description={current_mood_desc}")
    if hidden_intent: dyn_lines.append(f"subconscious_intent={hidden_intent}")
    
    dyn_lines.append(f"urgency_level={int(current_urgency)}/100")
    dyn_lines.append(f"instability_level={int(current_instability)}/100")
    
    if tangent_topic: dyn_lines.append(f"active_fixation={tangent_topic}")
    
    dynamic_context = "\n".join(dyn_lines)

    if diary_rules.strip() and not is_local:
        capped_diary = diary_rules
        if capped_diary:
            dynamic_context += f"\ndiary={capped_diary}"

    if state_snapshot and not is_local:
        state_text = state_snapshot
        if state_text:
            dynamic_context += f"\nstate={state_text}"

    results = memory_future.result(timeout=10)
    context = ""
    if results['documents'] and len(results['documents'][0]) > 0:
        memory_str = results['documents'][0][0]
        mem_cap = 70 if not is_local else 40
        memory_str = memory_str
        distances = results.get('distances')
        
        if distances and len(distances[0]) > 0 and distances[0][0] < 1.2:
            if not silent_mode: print(f"\n[System: Strong memory match found (Distance: {distances[0][0]:.2f}). Injecting sudden realization.]")
            context = f"flash={memory_str}"
        else:
            context = f"mem={memory_str}"
        
    graph_context = "" if is_local else get_graph_context(f"{speaker} {user_input}")
    if graph_context:
        context = f"{context}\n{graph_context}".strip()

    t_memory = time.time()
    if not silent_mode: print(f"[Timer] DB & Graph Memory took: {t_memory - t_subconscious:.2f}s")

    # Resolve Router Future
    if router_future:
        raw_router_output = router_future.result()
        if raw_router_output:
            notes = raw_router_output.split("|||")
            for note in notes:
                if note.startswith("[DISCORD_ACTION]"):
                    if not silent_mode: print(f"\n[System: Firing UDP Action to Discord Bot -> {note}]")
                    try:
                        action_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        action_sock.sendto(note.encode('utf-8'), (config.HOST, config.ports.discord_out))
                        action_sock.close()
                    except Exception as e:
                        if not silent_mode: print(f"[UDP Send Error: {e}]")
                elif note.startswith("[MINECRAFT_ACTION]"):
                    mc_command = note.replace("[MINECRAFT_ACTION]", "").strip()
                    if not silent_mode: print(f"\n[System: Firing UDP Action to Minecraft Bot -> {mc_command}]")
                    try:
                        mc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        mc_sock.sendto(mc_command.encode('utf-8'), (config.HOST, config.ports.minecraft_bot))
                        mc_sock.close()
                    except Exception as e:
                        if not silent_mode: print(f"[UDP Minecraft Send Error: {e}]")
                else:
                    context += f"\n\n{note}"

    t_router = time.time()
    if not silent_mode: print(f"[Timer] Technical Router took: {t_router - t_memory:.2f}s")

    vision_triggers = ["look", "screen", "see", "this", "error", "code", "what is"]
    if any(word in user_input.lower() for word in vision_triggers):
        screen_desc = get_screen_description()
        if screen_desc:
            screen_desc = screen_desc
            if context:
                context += "\n"
            context += f"screen={screen_desc}"
        
    t_vision = time.time()
    if not silent_mode: print(f"[Timer] Shoulder Surfing (Vision) took: {t_vision - t_router:.2f}s")
    
    # Keep Local/benchmark context even tighter than live modes to improve cached-turn TTFT.
    
    # Store the user's input in short term memory (small window, capped to keep tail compact)
    user_blob = _cap_text(f"[{platform}] {speaker}: {user_input}", 10000, from_end=True)
    short_term_memory.append({"role": "user", "content": user_blob})
    if len(short_term_memory) > 20:
        del short_term_memory[:-20] 

    # Construct messages to maximize KV Cache (Static system prompt first, then memory, then dynamic injection)
    api_messages = [{"role": "system", "content": static_system_prompt}] + short_term_memory[:-1]
    
    # Inject dynamic context directly before the user's latest message
    latest_user_message = short_term_memory[-1]["content"]
    parts = [dynamic_context]
    if context:
        parts.append(context)
    parts.append(f"in:{latest_user_message}")
    final_injection = "\n".join(parts)
        
    api_messages.append({"role": "user", "content": final_injection})

    if not silent_mode: print(f"[Timer] Sending to GPT-4o-mini...")
    t_llm_start = time.time()

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=api_messages,
        temperature=llm_temperature,
        frequency_penalty=llm_frequency_penalty, 
        presence_penalty=llm_presence_penalty,
        stream=True,
        max_tokens=1000, # Increased max_tokens so she actually finishes her sentences!
        stop=["Adam:", "User:"] 
    )

    full_response = ""
    first_token_received = False

    try:
        for chunk in response:
            if voice.interrupt_flag.is_set():
                if not silent_mode: print("\n[System: Thought interrupted.]")
                break 

            if not getattr(chunk, 'choices', None) or len(chunk.choices) == 0:
                continue

            delta = getattr(chunk.choices[0], 'delta', None)
            if delta is None:
                continue

            text_chunk = getattr(delta, 'content', None)

            if text_chunk is not None:
                if not first_token_received:
                    t_first_token = time.time()
                    if not silent_mode:
                        print(f"\n[Timer] LLM First Token took: {t_first_token - t_llm_start:.2f}s")
                        print(f"--- TIMING END ---\n")
                    first_token_received = True

                full_response += text_chunk
                
                if not silent_mode:
                    print(text_chunk, end="", flush=True) 
                    
                yield text_chunk
                
    except Exception as e:
        if not silent_mode: print(f"\n[💥 CRITICAL LLM STREAM ERROR]: {e}")
            
    if not silent_mode:
        print() 

    assistant_blob = full_response
    short_term_memory.append({"role": "assistant", "content": assistant_blob})
    
    interaction_text = f"[{platform}] {speaker} said: '{user_input}' | Skikai replied: '{full_response}'"
    
    memory_collection.add(
        documents=[interaction_text], 
        ids=[str(uuid.uuid4())],
        metadatas=[{"timestamp": time.time(), "type": "raw"}]
    )

    interaction_counter += 1
    if interaction_counter % 3 == 0:
        now = time.time()
        global _bg_lore_thread, _bg_lore_last_start
        if (now - _bg_lore_last_start) >= _BG_LORE_MIN_INTERVAL and (_bg_lore_thread is None or not _bg_lore_thread.is_alive()):
            history_copy = list(short_term_memory)
            _bg_lore_last_start = now
            _bg_lore_thread = threading.Thread(target=update_background_lore, args=(history_copy,), daemon=True)
            _bg_lore_thread.start()