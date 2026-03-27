import os
from openai import OpenAI

cloud_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Expanded list to cover more subtle human behaviors
VALID_ACTIONS = [
    "nod", "point", "laugh", "angry", "shake_head", "excited",
    "pose", "lean_forward", "think", "shrug", "tilt_head",
    "glance_away", "sigh", "pout", "smug", "surprise",
]

IDLE_ACTION = "idle"

def classify_action(raw_action_text):
    """Translates roleplay text or emotional state into Warudo triggers with Neuro-sama style fluidity."""
    
    prompt = f"""You are the animation director for Skikai, a high-fidelity AI VTuber.
    Skikai is deadpan, slightly sociopathic, but very expressive with her model.
    
    Input: "{raw_action_text}"
    
    Task: Map this to ONE animation from this list: {VALID_ACTIONS}.
    
    Guidelines:
    - '*sighs*' or boredom -> sigh or lean_forward.
    - '*roasts you*' or teasing -> smug or point.
    - '*is confused*' -> tilt_head or think.
    - '*ignores you*' -> glance_away.
    - '*is happy*' -> excited or laugh.
    - If she is being arrogant -> smug or pose.
    
    Pick the one that fits the emotional 'micro-movement' of a human.
    RESPOND WITH ONLY THE EXACT WORD FROM THE LIST."""
    
    try:
        response = cloud_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4, # Gives it just enough room to map unlisted actions to your valid ones
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip().lower()
        
        # Failsafe: check if the LLM's word is actually inside your locked list
        for action in VALID_ACTIONS:
            if action in result:
                return action
                
    except Exception as e:
        print(f"[Animator Error: {e}]")
        
    return None