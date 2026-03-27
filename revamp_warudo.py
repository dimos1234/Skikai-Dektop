"""
Warudo Blueprint Revamp Script.
Applies Neuro-sama-style animation overhaul:
  - Snappy one-shot transitions (2.0 -> 0.35)
  - Slightly faster animation speed (1.0 -> 1.15)
  - Stronger pendulum sway for constant "alive" motion
  - More responsive lip sync
  - New trigger branches for shrug, tilt_head, glance_away, sigh, pout, smug, surprise
"""
import json
import os
import uuid
import sys

DEFAULT_PATH = 'formatted_blueprint.json'
FALLBACK_PATH = 'skikai_model/skikai_blueprint.json'

CHARACTER_REF = '{"id":"29399e49-1c26-41bb-b40f-294dc0590f68","name":"Character 1"}'

STRING_EQUAL_TYPE   = "6d1b6dd6-5534-4427-9d58-2952082e1244"
IF_BRANCH_TYPE      = "1b58a074-3c70-412e-ace4-0f12c3f7f16b"
PLAY_ANIM_TYPE      = "3c8f47ba-5430-4061-8506-19812b4d2ec0"

NEW_TRIGGERS = {
    "shrug":      "character-animation://resources/Animations/AGIA/02_Layers/AGIA_Layer_shrug_01",
    "tilt_head":  "character-animation://resources/Animations/AGIA/02_Layers/AGIA_Layer_head_tilt_01",
    "glance_away":"character-animation://resources/Animations/AGIA/02_Layers/AGIA_Layer_look_away_01",
    "sigh":       "character-animation://resources/Animations/AGIA/01_Idles/AGIA_Idle_sigh_01",
    "pout":       "character-animation://resources/Animations/AGIA/02_Layers/AGIA_Layer_pout_01",
    "smug":       "character-animation://resources/Animations/AGIA/01_Idles/AGIA_Idle_smug_01",
    "surprise":   "character-animation://resources/Animations/AGIA/03_Others/AGIA_Other_surprised_01",
}


def _uid():
    return str(uuid.uuid4())


def _find_websocket_node(nodes):
    for nid, n in nodes.items():
        if n.get("name") == "ON_WEBSOCKET_RAW_MESSAGE":
            return nid
    return None


def _find_last_if_branch(flow_conns, nodes):
    """Walk the IfFalse chain starting from the WebSocket flow to find the terminal IF_BRANCH."""
    if_branches = {nid for nid, n in nodes.items() if n.get("name") == "IF_BRANCH"}
    has_false_out = set()
    for fc in flow_conns:
        if fc["outputPort"] == "IfFalse" and fc["outputNode"] in if_branches:
            has_false_out.add(fc["outputNode"])
    terminal = if_branches - has_false_out
    if terminal:
        return terminal.pop()
    return None


def _existing_trigger_words(nodes, data_conns):
    """Collect all trigger words already present as STRING_EQUAL B values."""
    words = set()
    for nid, n in nodes.items():
        if n.get("name") == "STRING_EQUAL":
            b_val = n["dataInputs"].get("B", {}).get("value", "")
            if isinstance(b_val, str):
                words.add(b_val.strip('"'))
    return words


def _make_string_equal(trigger_word, x, y):
    nid = _uid()
    return nid, {
        "id": nid,
        "dataInputs": {
            "A": {"type": "string", "value": f'"{trigger_word}"'},
            "B": {"type": "string", "value": f'"{trigger_word}"'},
            "IgnoreCase": {"type": "bool", "value": "true"},
            "TrimWhitespaces": {"type": "bool", "value": "true"}
        },
        "typeId": STRING_EQUAL_TYPE,
        "name": "STRING_EQUAL",
        "x": x, "y": y
    }


def _make_if_branch(x, y):
    nid = _uid()
    return nid, {
        "id": nid,
        "dataInputs": {"Condition": {"type": "bool", "value": "false"}},
        "typeId": IF_BRANCH_TYPE,
        "name": "IF_BRANCH",
        "x": x, "y": y
    }


def _make_play_animation(clip_path, x, y):
    nid = _uid()
    return nid, {
        "id": nid,
        "dataInputs": {
            "Character": {"type": "Warudo.Plugins.Core.Assets.Character.CharacterAsset", "value": CHARACTER_REF},
            "Animation": {"type": "string", "value": f'"{clip_path}"'},
            "TransitionTime": {"type": "float", "value": "0.35"},
            "Weight": {"type": "float", "value": "1.0"},
            "Speed": {"type": "float", "value": "1.15"},
            "Masked": {"type": "bool", "value": "false"},
            "MaskedBodyParts": {"type": "Warudo.Plugins.Core.Assets.Character.CharacterAsset+AnimationMaskedBodyPart[]", "value": "[]"},
            "Additive": {"type": "bool", "value": "false"}
        },
        "typeId": PLAY_ANIM_TYPE,
        "name": "PLAY_CHARACTER_ONE_SHOT_ANIMATION",
        "x": x, "y": y
    }


