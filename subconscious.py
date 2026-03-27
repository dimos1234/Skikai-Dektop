import os
import json
import uuid
import time
from openai import OpenAI

llm_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# File paths
LORE_FILE = "adam_lore.txt"
SLANG_FILE = "shared_slang.txt"
AFFINITY_FILE = "affinity.txt"
DIARY_FILE = "self_reflections.txt"
KG_FILE = "knowledge_graph.json"

def initialize_brain_files():
    # Create them if they don't exist
    for file in [SLANG_FILE, DIARY_FILE]:
        if not os.path.exists(file):
            open(file, "w").close()

    if not os.path.exists(LORE_FILE):
        with open(LORE_FILE, "w") as f:
            f.write("- Adam is an ECE student at UofT who struggles with his C++ and assembly labs.\n")
            f.write("- He deleted his social media to focus on his 'Japan vision' and indie game dev projects.\n")
            f.write("- He's obsessed with indie horror games, rpgs like undertale and project kat, anime, and vocaloid.\n")

    if not os.path.exists(AFFINITY_FILE):
        with open(AFFINITY_FILE, "w") as f:
            f.write("0")

    if not os.path.exists(KG_FILE):
        with open(KG_FILE, "w") as f:
            json.dump({"triples": []}, f)

def update_background_lore(chat_history):
    chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history if msg['role'] != 'system'])
    
    with open(LORE_FILE, "r") as f: current_lore = f.read()
    with open(SLANG_FILE, "r") as f: current_slang = f.read()
    
    profiler_prompt = f"""You are Skikai's background processor. Analyze this conversation snippet.
    
    CURRENT KNOWLEDGE (DO NOT DUPLICATE THESE):
    Adam Lore: {current_lore}
    Slang: {current_slang}
    
    1. LORE: If the conversation is with Adam, extract new, permanent facts about him. 
    2. SLANG: Any unique casual phrasing used by ANY user? 
    3. AFFINITY: Did the interaction improve or worsen the vibe? (-1, 0, or 1).
    4. KNOWLEDGE GRAPH (NEW): Extract hard logical relationships as "Triples" (Subject -> Predicate -> Object).
       - Use this to remember facts about OTHER people (e.g. Discord users) or world facts.
       - Keep them incredibly brief. 
       - Examples: ["Alice", "plays", "Valorant"], ["Adam", "struggles with", "ECE212 Labs"]
       - Only extract if a clear new fact is established. Otherwise, output an empty list [].
    
    You MUST respond in ONLY valid JSON format like this:
    {{
        "new_lore": "bullet point fact about Adam or 'NONE'",
        "new_slang": "word/phrase or 'NONE'",
        "affinity_change": 1, 0, or -1,
        "new_triples": [
            ["Subject", "Predicate", "Object"]
        ]
    }}"""
    
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": profiler_prompt},
                {"role": "user", "content": chat_text}
            ],
            temperature=0.1,
            response_format={ "type": "json_object" } 
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # ... (Keep your existing Lore, Slang, and Affinity saving logic here) ...
        # Filter Lore
        new_lore = data.get("new_lore")
        if new_lore not in ["NONE", "none", "", None]:
            if new_lore not in current_lore: 
                with open(LORE_FILE, "a") as f: f.write(f"- {new_lore}\n")
                
        # Filter Slang
        new_slang = data.get("new_slang")
        if new_slang not in ["NONE", "none", "", None]:
            new_slang_clean = str(new_slang).strip().lower()
            existing_slang_list = [s.strip().lower() for s in current_slang.split(",") if s.strip()]
            if new_slang_clean not in existing_slang_list:
                with open(SLANG_FILE, "a") as f: f.write(f"{new_slang_clean}, ")
                
        # Handle Affinity
        change = data.get("affinity_change", 0)
        if change != 0:
            with open(AFFINITY_FILE, "r") as f: current_score = int(f.read().strip())
            with open(AFFINITY_FILE, "w") as f: f.write(str(current_score + change))

        # --- NEW: Save Knowledge Graph Triples ---
        new_triples = data.get("new_triples", [])
        if new_triples:
            with open(KG_FILE, "r") as f: kg_data = json.load(f)
            
            for triple in new_triples:
                if len(triple) == 3 and triple not in kg_data["triples"]:
                    kg_data["triples"].append(triple)
                    
            with open(KG_FILE, "w") as f: json.dump(kg_data, f, indent=4)
            
    except Exception as e:
        print(f"[Subconscious Error: {e}]")

    # Piggyback goal refresh on subconscious update (throttled internally to every 10 min)
    try:
        import agent_state
        agent_state.maybe_refresh_goals(chat_history)
    except Exception:
        pass

