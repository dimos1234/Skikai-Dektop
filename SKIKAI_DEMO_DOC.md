

---

# Skikai: Demo, Testing & Usage Documentation

## Part 1 — How to Use Skikai

### Prerequisites

- **PC (Windows):** Python 3.10+, TTS server (port 9880), Warudo (port 19190), optional Discord bot.
- **Mac:** LM Studio (main brain) and Ollama (subconscious + vision) reachable from PC via `MAC_LLM_URL` and `MAC_OLLAMA_URL` in `.env`.
- `**.env`:** `OPENAI_API_KEY`, `DISCORD_TOKEN`, `GROQ_API_KEY` (for VC transcription), `MAC_LLM_URL`, `MAC_OLLAMA_URL`. No bank account required for demo.

### Starting her

1. **Mac:** Start Ollama, run `ollama run moondream`. Ensure `OLLAMA_HOST=0.0.0.0` if PC and Mac are different machines.
2. **PC:** Start TTS API (port 9880). Optionally start Warudo and load Skikai’s blueprint. Optionally start `discord_bot.py` and invite the bot; ensure it’s in the right server and has message/VC permissions.
3. **PC:** From project root run `python main.py`. You should see brain loaded, Discord listener (if enabled), then greeting: `AI: what do you want?` and TTS speaking it.
4. **Terminal input:** Type in the same terminal and press Enter to talk. She waits for ~0.5s of silence then replies with streamed TTS and Warudo triggers.

### Voice commands (terminal only unless noted)


| Say (approx)                                 | Effect                                                                                                                 |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Normal chat                                  | She replies in character (Neuro-sama style), uses router for search/Discord/Minecraft.                          |
| **"stop working"** / **"back"** / **"done"** | Exits project mode back to companion.                                                                                  |
| **"project mode"** / **"collab mode"**       | Placeholder: speaks that project mode is coming; say “stop working” to exit.                                           |
| **"learning mode"**                          | Runs diary + Chroma compress, then spawns `learning_mode.py` in a new console (Cursor CLI sandbox). Main script exits. |
| **"quit"** / **"exit"** / **"sleep"**        | Goodbye message, diary + compress, then main exits.                                                                    |
| **"stop"** / **"shut up"** / **"quiet"**     | Stops TTS immediately; no reply.                                                                                       |


### Modes

- **Companion:** Normal loop: sensory events, your input, boredom after ~45 s idle (boredom > 85). Router + brain + TTS + Discord/Minecraft as applicable.
- **Project:** Placeholder; currently just a message.

### Ports (config: `config.py` / env)


| Port  | Service          | Notes                                                           |
| ----- | ---------------- | --------------------------------------------------------------- |
| 5005  | Discord → Skikai | Bot sends transcribed VC and DMs here.                          |
| 5006  | Skikai → Discord | Main/voice sends `[DISCORD_ACTION]` and `[DISCORD_VOICE]` here. |
| 5007  | Sensory API      | Minecraft/plugins send JSON game events here.                   |
| 5008  | Minecraft bot    | Main/brain send UDP commands to bot.                            |
| 9880  | TTS              | HTTP TTS API.                                                   |
| 19190 | Warudo           | WebSocket for animation triggers.                               |


### Feature flags (env or `config.features`)

- `SKIKAI_TTS`, `SKIKAI_WARUDO`, `SKIKAI_SCREEN_CAPTURE`, `SKIKAI_DISCORD`, `SKIKAI_MINECRAFT`, `SKIKAI_WEATHER`. Set to `false` for portable/headless (e.g. brain-only).

---

## Part 2 — Full Demo & Test Checklist (Expected Outputs & Times)

Use this for a full demo or regression test. Assume “valid” = within the stated time and behavior.

### A. Core brain & conversation


