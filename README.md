# Skikai Desktop (Legacy)

The original Skikai companion designed for desktop use with Warudo 3D model integration and local TTS.

## Usage
1. **Prerequisites:**
   - Start **Warudo** (WebSocket port `19190`).
   - Start your local **TTS API** (HTTP port `9880`).
   - Start an Ollama and moondream server on your network, and depending on the port opened edit the vision.py and brain.py files to point towards this server. This is so that the agent has vision of your desktop screen.  
   - (Optional) Start `discord_bot.py` for Discord integration.
   - (Optional) Start `bot.js` in plugins/minecraft for Minecraft integration. Open minecraft server to lan and adjust port in file. 
2. **Start:** Run `python main.py`.
3. **Voice:** Speak into your mic or type in the terminal. Use "learning mode" to trigger autonomous code self-optimization.

## Features
- **Warudo Sync:** Real-time 3D animation triggers based on emotion.
- **Subconscious Thread:** Llama 3.2 running on Mac handles intent and mood drift.
- **Vision:** Periodically captures screen content for "shoulder surfing" reactions.
