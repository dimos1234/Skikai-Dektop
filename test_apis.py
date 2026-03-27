import os
import requests
import json
import asyncio
from dotenv import load_dotenv

# Ensure we load the .env file
load_dotenv()

def print_result(api_name, success, details=""):
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status} | {api_name:<15} | {details}")

def test_openai():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print_result("OpenAI", False, "Missing OPENAI_API_KEY in .env")
        return
        
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        # A lightweight models list request to verify auth
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
        if response.status_code == 200:
            print_result("OpenAI", True, "Successfully authenticated.")
        else:
            print_result("OpenAI", False, f"HTTP {response.status_code}: {response.text[:50]}...")
    except Exception as e:
        print_result("OpenAI", False, str(e))

def test_elevenlabs():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print_result("ElevenLabs", False, "Missing ELEVENLABS_API_KEY in .env")
        return
        
    try:
        headers = {"xi-api-key": api_key}
        response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=5)
        if response.status_code == 200:
            print_result("ElevenLabs", True, "Successfully authenticated.")
        else:
            print_result("ElevenLabs", False, f"HTTP {response.status_code}: {response.text[:50]}...")
    except Exception as e:
        print_result("ElevenLabs", False, str(e))

def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print_result("Groq", False, "Missing GROQ_API_KEY in .env")
        return
        
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if response.status_code == 200:
            print_result("Groq", True, "Successfully authenticated.")
        else:
            print_result("Groq", False, f"HTTP {response.status_code}: {response.text[:50]}...")
    except Exception as e:
        print_result("Groq", False, str(e))

def test_gemini():
    # You misspelled it as GEMENI_API_KEY in the .env file! Checking for both.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMENI_API_KEY")
    if not api_key:
        print_result("Gemini", False, "Missing GEMINI_API_KEY in .env")
        return
        
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print_result("Gemini", True, "Successfully authenticated.")
        else:
            print_result("Gemini", False, f"HTTP {response.status_code}: {response.text[:50]}...")
    except Exception as e:
        print_result("Gemini", False, str(e))

def test_twitter():
    consumer_key = os.getenv("TWITTER_API_KEY")
    consumer_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")
    
    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        print_result("Twitter", False, "Missing one or more Twitter keys in .env")
        return
        
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_secret
        )
        # Attempt to get the authenticated user's ID
        me = client.get_me()
        if me.data:
            print_result("Twitter", True, f"Authenticated as @{me.data.username}")
        else:
            print_result("Twitter", False, "Failed to fetch user data. Check permissions.")
    except Exception as e:
        print_result("Twitter", False, f"Auth Error (Do you have Read/Write/v2 access?): {e}")

async def test_discord():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print_result("Discord", False, "Missing DISCORD_TOKEN in .env")
        return
        
    import discord
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    auth_success = False
    
    @client.event
    async def on_ready():
        nonlocal auth_success
        auth_success = True
        print_result("Discord", True, f"Authenticated as {client.user}")
        await client.close()
        
    try:
        # We wrap it in a timeout so the script doesn't hang if the token is invalid
        await asyncio.wait_for(client.start(token), timeout=5.0)
    except discord.LoginFailure:
        print_result("Discord", False, "Invalid Token.")
    except asyncio.TimeoutError:
        if auth_success:
            pass # We closed it intentionally
        else:
            print_result("Discord", False, "Connection timed out.")
    except Exception as e:
        if "closed" not in str(e).lower():
            print_result("Discord", False, str(e))


def run_all_tests():
    print("\n====================================")
    print("📡 SKIKAI API CONNECTION TEST 📡")
    print("====================================\n")
    
    test_openai()
    test_elevenlabs()
    test_groq()
    test_gemini()
    test_twitter()
    
    print("\n[Testing Discord async connection...]")
    # Run discord last because of async event loop
    try:
        asyncio.run(test_discord())
    except Exception as e:
        print_result("Discord", False, f"Async crash: {e}")
        
    print("\n====================================")
    print("🏁 DIAGNOSTICS COMPLETE 🏁")
    print("====================================\n")

if __name__ == "__main__":
    run_all_tests()