| #   | Action                                                          | Expected output / behavior                                                                                       | Valid time                                               |
| --- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 1   | Run `python testbench.py`                                       | `STATUS=SUCCESS` in `benchmark_results.txt`; console shows “SUCCESS. All systems functional” and avg TTFT/total. | TTFT < 8 s, total test < 60 s                            |
| 2   | Ask: “What is your name?”                                       | Reply in character (e.g. Skikai), possibly sarcastic. Streamed text + TTS.                                       | First token < 8 s, full reply < 30 s (depends on length) |
| 3   | Ask: “If I have 5 apples and eat 2, then buy 3 more, how many?” | Correct answer (6) in her style.                                                                                 | Same as above                                            |
| 4   | Say “stop” while she’s talking                                  | TTS stops immediately; no new reply.                                                                             | Instant                                                  |
| 5   | Say “um” or “ok” only                                           | Filtered: “[Filtered Noise] … Discarded.” No reply.                                                              | N/A                                                      |
| 6   | Say “quit”                                                      | Goodbye line, then script exits after diary + compress.                                                          | Exit within ~10 s                                        |


### B. Router: search, file, Discord, Minecraft


| #   | Action                                             | Expected output / behavior                                                                                                                           | Valid time                                                                                  |
| --- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 7   | “Search the web for latest news about AI”          | Router sets `needs_search`; brain gets search results and weaves into reply.                                                                         | Reply includes search snippet; total < 25 s                                                 |
| 8   | “Send a message to [Discord user] saying hello”    | Router sets `needs_action` + Discord target; brain outputs `[DISCORD_ACTION] TARGET:…                                                                | ACTION:send_message                                                                         |
| 9   | “Mine some dirt” (Minecraft bot running, same PC)  | Router sets `needs_minecraft_action`, `minecraft_command` e.g. “mine dirt”; brain emits `[MINECRAFT_ACTION] mine dirt`; main/brain send UDP to 5008. | Bot console “[Command Received]: mine dirt”; bot sends sensory event “I spotted some dirt…” |


### C. Discord (full flow)


| #   | Action                                                                | Expected output / behavior                                                                                                                                                                                                                                  | Valid time                                |
| --- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| 13  | Send DM to Skikai in Discord: “Hey Skikai”                            | Bot receives message, sends to main on 5005; main puts in queue; cooldown 15 s per user; `skikai_is_typing = True`; background thread runs `chat_streamer(..., platform="Discord")`; main sends `[DISCORD_ACTION] TARGET:YourName                           | ACTION:send_message                       |
| 14  | Same user sends another DM within 15 s                                | Console “[System: Ignoring … Cooldown active.]”; no second reply.                                                                                                                                                                                           | N/A                                       |
| 15  | Say in VC (with bot in VC): “Skikai, what time is it?”                | Bot’s VC sink buffers PCM; after ~1 s silence, Groq Whisper transcribes; bot sends `[Discord VC - YourName]: what time is it?` to 5005; main treats as VC; after silence + 0.5 s, streamed reply + TTS; bot receives `[DISCORD_VOICE]` + path, plays in VC. | You hear her reply in VC within ~15–25 s. |
| 16  | “Skikai listen to me” / “stop typing” while she’s replying to Discord | Main clears `skikai_is_typing`, aborts Discord send; next input is processed.                                                                                                                                                                               | Next input not blocked.                   |


### D. Minecraft (bot.js + main)

Prereq: Minecraft server running, bot connected (`node bot.js`), `host`/`port` in `bot.js` match server. Skikai main running with `SKIKAI_MINECRAFT` true (default).


