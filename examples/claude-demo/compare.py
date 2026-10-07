"""Compare asset selection with and without the saved Claude scene plan.

Run from the repository root: python examples/claude-demo/compare.py
No API call is made; the plan is the unedited live output in output/scene-plan.json.
"""
import json, sys, tempfile
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parents[1]))
from narrativecut.claude_plan import load_scene_plan
from narrativecut.core import build

brief = json.loads((root / "brief.json").read_text()); script = (root / "script.txt").read_text()
plan = load_scene_plan(root / "output" / "scene-plan.json", script)
with tempfile.TemporaryDirectory() as tmp:
    baseline = build(brief, script, root / "assets", Path(tmp) / "baseline")
    guided = build(brief, script, root / "assets", Path(tmp) / "guided", plan)
name = lambda s: Path(s["asset"]["path"]).stem if s["asset"] else "-"
rows = ["| Beat | Claude visual role | Without plan | With plan |", "|---|---|---|---|"]
for b, g in zip(baseline["scenes"], guided["scenes"]):
    mark = " (changed)" if name(b) != name(g) else ""
    rows.append(f"| {g['id']} | {g['plan']['visual_role']} | {name(b)} | {name(g)}{mark} |")
changed = sum(name(b) != name(g) for b, g in zip(baseline["scenes"], guided["scenes"]))
print("\n".join(rows)); print(f"\n{changed} of {len(rows) - 2} beats changed asset.")
