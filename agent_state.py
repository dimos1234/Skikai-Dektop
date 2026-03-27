"""
Agent State: unified snapshot of Skikai's current situation + goals layer.
Injected into brain context each turn so she can reason holistically.
"""
import os
import json
import time

GOALS_FILE = "skikai_goals.json"
_goals: list[dict] = []
_goals_load_time: float = 0.0


def _load_goals():
    global _goals, _goals_load_time
    if time.time() - _goals_load_time < 30:
        return
    try:
        with open(GOALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _goals = data.get("goals", [])
    except (FileNotFoundError, json.JSONDecodeError):
        _goals = []
    _goals_load_time = time.time()


def _save_goals():
    global _goals_load_time
    try:
        with open(GOALS_FILE, "w", encoding="utf-8") as f:
            json.dump({"goals": _goals, "updated": time.time()}, f, indent=2)
        _goals_load_time = time.time()
    except Exception as e:
        print(f"[Goals] Save error: {e}")


def get_goals() -> list[dict]:
    _load_goals()
    return list(_goals)


def set_goals(new_goals: list[str]):
    """Replace current goals with a new list. Each goal is a short string."""
    global _goals
    _goals = [{"text": g, "created": time.time()} for g in new_goals]
    _save_goals()


def initialize_default_goals():
    """Set starter goals if none exist."""
    _load_goals()
    if not _goals:
        set_goals([
            "Make Adam laugh at least once per session",
            "Try something new this session",
            "Remember something from a past conversation and bring it up",
        ])


def get_state_snapshot() -> str:
    """
    Build a compact one-block summary of Skikai's full state.
    Called by brain.py each turn for context injection.
    """
    _load_goals()
    if _goals:
        goal_strs = [g["text"] for g in _goals[:3]]
        return "Goals: " + "; ".join(goal_strs)
    return ""


def maybe_refresh_goals(chat_history: list[dict]):
    """
    Periodically re-evaluate goals using a cheap cloud LLM call.
    Called by subconscious every N turns (piggybacks on update_background_lore).
    Skips if goals were updated recently (< 10 min).
    """
    _load_goals()
    if _goals and time.time() - _goals_load_time < 600:
        return

    state = get_state_snapshot()
    if not state:
        initialize_default_goals()
        return

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        prompt = f"""You are Skikai's goal-planning subsystem. Given her current state, output 1-3 short-term goals.

Current state: {state}

Rules:
- Goals should be specific, actionable, and achievable in one session.
- At least one goal should relate to social interaction or personality.
- Keep each goal to one short sentence.

Respond in JSON: {{"goals": ["goal1", "goal2", "goal3"]}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        new_goals = data.get("goals", [])
        if new_goals:
            set_goals(new_goals)
            print(f"[Goals] Updated: {new_goals}")
    except Exception as e:
        print(f"[Goals] Refresh error: {e}")
        if not _goals:
            initialize_default_goals()


# Initialize on import
initialize_default_goals()