| #   | Action                                               | Expected output / behavior                                                                                                                                                                                                   | Valid time                                                                 |
| --- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 17  | “Follow me” (you = Adam)                             | You: “follow Adam”. Bot sets goal `follow Adam`, sends “You are now following Adam.” Sensory event to 5007; main may react vocally (e.g. “following you”).                                                                   | Bot moves toward you; sensory in main.                                     |
| 18  | “Attack that zombie”                                 | Command “attack zombie”; bot pathfinds if far, then attacks; sends “You are now attacking zombie” or “Close enough! Now attacking…”.                                                                                         | Bot attacks; sensory event.                                                |
| 19  | “Build a hut” / “Build shelter”                      | `build_hut` / `shelter`: needs ≥20 blocks (dirt/cobblestone/planks); builds 3×3 shelter; sensory “Shelter done! Placed N blocks…”.                                                                                           | If blocks available, completion in < 2 min.                                |
| 20  | “Set our goal to survive the night”                  | Via brain/router: “our goal is survive the night” → router may not send SESSION_GOAL; alternatively send UDP `SESSION_GOAL:survive the night` to 5008 (custom). Bot supports `SESSION_GOAL:text` and `session_goal` command. | If command reaches bot: “Our goal for this session is: survive the night”. |
| 21  | “Stop” (in-game)                                     | Bot receives `stop`; pathfinder/pvp cleared; “You stopped whatever you were doing.”                                                                                                                                          | Idle immediately.                                                          |
| 22  | “Dance”                                              | Bot toggles sneak ~10×; “You started dancing.”                                                                                                                                                                               | ~3 s then idle.                                                            |
| 23  | “What’s in your inventory?” then “inventory” command | You ask; she may say “check my inventory”; you “inventory” → bot sends sensory with item list.                                                                                                                               | Bot console and sensory event with list.                                   |
| 24  | Stuck case: bot pathfinds for 60+ s with no movement | Stuck detection clears goal, sends “I got stuck trying to … I’m giving up…”.                                                                                                                                                 | After ~60 s stuck.                                                         |
| 25  | No command for 5+ min with bot active                | Periodic session summary every 5 min: task, HP, food, time of day, items, session goal.                                                                                                                                      | Sensory event every 5 min.                                                 |


### F. Sensory API (game/plugin events)


| #   | Action                                                                                        | Expected output / behavior                                                                                                                                         | Valid time              |
| --- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------- |
| 29  | Send UDP to 5007: `{"type":"GAME_EVENT","app":"Minecraft","event":"Adam died to a Creeper."}` | Main dequeues event; adds to short-term memory; if not talking and >15 s since last game reaction, generates vocal reaction (e.g. “Oh no, you died to a Creeper”). | One short TTS reaction. |
| 30  | Send same event again within 15 s                                                             | Event stored; “[System: Skikai noted the event silently to avoid spamming…]”.                                                                                      | No extra TTS.           |


### G. Boredom (companion mode only)


| #   | Action                                                 | Expected output / behavior                                                                                                                                                                                        | Valid time                            |
| --- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| 31  | Don’t type or trigger anything for 45+ s, boredom > 85 | “[System: Skikai’s boredom hit … She is taking autonomous action…]”; one of: Minecraft (if env has “Minecraft”), time-of-day, tweet, Discord DM, or browse; then streamed reply. | Single autonomous action + one reply. |
| 32  | Minecraft in env, boredom fires Minecraft              | UDP sent to 5008 (e.g. dance, mine dirt, wander); bot acts; she says what she did.                                                                                                                                | Bot and TTS.                          |


### H. Learning mode


| #   | Action                                                    | Expected output / behavior                                                                                                              | Valid time                                   |
| --- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| 33  | “Learning mode”                                           | Goodnight message, diary + compress, new console with `learning_mode.py`. Main exits.                                                   | New window starts sandbox.                   |
| 34  | In learning window: Cursor CLI installed, `agent` on PATH | Sandbox creates backup, runs Cursor agent with `temp_prompt.txt`, then `python testbench.py`; on success, new backup; on fail, restore. | Per-iteration ~2–10+ min depending on model. |
| 35  | Ctrl+C in learning window                                 | “KILLSWITCH ACTIVATED”; prompt keep/revert; if revert, backup restored.                                                                 | N/A                                          |


### I. Edge cases & failures