def revamp_blueprint(path=None):
    if path is None:
        path = DEFAULT_PATH if os.path.exists(DEFAULT_PATH) else FALLBACK_PATH

    if not os.path.exists(path):
        print(f"Blueprint not found: {path}")
        return

    with open(path, "rb") as fb:
        raw = fb.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode("utf-16")
    elif raw[:3] == b'\xef\xbb\xbf':
        text = raw.decode("utf-8-sig")
    else:
        text = raw.decode("utf-8")
    data = json.loads(text)

    nodes = data.get("nodes", {})
    data_conns = data.get("dataConnections", [])
    flow_conns = data.get("flowConnections", [])

    # ── 1. Snappy one-shot transitions ──────────────────────────────────
    anim_count = 0
    for nid, node in nodes.items():
        if node.get("name") == "PLAY_CHARACTER_ONE_SHOT_ANIMATION":
            di = node["dataInputs"]
            if "TransitionTime" in di:
                di["TransitionTime"]["value"] = "0.35"
            if "Speed" in di:
                di["Speed"]["value"] = "1.15"
            anim_count += 1
    print(f"  [1/6] Updated {anim_count} one-shot animations: TransitionTime=0.35, Speed=1.15")

    # ── 2. Lip sync responsiveness ──────────────────────────────────────
    for nid, node in nodes.items():
        if node.get("name") == "GENERATE_LIP_SYNC_BLENDSHAPES":
            di = node["dataInputs"]
            if "SmoothTime" in di:
                di["SmoothTime"]["value"] = "0.05"
            if "VolumeThreshold" in di:
                di["VolumeThreshold"]["value"] = "15.0"
    print("  [2/6] Lip sync: SmoothTime=0.05, VolumeThreshold=15.0")

    # ── 3. Pendulum physics – stronger constant sway ────────────────────
    for nid, node in nodes.items():
        if node.get("name") == "FLOAT_PENDULUM_PHYSICS":
            di = node["dataInputs"]
            if "Intensity" in di:
                di["Intensity"]["value"] = "3.5"
            if "SourceValueMax" in di:
                di["SourceValueMax"]["value"] = "5.0"
            if "Arms" in di:
                raw = di["Arms"]["value"]
                arms = json.loads(raw) if isinstance(raw, str) else raw
                for arm in arms:
                    adi = arm.get("dataInputs", {})
                    if "Length" in adi:
                        adi["Length"]["value"] = "25.0"
                    if "Mass" in adi:
                        adi["Mass"]["value"] = "1.5"
                    if "Spring" in adi:
                        adi["Spring"]["value"] = "1.8"
                    if "Gravity" in adi:
                        adi["Gravity"]["value"] = "0.25"
                    if "Damping" in adi:
                        adi["Damping"]["value"] = "0.05"
                di["Arms"]["value"] = json.dumps(arms) if isinstance(raw, str) else arms
    print("  [3/6] Pendulum: Intensity=3.5, arm physics strengthened")

    # ── 4. Smoother sway response ───────────────────────────────────────
    for nid, node in nodes.items():
        if node.get("name") == "SMOOTH_FLOAT":
            di = node["dataInputs"]
            if "SmoothTime" in di:
                di["SmoothTime"]["value"] = "0.45"
    print("  [4/6] SMOOTH_FLOAT: SmoothTime=0.45")

    # ── 5. Increase sway multipliers for more visible body motion ───────
    for nid, node in nodes.items():
        if node.get("name") == "MULTIPLY_FLOAT":
            di = node["dataInputs"]
            b_val = di.get("B", {}).get("value", "0")
            try:
                b = float(b_val)
            except (ValueError, TypeError):
                continue
            if abs(b - 10.0) < 0.01:
                di["B"]["value"] = "15.0"
            elif abs(b - 15.0) < 0.01:
                di["B"]["value"] = "20.0"

    # Increase spine/head offset scales in VECTOR3 nodes
    for nid, node in nodes.items():
        if node.get("name") == "VECTOR3":
            di = node["dataInputs"]
            try:
                y_val = float(di.get("Y", {}).get("value", "0"))
            except (ValueError, TypeError):
                continue
            if abs(y_val - 3.333) < 0.1:
                di["X"]["value"] = "1.5"
                di["Y"]["value"] = "5.0"
                di["Z"]["value"] = "1.5"
            elif abs(y_val + 3.333) < 0.1:
                di["X"]["value"] = "-1.5"
                di["Y"]["value"] = "-5.0"
                di["Z"]["value"] = "-1.5"
    print("  [5/6] Sway multipliers and bone offsets increased")

    # ── 6. Add new trigger branches ─────────────────────────────────────
    ws_node = _find_websocket_node(nodes)
    last_if = _find_last_if_branch(flow_conns, nodes)
    existing = _existing_trigger_words(nodes, data_conns)

    added = 0
    base_y = 3000.0
    for trigger, clip in NEW_TRIGGERS.items():
        if trigger in existing:
            continue

        se_id, se_node = _make_string_equal(trigger, 750.0, base_y)
        ib_id, ib_node = _make_if_branch(1100.0, base_y + 12.0)
        pa_id, pa_node = _make_play_animation(clip, 1600.0, base_y + 10.0)

        nodes[se_id] = se_node
        nodes[ib_id] = ib_node
        nodes[pa_id] = pa_node

        if ws_node:
            data_conns.append({"outputNode": ws_node, "inputNode": se_id, "outputPort": "RawMessage", "inputPort": "A"})
        data_conns.append({"outputNode": se_id, "inputNode": ib_id, "outputPort": "Result", "inputPort": "Condition"})

        flow_conns.append({"outputNode": ib_id, "inputNode": pa_id, "outputPort": "IfTrue", "inputPort": "Enter"})

        if last_if:
            flow_conns.append({"outputNode": last_if, "inputNode": ib_id, "outputPort": "IfFalse", "inputPort": "Enter"})

        last_if = ib_id
        base_y += 450.0
        added += 1

    print(f"  [6/6] Added {added} new trigger branches: {', '.join(t for t in NEW_TRIGGERS if t not in existing)}")

    # ── Write back ──────────────────────────────────────────────────────
    data["nodes"] = nodes
    data["dataConnections"] = data_conns
    data["flowConnections"] = flow_conns

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\nWarudo blueprint revamped: {path}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target == "--full-overhaul":
        target = None
    revamp_blueprint(target)
