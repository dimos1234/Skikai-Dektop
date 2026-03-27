import time
import requests
import threading
import os

class EmotionalEngine:
    def __init__(self):
        # Core emotional vectors (0 to 100)
        self.boredom = 0.0
        self.energy = 80.0
        self.sass = 50.0
        self.urgency = 0.0 # Tracks environmental chaos
        self.instability = 10.0 # 💥 NEW: Drives Neuro-style tangents and random freakouts
        self.last_tick = time.time()
        
        # --- NEW: Asynchronous Intent States ---
        self.current_intent = "She wants to playfully tease Adam."
        self.latest_visual_context = "No recent visual history."
        
        # Target your MacBook's new Llama 3.2 instance
        self.mac_logic_url = os.environ.get("MAC_OLLAMA_URL")
        
        # Fire up the subconscious thinker thread immediately!
        threading.Thread(target=self._background_thinker, daemon=True).start()

    def tick(self, adam_spoke=False, visual_changed=False, is_speaking=False):
        """Called by the heartbeat to drift her emotions."""
        import random
        now = time.time()
        elapsed = now - self.last_tick
        self.last_tick = now
        
        # 💥 THE FIX: Slower decay, and it freezes while she's talking!
        if not is_speaking:
            self.urgency = max(0.0, self.urgency - (elapsed * 3)) 
            self.instability = max(10.0, self.instability - (elapsed * 3)) # Slowly calms down
        
        if adam_spoke:
            self.boredom = max(0.0, self.boredom - 40.0)
            self.energy = min(100.0, self.energy + 15.0)
            self.urgency = min(100.0, self.urgency + 30.0) 
            
            # 💥 THE FIX: If she is already unstable, talking to her grounds her. 
            # If she is stable, it adds a little chaos.
            if self.instability > 70.0:
                self.instability = max(50.0, self.instability - 15.0) 
            else:
                self.instability = min(100.0, self.instability + random.uniform(2.0, 5.0))
        elif visual_changed:
            self.boredom = max(0.0, self.boredom - 5.0)
            self.urgency = min(100.0, self.urgency + 50.0) 
        else:
            self.boredom = min(100.0, self.boredom + (elapsed * 0.5))
            
        if self.boredom > 70.0:
            self.sass = min(100.0, self.sass + (elapsed * 0.2))
            self.instability = min(100.0, self.instability + (elapsed * 0.5)) # Boredom breeds insanity
        else:
            self.sass = max(0.0, self.sass - (elapsed * 0.1))

    def get_mood_string(self):
        """Translates the math into a prompt-ready string."""
        moods = []
        if self.boredom > 80: moods.append("extremely bored and impatient")
        elif self.boredom < 20: moods.append("engaged and focused")
        
        if self.energy > 80: moods.append("hyperactive and loud")
        elif self.energy < 30: moods.append("sluggish, quiet, and tired")
        
        if self.sass > 80: moods.append("ruthlessly sarcastic and completely unfiltered")
        elif self.sass < 30: moods.append("surprisingly docile and helpful")
        
        if self.instability > 75: moods.append("currently having a manic freak-out or existential crisis")
        elif self.instability > 55: moods.append("prone to going on very weird, unprompted tangents")
        
        return ", ".join(moods) if moods else "neutral and observing"

    def update_vision(self, visual_context):
        """Called constantly by main.py so the background thread knows what she is seeing."""
        self.latest_visual_context = visual_context

    def _background_thinker(self):
        """Runs forever in the background, updating her intent every 10 seconds."""
        print("\n[Subconscious: Llama 3.2 Thinker Thread Initialized.]")
        while True:
            time.sleep(10) # Process intent every 10 seconds to spare Mac CPU
            mood = self.get_mood_string()
            
            intent_prompt = f"""You are the subconscious brain of Skikai, an AI VTuber. 
            Current Mood: {mood}
            Recent Screen Context: {self.latest_visual_context}
            
            Based on this, what is Skikai's general hidden intent right now? 
            Write exactly ONE short sentence describing her current motive (e.g., 'She wants to mock him for dying', 'She is bored and wants to complain', 'She wants to help him code'). Do not write dialogue."""

            payload = {
                "model": "llama3.2",
                "prompt": intent_prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 30}
            }

            try:
                response = requests.post(self.mac_logic_url, json=payload, timeout=3)
                if response.status_code == 200:
                    self.current_intent = response.json().get("response", "").strip()
            except:
                pass

    def get_instant_intent(self):
        """Called when you speak. Returns the pre-calculated intent instantly with ZERO latency!"""
        return self.current_intent
        
    def generate_forced_intent(self, visual_context, user_input):
        """Used ONLY for proactive interjections (like visual triggers) where latency doesn't matter."""
        mood = self.get_mood_string()
        
        intent_prompt = f"""You are the subconscious brain of Skikai, an AI VTuber. 
        Current Mood: {mood}
        Recent Screen Context: {visual_context}
        Adam's Input/Action: {user_input}
        
        Based on this, what is Skikai's hidden intent for her next response? 
        Write exactly ONE short sentence describing what she wants to achieve."""

        payload = {
            "model": "llama3.2",
            "prompt": intent_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 30}
        }

        try:
            response = requests.post(self.mac_logic_url, json=payload, timeout=2)
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except:
            pass
        return "She wants to react to the current situation."

# Global instance to be imported by main.py
engine = EmotionalEngine()