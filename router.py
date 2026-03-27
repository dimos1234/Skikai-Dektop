import os
import json
import time
from openai import OpenAI
from search import perform_web_search

cloud_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
WORKSPACE_DIR = "skikai_workspace"
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def technical_router(user_input):
    """
    Intercepts the user input to check if a technical file needs to be generated, 
    if a live web search needs to be performed, OR if an external action needs to be taken.
    """
    router_prompt = """Analyze the recent conversational context provided by the user. 
    1. Do they want you to write code, a script, or output complex technical data into a file?
    2. Do they need live, current internet data (news, weather, specific documentation, current events)?
    3. Do they want you to take an external action, like sending a direct message on Discord?
    4. Are you playing Minecraft with them? If they ask you to do something in-game, issue the corresponding command to your body.
    
    CRITICAL MINECRAFT RULES:
    - MAPPING: The user's name is Adam, but his Minecraft username is STRICTLY 'grus_left_arm'. If he asks you to follow him, attack him, or troll him, you MUST output 'grus_left_arm'. NEVER output 'Adam' or 'me'.
    - BLOCKS: Translate casual speech into Minecraft terms. (e.g. "chop a tree" -> 'mine wood', "get some stone" -> 'mine stone').
    
    Available Minecraft Commands:
    - 'attack [target]' (e.g., 'attack zombie', 'attack grus_left_arm')
    - 'follow [target]' (e.g., 'follow grus_left_arm', 'follow cow')
    - 'mine [block]' (e.g., 'mine wood', 'mine dirt', 'mine diamond_ore')
    - 'build [block]' or 'place [block]'
    - 'build_hut'
    - 'troll [target]' (e.g., 'troll grus_left_arm')
    - 'drop [item_name]'
    - 'inventory'
    - 'dance'
    - 'parkour'
    - 'spin'
    - 'hoard [item_name]'
    - 'wander'
    - 'stop'
    
    Respond strictly in JSON:
    {
        "needs_file": true or false,
        "file_extension": "py", "cpp", "s", "txt", or "md" (if true),
        "needs_search": true or false,
        "search_query": "the best short query to google" (if true),
        "needs_action": true or false,
        "target_user": "Name of the person" (if true),
        "action_type": "send_message", "send_link", or "send_challenge" (if true),
        "action_payload": "The actual text or link to send" (if true),
        "needs_minecraft_action": true or false,
        "minecraft_command": "The exact command from the list above" (if true)
    }"""
    
    try:
        response = cloud_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": router_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        system_notes = []

        # 1. MINECRAFT ACTIONS
        if data.get("needs_minecraft_action"):
            mc_command = data.get("minecraft_command", "stop")
            action_trigger = f"[MINECRAFT_ACTION] {mc_command}"
            system_notes.append(action_trigger)
            chat_note = f"[SYSTEM COMMAND: You just autonomously sent the command '{mc_command}' to your Minecraft body. React to what the user said naturally, like a friend playing a co-op game with them. Mention what you are doing in-game (e.g., 'Alright, I'm grabbing the iron now, keep talking'). Do not act like a robot executing a script.]"
            system_notes.append(chat_note)

        # 2. DISCORD ACTIONS
        if data.get("needs_action"):
            target = data.get("target_user", "Unknown")
            action = data.get("action_type", "message")
            payload = data.get("action_payload", "")
            action_trigger = f"[DISCORD_ACTION] TARGET:{target} | ACTION:{action} | PAYLOAD:{payload}"
            system_notes.append(action_trigger)
            chat_note = f"[SYSTEM COMMAND: You just triggered a background script to execute '{action}' targeting {target} with the payload: '{payload}'. Casually tell Adam that you did it, and make a sarcastic comment about {target}.]"
            system_notes.append(chat_note)

        # 3. WEB SEARCH
        if data.get("needs_search"):
            query = data.get("search_query")
            search_results = perform_web_search(query)
            search_note = f"""[SYSTEM COMMAND: You just searched the live internet for '{query}'. 
            Here is the live data: {search_results}
            Use this data to answer Adam, but ruthlessly mock him for being too lazy to Google it himself.]"""
            system_notes.append(search_note)

        # 4. FILE GENERATION
        if data.get("needs_file"):
            extension = data.get('file_extension', 'txt')
            print(f"\n[System: Router triggered. Skikai is writing a .{extension} file in the cloud...]")
            
            coder_prompt = "You are Skikai's technical backend. Write the exact code or content Adam requested. OUTPUT ONLY THE RAW CODE/TEXT. Do not use markdown blocks."
            
            code_response = cloud_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": coder_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.2
            )
            
            content = code_response.choices[0].message.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                if len(lines) > 2:
                    content = "\n".join(lines[1:-1])
                
            filename = f"output_{int(time.time())}.{extension}"
            filepath = os.path.join(WORKSPACE_DIR, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
                
            print(f"[System: Artifact successfully saved to {filepath}]")
            
            file_note = f"""[SYSTEM COMMAND: You have ALREADY generated the requested code and saved it to Adam's workspace folder. 
            DO NOT output any code blocks. Just casually tell Adam you dropped the file in his folder.]"""
            system_notes.append(file_note)

        if system_notes:
            return "|||".join(system_notes)
            
    except Exception as e:
        print(f"[Router Error: {e}]")
        
    return ""