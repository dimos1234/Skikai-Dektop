import os
from openai import OpenAI
from dotenv import load_dotenv
import time

load_dotenv()

# Grabs the IP from your .env
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

print(f"Attempting to ping OpenAI")

t0 = time.time()
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Explain quantum physics in one sentence."}],
        stream=True,
        max_tokens=50
    )
    
    print("Connection established. Waiting for tokens...\n")
    
    for chunk in response:
        if getattr(chunk, 'choices', None) and len(chunk.choices) > 0:
            content = getattr(chunk.choices[0].delta, 'content', None)
            if content:
                print(content, end="", flush=True)
                
    print(f"\n\n[Success! Total time: {time.time() - t0:.2f}s]")

except Exception as e:
    print(f"\n[Network Error]: {e}")