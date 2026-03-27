import webbrowser
import requests
import socket
import config

def browse_website(url):
    """
    Browses a website and returns the title of the page.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SkikaiBot'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            return {"status": "success", "data": r.text}
    except Exception as e:
        return {"status": "failure", "data": str(e)}

def search_youtube(query):
    """
    Searches YouTube for a given query.
    """
    try:
        webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        return {"status": "success", "data": f"Searched YouTube for '{query}'."}
    except Exception as e:
        return {"status": "failure", "data": str(e)}

def execute_minecraft_command(command):
    """
    Executes a Minecraft command.
    """
    try:
        mc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mc_sock.sendto(command.encode('utf-8'), (config.HOST, config.ports.minecraft_bot))
        mc_sock.close()
        return {"status": "success", "data": f"Executed Minecraft command: {command}"}
    except Exception as e:
        return {"status": "failure", "data": str(e)}
