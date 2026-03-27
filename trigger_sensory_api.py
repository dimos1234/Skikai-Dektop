import socket
import json
from youtube_transcript_api import YouTubeTranscriptApi
import time

# Utility script to test the Sensory API or be used by other extensions
# Sends a UDP packet to Skikai's brain on port 5007

UDP_IP = "127.0.0.1"
UDP_PORT = 5007

def send_event(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(json.dumps(payload).encode('utf-8'), (UDP_IP, UDP_PORT))
    print(f"[Sent] {payload}")

def trigger_minecraft_death():
    send_event({
        "type": "GAME_EVENT",
        "app": "Minecraft",
        "event": "Adam just fell into lava and lost all his diamonds."
    })

def stream_youtube_video(video_id):
    """
    Fetches the transcript for a YouTube video and streams it to Skikai line by line,
    simulating her 'watching' it with you in real-time.
    """
    print(f"Fetching transcript for video: {video_id}")
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        print("Transcript loaded. Beginning simulated playback...\n")
        
        for i, block in enumerate(transcript):
            # Send a chunk of text to Skikai
            send_event({
                "type": "YOUTUBE_WATCH",
                "video_id": video_id,
                "transcript_chunk": block['text']
            })
            
            # Wait until the next line is spoken in the video
            if i < len(transcript) - 1:
                current_time = block['start']
                next_time = transcript[i+1]['start']
                sleep_duration = next_time - current_time
                # Cap sleep duration just in case of weird gaps
                time.sleep(min(sleep_duration, 5.0)) 
                
    except Exception as e:
        print(f"Failed to load transcript: {e}")

if __name__ == "__main__":
    print("1. Test Minecraft Death Event")
    print("2. Test YouTube Video Stream (Neuro-sama Clip)")
    choice = input("Select an option: ")
    
    if choice == '1':
        trigger_minecraft_death()
    elif choice == '2':
        # The video ID from the URL you provided: https://youtu.be/b1JWLMF5bZo
        stream_youtube_video("b1JWLMF5bZo")
