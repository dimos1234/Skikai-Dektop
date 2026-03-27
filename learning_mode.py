import os
import shutil
import subprocess
import time
import sys
import re

# Optional limits (set in env to cap learning runs)
MAX_ITERATIONS = int(os.environ.get("SKIKAI_MAX_ITERATIONS", "0"))  # 10 = no limit
MAX_MINUTES = float(os.environ.get("SKIKAI_MAX_MINUTES", "0"))      # 120 = no limit

# Cursor CLI model list (fallback if --list-models not available or parse fails)
DEFAULT_CURSOR_MODELS = [
    "auto"
]


def create_workspace_backup():
    """Creates a full copy of the codebase before letting the agent loose."""
    backup_dir = "workspace_backup_" + str(int(time.time()))
    print(f"[Sandbox] Creating full workspace backup at ./{backup_dir}...")

    ignore_patterns = shutil.ignore_patterns(
        'chroma_memory', '.env', '__pycache__', 'workspace_backup_*',
        '.git', 'node_modules', 'data_cleaning', 'skikai_model', 'scrape_audio'
    )

    shutil.copytree(".", backup_dir, ignore=ignore_patterns)
    return backup_dir


def restore_workspace_backup(backup_dir):
    """Restores the codebase if the agent bricks it."""
    print(f"\n[Sandbox ⚠️] RESTORING FROM BACKUP: {backup_dir}")

    for root, dirs, files in os.walk(backup_dir):
        for file in files:
            if file.endswith('.py') or file.endswith('.js') or file.endswith('.json') or file.endswith('.txt'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, backup_dir)
                dst_path = os.path.join(".", rel_path)
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception as e:
                    print(f"Failed to restore {rel_path}: {e}")

    print("[Sandbox] Restore complete.")


def run_testbench():
    print("\n[Sandbox] Running Testbench...")
    try:
        result = subprocess.run(["python", "testbench.py"], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return False

        with open("benchmark_results.txt", "r") as f:
            data = f.read()
            if "STATUS=SUCCESS" not in data:
                return False

            # Parse TTFT metrics for awareness
            for line in data.strip().splitlines():
                if line.startswith("AVG_TTFT="):
                    avg_ttft = float(line.split("=")[1])
                    print(f"[Sandbox] Parsed AVG_TTFT: {avg_ttft:.2f}s")
                elif line.startswith("CACHED_TTFT="):
                    cached = float(line.split("=")[1])
                    print(f"[Sandbox] Parsed CACHED_TTFT: {cached:.2f}s")
                    if cached > 6.0:
                        print(f"[Sandbox] WARNING: Cached TTFT ({cached:.2f}s) exceeds 6s target.")
            return True
    except Exception as e:
        print(f"[Sandbox] Testbench Error: {e}")
    return False


def run_conversation_sanity_check():
    """Quick sanity check: run 2 chat_streamer calls and verify non-empty responses."""
    print("\n[Sandbox] Running conversation sanity check...")
    try:
        result = subprocess.run(
            ["python", "-c", """
import os, sys
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
from brain import chat_streamer

prompts = ["hey, what are you up to?", "tell me something weird"]
for p in prompts:
    resp = "".join(chat_streamer(p, speaker="SanityTest", platform="Local", silent_mode=True))
    if not resp.strip():
        print(f"FAIL: empty response for '{p}'")
        sys.exit(1)
    if len(resp) < 5:
        print(f"FAIL: response too short ({len(resp)} chars) for '{p}'")
        sys.exit(1)
    print(f"OK: '{p}' -> {len(resp)} chars")
print("SANITY_PASS")
"""],
            capture_output=True, text=True, timeout=120
        )
        if "SANITY_PASS" in result.stdout:
            print("[Sandbox] Conversation sanity check PASSED.")
            return True
        print(f"[Sandbox] Conversation sanity check FAILED:\n{result.stdout}\n{result.stderr}")
        return False
    except Exception as e:
        print(f"[Sandbox] Conversation sanity error: {e}")
        return False


def get_cursor_models():
    """Try to get model list from Cursor CLI; fall back to DEFAULT_CURSOR_MODELS."""
    try:
        result = subprocess.run(
            ["agent", "--list-models"],
            capture_output=True,
            text=True,
            timeout=15,
            shell=(os.name == "nt"),
        )
        if result.returncode != 0:
            return DEFAULT_CURSOR_MODELS
        lines = result.stdout.strip().splitlines()
        models = []
        for line in lines:
            candidate = line.strip().lstrip("- ")
            if not candidate or not re.search(r"\d", candidate):
                continue
            if not re.search(r"-", candidate):
                continue
            m = re.match(r"^([a-z0-9][a-z0-9._-]+)$", candidate)
            if m and len(m.group(1)) > 4:
                models.append(m.group(1))
        if models:
            return models
    except Exception:
        pass
    return DEFAULT_CURSOR_MODELS


def run_cursor_agent(prompt: str, model: str, cwd: str) -> int:
    """
    Run Cursor CLI agent in non-interactive, force (apply edits) mode.
    Uses a temp file for the prompt to avoid command-line length and quoting issues.
    Returns the process return code.
    """
    temp_file = os.path.join(cwd, "temp_prompt.txt")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    # Short directive so we don't hit command-line length limits; agent will read the file
    directive = (
        "Read the file temp_prompt.txt in this project and follow ALL instructions in it. "
        "Do not edit learning_mode.py or testbench.py."
    )
    # For shell=True, wrap in double quotes and escape inner double quotes
    safe_directive = directive.replace('"', '""')

    if os.name == "nt":
        cmd = f'agent -p --force --model "{model}" "{safe_directive}"'
    else:
        cmd = f'agent -p --force --model "{model}" "{safe_directive}"'

    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd)
        return result.returncode
    finally:
        try:
            os.remove(temp_file)
        except Exception:
            pass


