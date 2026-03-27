import socket
import time
import ears
import config

def text_input_thread():
    """Listens for manual keyboard inputs from Adam in the terminal."""
    while True:
        text = input() 
        if text.strip():
            if ears.on_interrupt:
                ears.on_interrupt()
                
            with ears.user_input_queue.mutex:
                ears.user_input_queue.queue.clear()
                
            ears.user_input_queue.put(text)

def discord_listener_thread():
    """Listens for UDP packets from the standalone discord_bot.py"""
    UDP_IP = config.HOST
    UDP_PORT = config.ports.discord_in
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"[System: Skikai is now listening to Discord via UDP port {UDP_PORT}]")
    
    while True:
        try:
            # Wait for a packet from the Discord Bot
            data, addr = sock.recvfrom(65535) 
            discord_msg = data.decode('utf-8')
            
            # Do NOT interrupt her voice for a Discord message
            with ears.user_input_queue.mutex:
                ears.user_input_queue.queue.clear()
                
            # Shove the tagged message into her brain
            ears.user_input_queue.put(discord_msg)
            
        except Exception as e:
            print(f"[Discord UDP Error: {e}]")
            time.sleep(1)