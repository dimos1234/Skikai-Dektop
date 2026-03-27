import time
import os
import sys
import threading
import json
import socket

from brain import chat_streamer

def test_intelligence_and_speed():
    print("[Testbench] Running intelligence & speed tests...")
    test_prompts = [
        "What is your name and who created you?",
        "If I have 5 apples and eat 2, then buy 3 more, how many do I have?"
    ]
    total_time = 0
    total_ttft = 0
    try:
        for prompt in test_prompts:
            t0 = time.time()
            generator = chat_streamer(prompt, speaker="TestBench", platform="Local", silent_mode=True)
            first_token_time = None
            response = ""
            for chunk in generator:
                if first_token_time is None:
                    first_token_time = time.time() - t0
                response += chunk
            elapsed = time.time() - t0
            if not response.strip():
                return False, 0, 0
            total_time += elapsed
            total_ttft += first_token_time
        return True, total_ttft / len(test_prompts), total_time / len(test_prompts)
    except Exception as e:
        print(f"[Testbench] Brain Error: {e}")
        return False, 0, 0

def test_discord_router():
    """Ensures that the technical_router correctly identifies Discord intents and fires the right JSON."""
    print("[Testbench] Testing Discord Router Logic...")
    from router import technical_router
    try:
        # We don't want it to actually send a UDP packet, we just want to test the parsing
        raw_output = technical_router("send a message to Alan saying hello")
        if "[DISCORD_ACTION]" in raw_output and "Alan" in raw_output:
            return True
        print(f"[Testbench] Router failed to generate Discord Action. Output: {raw_output}")
        return False
    except Exception as e:
        print(f"[Testbench] Discord Router Error: {e}")
        return False

def test_minecraft_router():
    """Ensures that the technical_router correctly identifies Minecraft intents."""
    print("[Testbench] Testing Minecraft Router Logic...")
    from router import technical_router
    try:
        raw_output = technical_router("mine some dirt")
        if "[MINECRAFT_ACTION]" in raw_output and "mine" in raw_output.lower():
            return True
        print(f"[Testbench] Router failed to generate Minecraft Action. Output: {raw_output}")
        return False
    except Exception as e:
        print(f"[Testbench] Minecraft Router Error: {e}")
        return False

def run_all_benchmarks():
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    
    # 1. Test Core Logic
    brain_ok, avg_ttft, avg_total = test_intelligence_and_speed()
    if not brain_ok:
        with open("benchmark_results.txt", "w") as f: f.write("STATUS=FAILED\nERROR=Brain failed to generate text.")
        return False
        
    # 2. Test Discord Module
    if not test_discord_router():
        with open("benchmark_results.txt", "w") as f: f.write("STATUS=FAILED\nERROR=Discord Router logic broken.")
        return False
        
    # 3. Test Minecraft Module
    if not test_minecraft_router():
        with open("benchmark_results.txt", "w") as f: f.write("STATUS=FAILED\nERROR=Minecraft Router logic broken.")
        return False

    # 4. Cached-turn TTFT: send a follow-up to measure KV cache performance
    cached_ttft = None
    try:
        follow_up = "Okay but what about the other ones?"
        t0 = time.time()
        gen = chat_streamer(follow_up, speaker="TestBench", platform="Local", silent_mode=True)
        for chunk in gen:
            if cached_ttft is None:
                cached_ttft = time.time() - t0
        print(f"[Testbench] Cached-turn TTFT: {cached_ttft:.2f}s")
    except Exception as e:
        print(f"[Testbench] Cached-turn test error: {e}")

    # If everything passed, record the metrics
    print(f"\n[Testbench] SUCCESS. All systems functional. Avg TTFT: {avg_ttft:.2f}s | Avg Total: {avg_total:.2f}s")
    
    if avg_ttft > 8.0:
        with open("benchmark_results.txt", "w") as f: f.write(f"STATUS=FAILED\nERROR=Performance regression. Avg TTFT ({avg_ttft:.2f}s) exceeded 8.0s limit. Remove bloated LLM calls.")
        print(f"[Testbench] FAILED: Performance regression. TTFT too high.")
        return False

    result_lines = f"AVG_TTFT={avg_ttft}\nAVG_TOTAL={avg_total}\nSTATUS=SUCCESS"
    if cached_ttft is not None:
        result_lines += f"\nCACHED_TTFT={cached_ttft}"
        if cached_ttft > 6.0:
            print(f"[Testbench] WARNING: Cached-turn TTFT ({cached_ttft:.2f}s) is above 6s target.")

    with open("benchmark_results.txt", "w") as f:
        f.write(result_lines)
    return True

if __name__ == "__main__":
    success = run_all_benchmarks()
    sys.exit(0 if success else 1)
