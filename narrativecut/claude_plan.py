"""Claude-powered editorial scene planning.

Claude groups deterministic script beats into editorial scenes and proposes a
purpose, claim type, visual role and asset search query for each one. Timing
stays deterministic: scene start and duration are derived from the beats that
`parse_script` produced, never from model output.
"""
from __future__ import annotations
import json
from pathlib import Path
from .core import VISUAL_ROLES, ValidationError, parse_script

DEFAULT_MODEL = "claude-opus-5-5"
PLAN_SCHEMA_VERSION = "1.0"
PURPOSES = ["hook", "context", "evidence", "explanation", "transition", "conclusion"]
CLAIM_TYPES = ["context", "entity", "event", "number"]

class PlanningError(ValueError):
    """Claude planning could not produce a valid scene plan."""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "logline": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "beat_ids": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "purpose": {"type": "string", "enum": PURPOSES},
                    "claim_type": {"type": "string", "enum": CLAIM_TYPES},
                    "visual_role": {"type": "string", "enum": sorted(VISUAL_ROLES)},
                    "search_query": {"type": "string"},
                    "on_screen_text": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["beat_ids", "summary", "purpose", "claim_type", "visual_role", "search_query", "on_screen_text", "rationale"],
                "additionalProperties": False,
            },
        },
        "editorial_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["logline", "scenes", "editorial_risks"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the editorial planner for NarrativeCut, a documentary and explainer video production tool.

You receive a brief and a script that has already been split into numbered beats. Group consecutive beats into editorial scenes and plan the visuals for each scene.

Rules:
- Every beat id must appear in exactly one scene, and scenes must keep the script order. Do not invent, merge or rename beat ids.
- A scene usually holds one to three beats. Start a new scene when the topic, claim or required visual changes.
- claim_type is "entity", "event" or "number" when the scene makes a specific factual claim that needs matching evidence on screen; otherwise "context".
- visual_role is the kind of visual the scene needs. Prefer evidence (primary-footage, document-evidence, data-chart, specific-entity) for specific claims.
- search_query is a short, concrete query for finding a rights-cleared local or archival asset. Name entities, places, dates or objects; avoid abstract words.
- on_screen_text is a short lower-third or caption, or an empty string when none is needed.
- rationale explains the editorial choice in one sentence.
- editorial_risks lists claims that need fact-checking or sourcing, pacing problems, or visuals that will be hard to source. Use an empty list when there are none.
- Work only from the script. Do not add facts that are not in it."""

def _prompt(brief, beats):
    lines = [f"Title: {brief.get('title', 'Untitled')}"]
    for key in sorted(k for k in brief if k != "title"):
        lines.append(f"{key}: {json.dumps(brief[key], ensure_ascii=False)}")
    lines.append("")
    lines.append("Script beats:")
    lines.extend(f"[{b.id}] {b.text}" for b in beats)
    return "\n".join(lines)

def _client():
    try: import anthropic
    except ImportError: raise PlanningError("Claude planning requires the optional dependency: pip install 'narrativecut[claude]'") from None
    return anthropic.Anthropic()

def request_plan(client, brief, beats, model=DEFAULT_MODEL):
    """Call Claude with a JSON-schema constrained output and return the parsed plan and usage."""
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _prompt(brief, beats)}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": PLAN_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise PlanningError(f"Claude declined to plan this script ({getattr(details, 'category', None) or 'no category'})")
    if response.stop_reason == "max_tokens":
        raise PlanningError("Claude response was truncated at max_tokens; shorten the script or split it")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None: raise PlanningError("Claude response contained no plan")
    try: data = json.loads(text)
    except json.JSONDecodeError: raise PlanningError("Claude response was not valid JSON") from None
    usage = getattr(response, "usage", None)
    return data, {"model": getattr(response, "model", model),
                  "input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None)}

def validate_plan(data, beats):
    """Check that the plan covers every beat exactly once, in script order."""
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise PlanningError("plan.scenes: expected a non-empty list")
    expected = [b.id for b in beats]
    seen = []
    for i, scene in enumerate(data["scenes"], 1):
        ids = scene.get("beat_ids") if isinstance(scene, dict) else None
        if not isinstance(ids, list) or not ids: raise PlanningError(f"plan.scenes[{i}]: expected a non-empty beat_ids list")
        for beat_id in ids:
            if beat_id not in expected: raise PlanningError(f"plan.scenes[{i}]: unknown beat id {beat_id!r}")
            if beat_id in seen: raise PlanningError(f"plan.scenes[{i}]: beat id {beat_id!r} is used more than once")
            seen.append(beat_id)
        if scene.get("visual_role") not in VISUAL_ROLES: raise PlanningError(f"plan.scenes[{i}]: invalid visual_role {scene.get('visual_role')!r}")
    if seen != expected:
        missing = [b for b in expected if b not in seen]
        if missing: raise PlanningError(f"plan: beats not assigned to any scene: {', '.join(missing)}")
        raise PlanningError("plan: scenes do not follow script order")
    return data

def plan_scenes(brief, script, output: Path, client=None, model=DEFAULT_MODEL):
    """Plan editorial scenes with Claude and write `scene-plan.json` to `output`."""
    beats = parse_script(script)
    if not beats: raise ValidationError("script: no text to plan")
    data, usage = request_plan(client or _client(), brief, beats, model)
    validate_plan(data, beats)
    by_id = {b.id: b for b in beats}
    scenes = []
    for i, s in enumerate(data["scenes"], 1):
        members = [by_id[x] for x in s["beat_ids"]]
        start = members[0].start; end = members[-1].start + members[-1].duration
        scenes.append({"id": f"plan-{i:03d}", "beat_ids": s["beat_ids"], "start": round(start, 3), "duration": round(end - start, 3),
                       "text": " ".join(b.text for b in members), **{k: s[k] for k in ("summary", "purpose", "claim_type", "visual_role", "search_query", "on_screen_text", "rationale")}})
    plan = {"schema_version": PLAN_SCHEMA_VERSION, "title": brief.get("title", "Untitled"), "logline": data.get("logline", ""),
            "planner": {"provider": "anthropic", **usage}, "beat_count": len(beats), "scenes": scenes,
            "editorial_risks": data.get("editorial_risks", [])}
    output.mkdir(parents=True, exist_ok=True)
    (output / "scene-plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return plan
