import discord
from discord.ext import voice_recv
import discord.opus
from discord.ext.voice_recv.opus import PacketDecoder
import socket
import os
import threading
import asyncio
from dotenv import load_dotenv
import wave
import time
from groq import Groq

# --- MONKEY PATCH TO FIX OPUS CORRUPTED STREAM CRASH ---
# The voice_recv library crashes entirely if a single corrupted packet arrives.
_old_decode_packet = PacketDecoder._decode_packet

def _safe_decode_packet(self, packet):
    try:
        return _old_decode_packet(self, packet)
    except discord.opus.OpusError:
        # Return a silent PCM block (20ms of stereo 48k is 3840 bytes)
        return packet, b'\x00' * 3840

PacketDecoder._decode_packet = _safe_decode_packet
# -------------------------------------------------------

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize Groq for the Discord bot to transcribe VC audio independently
groq_client = Groq(api_key=GROQ_API_KEY)

UDP_IP = "127.0.0.1"
UDP_PORT_OUT = 5005 # Sending TO Skikai's brain
UDP_PORT_IN = 5006  # Receiving FROM Skikai's brain

sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.voice_states = True # 💥 Needed for voice chat
client = discord.Client(intents=intents)

# Global voice client reference
skikai_vc = None

# A set of Discord user display names that Skikai will ignore in VC
ignored_users = set()

