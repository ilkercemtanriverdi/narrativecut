import argparse, json
from pathlib import Path
from .core import build, assemble, revise, qc

def main():
    p=argparse.ArgumentParser(); p.add_argument("--brief",type=Path,required=True); p.add_argument("--script",type=Path,required=True); p.add_argument("--assets",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--narration",type=Path); p.add_argument("--assemble",action="store_true"); p.add_argument("--revise"); a=p.parse_args()
    for name, path in (("brief", a.brief), ("script", a.script), ("assets", a.assets)):
        if not path.exists(): p.error(f"--{name} path does not exist: {path}")
    if not a.brief.is_file() or not a.script.is_file(): p.error("--brief and --script must be files")
    if not a.assets.is_dir(): p.error("--assets must be a directory")
    if a.revise: revise(a.output/"timeline.json",a.revise,a.output/"revision-manifest.json"); print(a.output/"revision-manifest.json"); return
    t=build(json.loads(a.brief.read_text()),a.script.read_text(),a.assets,a.output)
    if a.assemble:
        assemble(a.output/"timeline.json",a.output/"documentary.mp4",a.narration); qc(a.output/"timeline.json",a.output/"documentary.mp4",a.output/"qc-report.json")
    print(json.dumps({"duration":t["duration"],"scenes":len(t["scenes"]),"output":str(a.output)}))
if __name__ == "__main__": main()