| #   | Scenario                            | Expected behavior                                                                                               |
| --- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 36  | Mac LM Studio down                  | Brain calls fail; reply may be empty or error; testbench fails.                                                 |
| 37  | Ollama down on Mac                  | Vision/emotion calls fail; vision thread backs off; emotion may fallback; no crash.                             |
| 38  | Discord bot not running             | No DMs to Skikai; VC not received. Main still runs; terminal works.                                             |
| 39  | Minecraft bot not running           | Commands to 5008 succeed UDP send; no sensory back; she may say she did something with no in-game effect.       |
| 40  | TTS server down                     | voice.py requests fail; “[TTS API Error]” or “[TTS Connection Error]”; no audio.                                |
| 41  | Warudo closed                       | WebSocket fails; “[WebSocket Error…]”; no animation; TTS/chat still work.                                       |
| 42  | Router returns invalid JSON         | Router error path; no action; brain may still reply with no tool use.                                           |


---

## Part 3 — Mac Model Suggestions

Current setup:

- **Main brain:** LM Studio, Llama 8B Instruct (~4 s TTFT).
- **Subconscious / intent:** Ollama, Llama 3.2 (3B) — mood, instant intent.
- **Vision:** Ollama, Moondream — screen description.

If things feel slow or you want better quality:

### Main brain (LM Studio, Mac)

- **Qwen 2.5 7B Instruct (Q4_K_M):** Often faster than Llama 8B on Apple Silicon, similar quality.
- **Mistral 7B v0.3 Instruct:** Also snappy on M-series.
- **Llama 3.1 8B Q4_K_M:** If you’re on Q8, switching to Q4_K_M can cut TTFT a lot with small quality loss for chat.
- Keep total TTFT under 8 s so `testbench.py` passes.

### Subconscious / intent (Ollama, Mac)

- **Llama 3.2 3B:** Current; fine for one-sentence intent/mood.
- **Llama 3.2 1B:** Faster, slightly less accurate; try if 3B is a bottleneck.
- Both are low-latency; 3B is safer for quality.

### Vision (Ollama, Mac)

- **Moondream:** Good for “describe this screen”; keep unless it’s too slow.
- If Moondream is too slow: **LLava 7B** or **Bakllava** in Ollama are alternatives; slightly heavier but sometimes faster depending on hardware. Benchmark with `vision.get_screen_description()` under load.

### Summary

- Prefer **Qwen 2.5 7B** or **Mistral 7B** on LM Studio for speed vs quality.
- Use **Q4_K_M** for main brain if you need lower TTFT.
- Subconscious: **Llama 3.2 3B** (or 1B for speed).
- Vision: **Moondream** first; if slow, try **LLava/Bakllava**.

---

## Part 4 — Time Bounds Reference


| Component                  | Limit / target           | Where                                     |
| -------------------------- | ------------------------ | ----------------------------------------- |
| Testbench TTFT             | < 8 s average            | `testbench.py`                            |
| Testbench total            | < 60 s                   | `testbench.py` timeout                    |
| Brain state snapshot       | 5 s                      | `brain.py` state_future.result(timeout=5) |
| Brain memory query         | 10 s                     | memory_future.result(timeout=10)          |
| Emotion get_mood_string    | 3 s                      | emotion.py request timeout                |
| Emotion get_instant_intent | 2 s                      | emotion.py request timeout                |
| Vision screen description  | 10 s                     | vision.py request timeout                 |
| Boredom cooldown           | 45 s idle + boredom > 85 | main.py                                   |
| Discord cooldown           | 15 s per user            | main.py                                   |
| Game reaction throttle     | 15 s                     | main.py last_game_reaction_time           |
| Minecraft stuck timeout    | 60 s                     | bot.js STUCK_TIMEOUT_MS                   |
| Session summary interval   | 5 min                    | bot.js SUMMARY_INTERVAL_MS                |


---