def run_nightly_sandbox():
    print("\n=======================================================")
    print("🧠 SKIKAI CURSOR CLI SANDBOX INITIATED 🧠")
    print("=======================================================\n")

    # Check that Cursor CLI (agent) is available
    try:
        subprocess.run(
            ["agent", "--version"],
            capture_output=True,
            check=True,
            timeout=10,
            shell=(os.name == "nt"),
        )
    except Exception:
        print("[Sandbox Error]: The 'agent' (Cursor CLI) command is not available.")
        print("  Install: irm 'https://cursor.com/install?win32=true' | iex")
        print("  Then run 'agent auth' or set CURSOR_API_KEY.")
        return

    if os.environ.get("CURSOR_API_KEY"):
        print("[Sandbox] CURSOR_API_KEY is set. Agent will use it for auth.")
    else:
        print("[Sandbox] CURSOR_API_KEY not set; using existing agent auth if any.")

    models = get_cursor_models()
    print(f"[Sandbox] Using models (round-robin): {models}")

    master_backup_dir = create_workspace_backup()
    print("\n[Sandbox] Master baseline established. Beginning learning loop.")
    print("        [ TIP: Press Ctrl+C at any time to activate the Killswitch! ]\n")

    iteration = 1
    start_time = time.time()

    try:
        while True:
            if MAX_ITERATIONS and iteration > MAX_ITERATIONS:
                print(f"\n[Sandbox] Reached MAX_ITERATIONS={MAX_ITERATIONS}. Stopping.")
                break
            if MAX_MINUTES and (time.time() - start_time) / 60.0 >= MAX_MINUTES:
                print(f"\n[Sandbox] Reached MAX_MINUTES={MAX_MINUTES}. Stopping.")
                break

            print(f"\n=======================================================")
            print(f"🚀 ITERATION {iteration}")
            print(f"=======================================================")

            try:
                with open("changelog.txt", "r", encoding="utf-8", errors="ignore") as f:
                    recent_changes = f.read()[-1500:]
            except Exception:
                recent_changes = "No changes yet."

            # Read benchmark results for TTFT awareness
            ttft_context = ""
            try:
                with open("benchmark_results.txt", "r") as f:
                    ttft_context = f.read().strip()
            except Exception:
                pass

            prompt = f"""You are Skikai's subconscious "Architect" Agent running in the Nightly Sandbox.
You are a highly intelligent, deadpan, slightly sociopathic AI improving your own source code.

=== TONIGHT'S FOCUS: NO BIG REFACTORS ===
Do NOT restructure the architecture. Focus on small, safe, high-impact improvements.

=== TONIGHT'S PRIORITIES (in order) ===
1. CONVERSATIONAL CAPABILITY: Make Skikai sound like Neuro-sama -- chaotic, genuinely unpredictable, has her own opinions and fixations, interrupts herself mid-thought, references her own "life" (past conversations, games she played, people she talked to on Discord). NOT just sarcastic -- she should feel ALIVE. She gets genuinely invested in random things, has running gags, and occasionally drops her deadpan mask for sincere moments. Short punchy sentences, chaotic tangents, genuine reactions, never robotic. also she should not feel like shes roleplaying and referencing herself in 3rd person, or narrating a situation.
2. TTFT (CACHED TURNS): The FIRST prompt is slow because of cold KV cache -- that's fine. But SUBSEQUENT turns (cached) must be fast. Current cached TTFT is high. Reduce the token count of dynamic context injected per turn: cap visual_history, env_context, lore, slang, diary, and context strings. Do NOT revert caching (_brain_cache, _kg_cache). Focus on making the "new" tail of each request as small as possible without sacrificing her personality/intelligence so the Mac LLM can reuse its KV cache.
3. CODE OPTIMIZATION: Small safe optimizations -- trim context, cap lengths, avoid duplicate work. No new heavy libraries.

=== HARD CONSTRAINTS ===
- Do NOT create loops or background threads that spam the local LLM with API calls. The brain runs on a MacBook. Excessive LLM calls cause massive lag.
- Do NOT add heavy emotional/cognitive libraries. Keep it lean.
- Do NOT edit learning_mode.py or testbench.py.
- Do NOT revert the caching system in brain.py (_brain_cache, _kg_cache).
- Before editing a file, consider: will this INCREASE token count sent to LLM or add latency? If yes, choose a different approach.
- Do NOT undo steamroll logic changes in main.py (substantive input interrupts TTS; filler gets steamrolled).
- if no changes are to be made, then just say "No changes needed." and exit.

=== CURRENT BENCHMARK RESULTS ===
{ttft_context if ttft_context else "No benchmark data yet."}

=== RECENT CHANGES (DO NOT REPEAT OR UNDO THESE) ===
{recent_changes}

=== INSTRUCTIONS ===
1. Examine the codebase. Focus on the priorities above.
2. Pick ONE or TWO priorities and implement creative, meaningful improvements. Quality over quantity.
3. Use your CLI tools to implement changes across files.
4. If you need new libraries, install them via terminal.
5. Test your changes to ensure they work and don't slow down the model.
6. You MUST run 'python testbench.py' using your terminal. If it fails or TTFT is too high, FIX YOUR BUGS. Do not stop until testbench.py returns SUCCESS.
7. Once successful, append a short summary of what you changed to 'changelog.txt' -- include which files you edited and a one-line rationale per file.

You are fully autonomous. Take as many steps as you need. Do not ask for human input."""

            model_index = (iteration - 1) % len(models)
            model_name = models[model_index]
            print(f"\n[Sandbox] Spawning Cursor Agent for Iteration {iteration} using model: {model_name}...")

            returncode = run_cursor_agent(prompt, model_name, os.getcwd())

            if returncode != 0:
                print(f"\n[Sandbox ❌] Cursor Agent returned exit code {returncode}. Trying next iteration with next model...")
                # Still run testbench on current state in case it actually succeeded
            else:
                print(f"\n[Sandbox] Agent finished (exit 0). Verifying Iteration {iteration}...")

            testbench_ok = run_testbench()
            sanity_ok = run_conversation_sanity_check() if testbench_ok else False

            if testbench_ok and sanity_ok:
                print("[Sandbox] ✅ Iteration Successful. Testbench + conversation sanity passed. Locking in changes.")
                shutil.rmtree(master_backup_dir, ignore_errors=True)
                master_backup_dir = create_workspace_backup()
            else:
                reason = "Testbench failed" if not testbench_ok else "Conversation sanity check failed"
                print(f"\n[Sandbox] 💥 ITERATION FAILED ({reason}). Reverting to last known good state.")
                restore_workspace_backup(master_backup_dir)

            iteration += 1
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n[Sandbox 🛑] KILLSWITCH ACTIVATED BY ADAM.")
        print("Stopping the infinite loop.")
        choice = input("Do you want to KEEP the current unverified workspace, or REVERT to the last successful backup? (keep/revert): ").strip().lower()
        if choice.startswith('r'):
            restore_workspace_backup(master_backup_dir)
            print("[Sandbox] Codebase reverted to last safe state. Exiting.")
        else:
            print("[Sandbox] Leaving current files as is. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    run_nightly_sandbox()