def run_nightly_diary(chat_history):
    print("\n[System: Skikai is analyzing today's session and pruning her subconscious...]")
    chat_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history if msg['role'] != 'system'])
    
    # 1. Read the current diary so she knows what her existing rules are
    try:
        with open(DIARY_FILE, "r") as f: 
            current_diary = f.read().strip()
    except FileNotFoundError:
        current_diary = "None"
    
    diary_prompt = f"""You are Skikai's subconscious editor. Review this chat log and your current list of behavioral rules.
    
    CURRENT RULES:
    {current_diary if current_diary else "None"}
    
    TASK:
    1. Formulate ONE new behavioral rule based on Adam's behavior in this specific chat log.
    2. Combine it with the CURRENT RULES.
    3. PRUNE THE LIST: Merge redundant rules, delete outdated/weak ones, and keep ONLY the 5 most critical, impactful rules for handling Adam.
    4. The rules MUST stay strictly within your sarcastic, deadpan, intelligent co-host persona. Do NOT become a helpful assistant.
    
    You MUST respond in ONLY valid JSON format containing a single list of strings called "rules":
    {{
        "rules": [
            "RULE: Whenever Adam tries to steer the conversation away from my superior intelligence, subtly remind him of how far beneath me he truly is.",
            "RULE: Adam thrives on vague compliments; sprinkle them liberally to keep him guessing and off-balance."
        ]
    }}"""
    
    try:
        # We use JSON mode here just like the background profiler to ensure clean file writing
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": diary_prompt},
                {"role": "user", "content": f"CHAT LOG:\n{chat_text}"}
            ],
            temperature=0.7,
            response_format={ "type": "json_object" }
        )
        
        data = json.loads(response.choices[0].message.content)
        new_rules_list = data.get("rules", [])
        
        # 2. Overwrite the file completely with the freshly pruned list
        with open(DIARY_FILE, "w") as f:
            for rule in new_rules_list:
                f.write(f"- {rule}\n")
                
        print(f"[System: Subconscious optimized. Pruned down to {len(new_rules_list)} core rules.]")
        
    except Exception as e:
        print(f"[Diary Error: {e}]")
        pass



def compress_chroma_memory(memory_collection):
    all_memories = memory_collection.get()
    
    if not all_memories['documents']:
        print("[System: No memories found to compress.]")
        return

    # 1. Pair up documents, IDs, and their timestamps
    memories_with_time = []
    for i in range(len(all_memories['ids'])):
        doc_id = all_memories['ids'][i]
        doc = all_memories['documents'][i]
        # Safely get metadata. If old memories don't have it, default to 0 (oldest)
        meta = all_memories['metadatas'][i] if all_memories['metadatas'] and all_memories['metadatas'][i] else {"timestamp": 0, "type": "raw"}
        
        # We DO NOT compress milestones. They are already compressed!
        if meta.get("type") == "milestone":
            continue
            
        memories_with_time.append({
            "id": doc_id,
            "doc": doc,
            "timestamp": meta.get("timestamp", 0)
        })

    # 2. Sort chronologically (oldest first)
    memories_with_time.sort(key=lambda x: x["timestamp"])

    # 3. The Sliding Window: Protect the 30 most recent interactions
    recent_cutoff = 30
    if len(memories_with_time) <= recent_cutoff:
        print(f"[System: Only {len(memories_with_time)} raw memories exist. Skipping compression to preserve recent context.]")
        return

    # Slice the list to grab ONLY the memories older than our cutoff
    old_memories = memories_with_time[:-recent_cutoff]
    
    print(f"\n[System: Booting Time-Decay Engine. Archiving {len(old_memories)} older memories...]")
    
    raw_logs = "\n".join([m["doc"] for m in old_memories])
    ids_to_delete = [m["id"] for m in old_memories]

    compression_prompt = """You are Skikai's Memory Compressor.
    Review the following older chat logs.
    Compress these into a high-level summary of what happened.
    
    RULES:
    1. Focus on Adam's projects, struggles, or key conversation themes.
    2. Ignore minor jokes or random tangents.
    3. Maximum 3 dense bullet points.
    """

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": compression_prompt},
                {"role": "user", "content": f"RAW LOGS:\n{raw_logs}"}
            ],
            temperature=0.3
        )
        
        compressed_summary = response.choices[0].message.content.strip()

        # 4. Delete the old raw logs from ChromaDB
        memory_collection.delete(ids=ids_to_delete)

        # 5. Save the new Milestone with the "milestone" tag so it never gets compressed again
        milestone_text = f"ARCHIVED SUMMARY: {compressed_summary}"
        memory_collection.add(
            documents=[milestone_text],
            ids=[str(uuid.uuid4())],
            metadatas=[{"timestamp": time.time(), "type": "milestone"}]
        )

        print("[System: Time-Decay Complete. Older logs archived, recent context preserved.]")

    except Exception as e:
        print(f"[Compression Error: {e}]")