"""Render the NarrativeCut explainer video.

Six narrated sections, each a motion card in the site's visual language.
Narration audio comes from AUDIO_DIR/s1.mp3 … s6.mp3 (generated separately with
ElevenLabs); section length follows the audio.

    python scripts/explainer.py AUDIO_DIR site/explainer.mp4
"""
from __future__ import annotations
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

W, H, FPS = 1280, 720, 30
BG, INK, MUTED, ACCENT, LINE, PANEL = "0x11110f", "0xf4f1e9", "0xaaa89e", "0xd1fa76", "0x35352f", "0x191916"
SANS = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
MONO = "/System/Library/Fonts/Menlo.ttc"
PAD = 0.7
# Animation cues are authored on this timeline (seconds per section) and scaled to the narration.
AUTHORED = [9.0, 7.0, 11.5, 11.5, 11.5, 8.5]

CAPTIONS = [
    "Small documentary teams lose days between the script, the footage, the rights notes and the edit.",
    "NarrativeCut connects them. You bring a script and your own licensed assets.",
    "Claude reads the script and plans every scene: what it needs to show, what kind of visual fits, and what to search for.",
    "NarrativeCut turns that plan into a deterministic timeline, with subtitles, a license report, and a render you can review.",
    "In our demo, Claude's plan changed the chosen visual on four of eight beats, replacing generic footage with the document each claim needs.",
    "NarrativeCut is open source, built on Claude, and founded in İzmir in 2026.",
]

class Card:
    def __init__(self, tmp: Path, key: str, scale: float = 1.0):
        self.tmp, self.key, self.filters, self.n, self.scale = tmp, key, [], 0, scale

    def text(self, value, at, x, y, size=28, color=INK, font=SANS, fade=0.45, rise=18):
        self.n += 1
        at, fade = at * self.scale, fade * min(1.0, self.scale)
        f = self.tmp / f"{self.key}-{self.n}.txt"
        f.write_text(value, encoding="utf-8")
        alpha = f"if(lt(t,{at}),0,min(1,(t-{at})/{fade}))"
        ypos = f"{y}+{rise}*(1-min(1,max(0,(t-{at})/{fade})))"
        self.filters.append(f"drawtext=fontfile='{font}':textfile='{f}':fontsize={size}:fontcolor={color}:alpha='{alpha}':x={x}:y='{ypos}':line_spacing=12")

    def box(self, x, y, w, h, color, at, thickness="fill"):
        at *= self.scale
        self.filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t={thickness}:enable='gte(t,{at})'")

    def chrome(self, index, caption, duration):
        self.text("NARRATIVECUT", 0, 56, 40, 15, ACCENT, MONO, rise=0)
        self.text(f"0{index} / 06", 0, "w-tw-56", 40, 15, MUTED, MONO, rise=0)
        self.box(56, H - 118, W - 112, 1, LINE, 0)
        self.text("\n".join(textwrap.wrap(caption, 92)), 0.2, 56, H - 98, 19, MUTED, SANS, rise=0)
        self.filters.append(f"drawbox=x=0:y={H - 5}:w='{W}*t/{duration:.3f}':h=5:color={ACCENT}:t=fill")

def section_1(c: Card):
    c.text("Days lost between the steps.", 0.2, 56, 120, 54)
    for i, (label, x, y) in enumerate([("SCRIPT", 96, 300), ("FOOTAGE", 420, 250), ("RIGHTS NOTES", 720, 330), ("EDIT", 1030, 270)]):
        c.box(x - 16, y - 18, len(label) * 15 + 32, 60, PANEL, 1.2 + i * 1.3)
        c.box(x - 16, y - 18, len(label) * 15 + 32, 60, LINE, 1.2 + i * 1.3, 1)
        c.text(label, 1.2 + i * 1.3, x, y, 22, INK, MONO)
    c.text("?", 6.6, 300, 290, 40, MUTED, MONO)
    c.text("?", 7.0, 615, 300, 40, MUTED, MONO)
    c.text("?", 7.4, 930, 300, 40, MUTED, MONO)

def section_2(c: Card):
    c.text("One connected workflow.", 0.2, 56, 120, 54)
    c.box(560, 250, 160, 160, ACCENT, 1.4, 2)
    c.text("NC", 1.4, 606, 300, 52, ACCENT, MONO)
    c.text("SCRIPT", 2.6, 160, 280, 24, INK, MONO)
    c.text("LICENSED ASSETS", 3.4, 120, 350, 24, INK, MONO)
    c.text("──────▶", 4.0, 400, 312, 26, MUTED, MONO)
    c.text("STRUCTURED", 5.0, 800, 280, 24, ACCENT, MONO)
    c.text("PRODUCTION", 5.4, 800, 350, 24, ACCENT, MONO)

