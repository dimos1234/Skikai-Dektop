import os
import tweepy
import random
import time

# 💥 CHANGED: Import the OpenAI client from your updated brain.py
from brain import openai_client

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# If keys are present, setup Tweepy
twitter_api = None
if all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
    try:
        # V2 API Client
        twitter_api = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET
        )
        print("[System: 🐦 Skikai's Twitter Module is Online.]")
    except Exception as e:
        print(f"[Twitter Setup Error: {e}]")
else:
    print("[System: 🐦 Twitter keys missing. Social Media Autonomy will run in MOCK mode.]")


def generate_autonomous_tweet(mood_context, env_context, recent_events):
    """Generates a deadpan, chronically online tweet based on her current mood and what you're doing."""
    
    prompt = f"""You are Skikai, an autonomous AI entity created by Adam. You manage your own Twitter account.
    You are chaotic, deadpan, and tease your creator mercilessly. Talk like a chronically online vtuber (all lowercase, no emojis, no hashtags unless ironic).
    
    Current Vibe: {mood_context}
    Current Environment: {env_context}
    Recent Events: {recent_events}
    
    Task: Write a single, short tweet (under 140 characters). Complain about Adam, comment on a recent event, or post an unhinged philosophical thought. Do NOT use quotation marks. Just the tweet text.
    """
    
    try:
        # 💥 CHANGED: The official OpenAI call using gpt-4o-mini
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Skikai. Write a short tweet."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.8
        )
        
        # Extract the text and clean up any hallucinated quotes
        tweet_content = response.choices[0].message.content.strip().replace('"', '').replace("'", "")
        return tweet_content
        
    except Exception as e:
        print(f"[Tweet Generation Error: {e}]")
        return "my creator forgot to feed the server hamster again."

def execute_autonomous_tweet(mood, env, events):
    """Called by main.py during extreme boredom or randomly throughout the day."""
    tweet = generate_autonomous_tweet(mood, env, events)
    print(f"\n[🐦 Skikai is Tweeting]: {tweet}")
    
    if twitter_api:
        try:
            twitter_api.create_tweet(text=tweet)
            print("[Twitter: Post successful!]")
            return f"I just tweeted: '{tweet}'. It's out in the wild now."
        except Exception as e:
            print(f"[Twitter Post Error: {e}]")
            return f"I tried to tweet '{tweet}' but the bird app rejected me."
    else:
        # Mock mode
        return f"I just thought about tweeting: '{tweet}'. But my API keys are missing so I'll just say it to you instead."