# --- DISCORD VC LISTENER SINK ---
class SkikaiVCSink(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.user_buffers = {}
        self.last_speech_time = {}
        self.processing = False
        
        # Start a background thread to check for silence and transcribe
        threading.Thread(target=self._process_buffers, daemon=True).start()

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user is None:
            return
            
        user_name = user.display_name
        
        # 💥 DUAL-INPUT FIX: Ignore specific users if they requested it
        if user_name in ignored_users:
            return

        if user_name not in self.user_buffers:
            self.user_buffers[user_name] = bytearray()
            
        # Append raw PCM data (48000Hz, 16-bit, stereo by default from Discord)
        self.user_buffers[user_name].extend(data.pcm)
        self.last_speech_time[user_name] = time.time()

    def cleanup(self):
        pass
        
    def _process_buffers(self):
        """Monitors when users stop speaking, saves the audio, and transcribes it."""
        while True:
            time.sleep(0.5)
            now = time.time()
            
            # Iterate over a copy of the keys to avoid dictionary changed size during iteration
            for user_name in list(self.last_speech_time.keys()):
                # If they haven't spoken for 1 second, and they have enough data (at least 0.5s)
                if now - self.last_speech_time[user_name] > 1.0:
                    pcm_data = self.user_buffers.pop(user_name, None)
                    self.last_speech_time.pop(user_name, None)
                    
                    # 48000 Hz * 2 channels * 2 bytes/sample = 192000 bytes/sec
                    if pcm_data and len(pcm_data) > 96000: 
                        threading.Thread(target=self._transcribe_and_route, args=(user_name, pcm_data)).start()

    def _transcribe_and_route(self, user_name, pcm_data):
        filename = f"vc_temp_{user_name}_{int(time.time())}.wav"
        try:
            # Discord provides 48kHz, 16-bit, stereo PCM
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(pcm_data)
                
            # Send to Groq
            with open(filename, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(filename, audio_file.read()),
                    model="whisper-large-v3",
                    response_format="text"
                )
                
            clean_text = transcription.strip()
            if clean_text and len(clean_text) > 2:
                print(f"[Discord VC] {user_name} said: {clean_text}")
                # Route it as a VC message so she speaks her reply out loud
                formatted_msg = f"[Discord VC - {user_name}]: {clean_text}"
                sock_out.sendto(formatted_msg.encode('utf-8'), (UDP_IP, UDP_PORT_OUT))
                
        except Exception as e:
            print(f"[VC Transcription Error for {user_name}]: {e}")
        finally:
            # Cleanup temp file
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass

def udp_listener_thread(loop):
    """Listens for actions from main.py and schedules them in the discord event loop."""
    global skikai_vc
    sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_in.bind((UDP_IP, UDP_PORT_IN))
    print(f"[- 📡 Discord Bot listening for Skikai's commands on UDP {UDP_PORT_IN} -]")
    
    while True:
        try:
            data, _ = sock_in.recvfrom(65535)
            command_str = data.decode('utf-8')
            
            # --- VOICE PLAYBACK ---
            if command_str.startswith("[DISCORD_VOICE]"):
                filepath = command_str.replace("[DISCORD_VOICE]", "").strip()
                if skikai_vc and skikai_vc.is_connected():
                    # Wait for previous audio chunk to finish so we don't drop sentences
                    while skikai_vc.is_playing():
                        time.sleep(0.05)
                    try:
                        skikai_vc.play(discord.FFmpegPCMAudio(source=filepath))
                    except Exception as e:
                        print(f"[VC Playback Error]: {e}")
                continue
            
            # --- TEXT ACTIONS ---
            print(f"\n[Discord Bot Received Core Command: {command_str}]")
            if command_str.startswith("[DISCORD_ACTION]"):
                parts = command_str.replace("[DISCORD_ACTION]", "").strip().split(" | ")
                
                target = ""
                action = ""
                payload = ""
                
                for part in parts:
                    if part.startswith("TARGET:"): target = part.split("TARGET:")[1].strip()
                    if part.startswith("ACTION:"): action = part.split("ACTION:")[1].strip()
                    if part.startswith("PAYLOAD:"): payload = part.split("PAYLOAD:")[1].strip()
                    
                asyncio.run_coroutine_threadsafe(execute_discord_action(target, action, payload), loop)
                
        except Exception as e:
            print(f"[UDP Listener Error: {e}]")

async def execute_discord_action(target, action, payload):
    """Executes the physical action on Discord servers."""
    print(f"[Executing] Action: {action} | Target: {target} | Payload: {payload}")
    
    target_member = None
    
    for guild in client.guilds:
        for member in guild.members:
            if target.lower() in member.display_name.lower() or target.lower() in member.name.lower():
                target_member = member
                break
        if target_member: 
            break
            
    if not target_member:
        print(f"[Action Failed: Could not find Discord user '{target}']")
        return
        
    try:
        if action in ["send_message", "send_link", "send_challenge"]:
            if not payload or payload.strip() == "":
                print(f"[Action Failed: Cannot send an empty message to {target_member.display_name}]")
                return
            await target_member.send(payload)
            print(f"[Success: Action delivered to {target_member.display_name}]")
    except discord.Forbidden:
        print(f"[Action Failed: {target_member.display_name} has DMs disabled.]")
    except Exception as e:
        print(f"[Discord API Error: {e}]")

@client.event
async def on_ready():
    print(f'\n[- 🟢 Discord Link Established. Logged in as {client.user} -]')
    threading.Thread(target=udp_listener_thread, args=(asyncio.get_running_loop(),), daemon=True).start()

@client.event
async def on_message(message):
    global skikai_vc
    if message.author == client.user: 
        return
        
    # --- VOICE COMMANDS ---
    if message.content.lower() == "!join":
        if message.author.voice:
            channel = message.author.voice.channel
            try:
                # Use VoiceRecvClient instead of standard connect
                skikai_vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
                print(f"[Discord: Skikai joined voice channel '{channel.name}']")
                
                # Start listening with our custom sink!
                skikai_vc.listen(SkikaiVCSink())
                print("[Discord: VC Listener Active. Skikai can now hear everyone.]")
            except Exception as e:
                print(f"[Discord Voice Error: {e}]")
        else:
            await message.channel.send("You need to be in a voice channel to summon me.")
        return
        
    if message.content.lower() == "!leave":
        if skikai_vc and skikai_vc.is_connected():
            await skikai_vc.disconnect()
            skikai_vc = None
            print("[Discord: Skikai left the voice channel]")
        return
        
    if message.content.lower() == "!ignoreme":
        ignored_users.add(message.author.display_name)
        await message.channel.send(f"Okay {message.author.display_name}, I will mute you in VC so I don't hear you twice.")
        print(f"[Discord: Ignoring VC audio for {message.author.display_name}]")
        return
        
    if message.content.lower() == "!listenme":
        if message.author.display_name in ignored_users:
            ignored_users.remove(message.author.display_name)
        await message.channel.send(f"I am now listening to you in VC, {message.author.display_name}.")
        print(f"[Discord: Listening to VC audio for {message.author.display_name}]")
        return

    # Standard text routing
    formatted_msg = f"[Discord User - {message.author.display_name}]: {message.content}"
    sock_out.sendto(formatted_msg.encode('utf-8'), (UDP_IP, UDP_PORT_OUT))

if __name__ == "__main__":
    client.run(TOKEN)