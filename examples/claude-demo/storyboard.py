"""Render a storyboard MP4 from a NarrativeCut timeline.

Each timeline scene becomes a text card showing the beat, the Claude-planned
visual role and search query, and the asset NarrativeCut selected. Cards stand
in for footage: the demo assets are synthetic placeholders, so this video shows
the plan and the timing, not finished visuals.

    python examples/claude-demo/storyboard.py out/claude-demo/timeline.json site/demo-storyboard.mp4
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

W, H, FPS = 1280, 720, 30
BG, INK, MUTED, ACCENT, LINE = "0x11110f", "0xf4f1e9", "0xaaa89e", "0xd1fa76", "0x35352f"
SANS = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"

def _text(tmp: Path, name: str, value: str, font: str, size: int, color: str, x, y) -> str:
    f = tmp / f"{name}.txt"
    f.write_text(value, encoding="utf-8")
    return f"drawtext=fontfile='{font}':textfile='{f}':fontsize={size}:fontcolor={color}:x={x}:y={y}:line_spacing=10"

def _card(scene: dict, index: int, total_duration: float, tmp: Path, out: Path):
    plan = scene.get("plan") or {}
    asset = Path(scene["asset"]["path"]).stem if scene.get("asset") else "none"
    stamp = f"{scene['id']}  ·  {int(scene['start'] // 60):02d}:{scene['start'] % 60:04.1f}"
    beat = "\n".join(textwrap.wrap(scene["text"], 46))
    rows = [
        ("CLAUDE VISUAL ROLE", plan.get("visual_role", "—")),
        ("CLAUDE SEARCH QUERY", plan.get("search_query", "—")),
        ("SELECTED ASSET", f"{asset}  (synthetic placeholder)"),
    ]
    progress = int(W * (scene["start"] + scene["duration"]) / total_duration)
    filters = [
        f"drawbox=x=0:y={H - 6}:w={progress}:h=6:color={ACCENT}:t=fill",
        _text(tmp, f"{index}-brand", "NARRATIVECUT  ·  STORYBOARD RENDER", MONO, 16, ACCENT, 56, 44),
        _text(tmp, f"{index}-stamp", stamp, MONO, 16, MUTED, f"w-tw-56", 44),
        _text(tmp, f"{index}-beat", beat, SANS, 38, INK, 56, 130),
        f"drawbox=x=56:y=440:w={W - 112}:h=1:color={LINE}:t=fill",
    ]
    for n, (label, value) in enumerate(rows):
        y = 466 + n * 58
        filters.append(_text(tmp, f"{index}-l{n}", label, MONO, 13, MUTED, 56, y))
        filters.append(_text(tmp, f"{index}-v{n}", value, MONO, 19, ACCENT if n < 2 else INK, 56, y + 20))
    filters.append(_text(tmp, f"{index}-note", "Text cards stand in for footage. Timing comes from the deterministic timeline.", MONO, 12, MUTED, 56, H - 34))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:r={FPS}:d={scene['duration']:.3f}",
                    "-vf", ",".join(filters), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28", str(out)], check=True)

def render(timeline_path: Path, output: Path):
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        parts = []
        for i, scene in enumerate(timeline["scenes"]):
            part = tmp / f"part-{i:03d}.mp4"
            _card(scene, i, timeline["duration"], tmp, part)
            parts.append(part)
        listing = tmp / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-movflags", "+faststart", str(output)], check=True)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: storyboard.py TIMELINE_JSON OUTPUT_MP4")
    render(Path(sys.argv[1]), Path(sys.argv[2]))
