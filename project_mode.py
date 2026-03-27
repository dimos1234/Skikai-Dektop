"""
Project Mode handler for Skikai.

Routes user input to specialized handlers when in project/collaboration mode:
- Idea bouncing (discussion with project context)
- Code review / tutoring (read files, explain, find bugs)
- Script generation (invoke Cursor CLI or generate inline)
"""

import os
import subprocess
import threading

from brain import chat_streamer, short_term_memory
import voice
import config


# Active project context (set when entering project mode)
_project_context = {
    "path": None,       # workspace path being worked on
    "description": "",  # user-provided project description
}


def set_project(path=None, description=""):
    _project_context["path"] = path
    _project_context["description"] = description


def _build_project_system_note():
    parts = ["[PROJECT MODE ACTIVE]"]
    if _project_context["description"]:
        parts.append(f"Project: {_project_context['description']}")
    if _project_context["path"] and os.path.isdir(_project_context["path"]):
        try:
            files = os.listdir(_project_context["path"])[:20]
            parts.append(f"Workspace files: {', '.join(files)}")
        except Exception:
            pass
    return " | ".join(parts)


def _detect_intent(text):
    """Classify what the user wants in project mode."""
    lower = text.lower()

    if any(kw in lower for kw in ["write a script", "generate code", "create a script",
                                   "write code", "make a script", "code this"]):
        return "script"

    if any(kw in lower for kw in ["review", "look at", "check this", "find bugs",
                                   "what's wrong", "debug this", "read this file"]):
        return "review"

    if any(kw in lower for kw in ["tutor", "explain", "teach me", "how does",
                                   "help me understand", "walk me through", "what does"]):
        return "tutor"

    # Default: idea bouncing / general discussion
    return "discuss"


def _read_file_for_context(file_path):
    """Read a file and return its contents (capped for LLM context)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if len(content) > 3000:
            content = content[:3000] + "\n... (truncated)"
        return content
    except Exception as e:
        return f"(Could not read file: {e})"


def _extract_file_path(text):
    """Try to extract a file path from user input."""
    import re
    patterns = [
        r'"([^"]+\.[a-zA-Z]+)"',
        r"'([^']+\.[a-zA-Z]+)'",
        r'`([^`]+\.[a-zA-Z]+)`',
        r'(\S+\.[a-zA-Z]{1,5})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1)
            if os.path.isfile(candidate):
                return candidate
            if _project_context["path"]:
                full = os.path.join(_project_context["path"], candidate)
                if os.path.isfile(full):
                    return full
    return None


def _handle_script_request(user_input, speaker):
    """Handle script generation requests via Cursor CLI or inline generation."""
    project_note = _build_project_system_note()
    prompt = (
        f"{project_note}\n\n"
        f"[SCRIPT REQUEST] {speaker} asked you to write code: '{user_input}'\n\n"
        "You are in project mode. Generate the requested code/script directly in your response. "
        "Write clean, well-structured code. Explain briefly what it does. "
        "If the request is vague, ask a clarifying question first."
    )
    return chat_streamer(prompt, speaker=speaker, platform="Voice", silent_mode=False)


def _handle_review(user_input, speaker):
    """Handle code review requests — read a file and provide feedback."""
    file_path = _extract_file_path(user_input)
    file_content = ""
    if file_path:
        file_content = f"\n\n[FILE CONTENTS ({file_path})]:\n{_read_file_for_context(file_path)}"

    project_note = _build_project_system_note()
    prompt = (
        f"{project_note}\n\n"
        f"[CODE REVIEW] {speaker} wants you to review code: '{user_input}'{file_content}\n\n"
        "Review the code. Point out bugs, improvements, and style issues. Be direct and specific. "
        "If no file was provided, ask which file to look at."
    )
    return chat_streamer(prompt, speaker=speaker, platform="Voice", silent_mode=False)


def _handle_tutor(user_input, speaker):
    """Handle tutoring requests — explain concepts or walk through solutions."""
    file_path = _extract_file_path(user_input)
    file_content = ""
    if file_path:
        file_content = f"\n\n[REFERENCE MATERIAL ({file_path})]:\n{_read_file_for_context(file_path)}"

    project_note = _build_project_system_note()
    prompt = (
        f"{project_note}\n\n"
        f"[TUTORING] {speaker} needs help understanding: '{user_input}'{file_content}\n\n"
        "You are tutoring. Explain clearly but stay in character. Use examples. "
        "Ask follow-up questions to check understanding. Don't just dump the answer — guide them."
    )
    return chat_streamer(prompt, speaker=speaker, platform="Voice", silent_mode=False)


def _handle_discuss(user_input, speaker):
    """Handle idea bouncing — general project discussion."""
    project_note = _build_project_system_note()
    prompt = (
        f"{project_note}\n\n"
        f"[IDEA BOUNCING] {speaker} said: '{user_input}'\n\n"
        "You are collaborating on a project. Engage with the idea — ask questions, suggest alternatives, "
        "poke holes in the plan, or build on it. Be opinionated and creative. Stay in character."
    )
    return chat_streamer(prompt, speaker=speaker, platform="Voice", silent_mode=False)


def handle_project_input(user_input, speaker="Adam"):
    """
    Main entry point for project mode input. Classifies intent and routes
    to the appropriate handler. Returns a generator (same interface as chat_streamer).
    """
    # Allow setting project path via voice command
    lower = user_input.lower()
    if lower.startswith("set project ") or lower.startswith("project path "):
        path = user_input.split(" ", 2)[-1].strip().strip('"').strip("'")
        if os.path.isdir(path):
            set_project(path=path)
            msg = f"got it. project path set to {path}."
        else:
            msg = f"that path doesn't exist: {path}"
        print(f"AI: {msg}")
        voice.speak(msg)
        return None

    if lower.startswith("project is ") or lower.startswith("working on "):
        desc = user_input.split(" ", 2)[-1].strip()
        _project_context["description"] = desc
        msg = f"noted. you're working on: {desc}"
        print(f"AI: {msg}")
        voice.speak(msg)
        return None

    intent = _detect_intent(user_input)
    print(f"[Project Mode] Detected intent: {intent}")

    handlers = {
        "script": _handle_script_request,
        "review": _handle_review,
        "tutor": _handle_tutor,
        "discuss": _handle_discuss,
    }

    handler = handlers.get(intent, _handle_discuss)
    return handler(user_input, speaker)