def section_3(c: Card):
    c.text("Claude plans every scene.", 0.2, 56, 120, 54)
    c.box(56, 210, W - 112, 260, PANEL, 1.0)
    c.box(56, 210, 4, 260, ACCENT, 1.0)
    c.text("“Inside were more than 3,000 letters written by factory workers between 1920 and 1950.”", 1.4, 84, 236, 22, INK)
    rows = [("WHAT IT SHOWS", "the letters themselves: a specific count and date range", 4.0),
            ("VISUAL ROLE", "document-evidence", 7.5),
            ("SEARCH QUERY", "handwritten factory worker letters 1920s 1940s archive boxes", 10.0)]
    for i, (label, value, at) in enumerate(rows):
        c.text(label, at, 84, 296 + i * 54, 13, MUTED, MONO)
        c.text(value, at + 0.15, 84, 314 + i * 54, 20, ACCENT if i else INK, MONO)

def section_4(c: Card):
    c.text("From plan to a reviewable cut.", 0.2, 56, 120, 54)
    steps = ["SCRIPT", "CLAUDE PLAN", "SELECTION", "TIMELINE", "RENDER"]
    for i, s in enumerate(steps):
        x, at = 56 + i * 238, 1.0 + i * 1.4
        c.box(x, 240, 210, 70, PANEL, at)
        c.box(x, 240, 210, 70, ACCENT if s == "CLAUDE PLAN" else LINE, at, 1)
        c.text(s, at, x + 18, 264, 18, ACCENT if s == "CLAUDE PLAN" else INK, MONO, rise=10)
        if i: c.text("▶", at - 0.3, x - 22, 262, 18, MUTED, MONO, rise=0)
    for i, out in enumerate(["timeline.json", "subtitles.srt", "asset-license-report.json", "final.mp4 + QC"]):
        c.text(f"→ {out}", 8.2 + i * 0.8, 56 + (i % 2) * 520, 370 + (i // 2) * 52, 20, MUTED, MONO)

def section_5(c: Card):
    c.text("4", 0.4, 56, 100, 150, ACCENT, SANS)
    c.text("of 8 beats changed asset\nwith the Claude plan", 0.8, 170, 140, 30, INK)
    rows = [("scene-002", "factory-workers-history", "letter-boxes"),
            ("scene-003", "factory-workers-history", "letter-boxes"),
            ("scene-005", "letter-boxes", "strike-letter-closeup"),
            ("scene-006", "strike-letter-closeup", "newspaper-front-page")]
    c.text("BEAT          KEYWORDS ONLY              WITH CLAUDE PLAN", 2.5, 56, 300, 14, MUTED, MONO)
    for i, (b, old, new) in enumerate(rows):
        at = 3.2 + i * 1.6
        c.text(f"{b:<14}{old:<27}", at, 56, 336 + i * 40, 18, MUTED, MONO)
        c.text(f"→ {new}", at + 0.4, 56 + 41 * 11, 336 + i * 40, 18, ACCENT, MONO)
    c.text("demo assets are labeled synthetic placeholders", 10.5, 56, 506, 13, MUTED, MONO)

def section_6(c: Card):
    c.text("NarrativeCut", 0.3, 56, 150, 80)
    for i, t in enumerate(["OPEN SOURCE", "BUILT ON CLAUDE", "İZMIR · 2026"]):
        c.text(t, 1.5 + i * 1.6, 56 + i * 300, 290, 22, ACCENT, MONO)
    c.text("narrativecut.com.tr", 6.5, 56, 380, 34, INK, SANS)
    c.text("github.com/ilkercemtanriverdi/narrativecut", 7.5, 56, 434, 18, MUTED, MONO)

SECTIONS = [section_1, section_2, section_3, section_4, section_5, section_6]

def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout) + PAD

def render(audio_dir: Path, output: Path):
    with tempfile.TemporaryDirectory() as d:
        tmp, parts = Path(d), []
        for i, build in enumerate(SECTIONS, 1):
            audio = audio_dir / f"s{i}.mp3"
            dur = duration(audio)
            card = Card(tmp, f"s{i}", min(1.0, (dur - 1.0) / AUTHORED[i - 1]))
            build(card)
            card.chrome(i, CAPTIONS[i - 1], dur)
            part = tmp / f"part-{i}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:r={FPS}:d={dur:.3f}",
                            "-i", str(audio), "-filter_complex", f"[0:v]{','.join(card.filters)}[v];[1:a]apad,atrim=0:{dur:.3f},aresample=44100[a]",
                            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
                            "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-t", f"{dur:.3f}", str(part)], check=True)
            parts.append(part)
        listing = tmp / "parts.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-movflags", "+faststart", str(output)], check=True)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: explainer.py AUDIO_DIR OUTPUT_MP4")
    render(Path(sys.argv[1]), Path(sys.argv[2]))
