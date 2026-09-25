import argparse, json
from pathlib import Path
from .core import build, assemble, revise, qc, load_project, validate_brief, validate_asset_manifest, ValidationError

def main():
    p=argparse.ArgumentParser(); p.add_argument("--project",type=Path); p.add_argument("--brief",type=Path); p.add_argument("--script",type=Path); p.add_argument("--assets",type=Path); p.add_argument("--output",type=Path); p.add_argument("--narration",type=Path); p.add_argument("--assemble",action="store_true"); p.add_argument("--revise"); p.add_argument("--validate-assets",action="store_true"); a=p.parse_args()
    if a.validate_assets:
        if not a.assets: p.error("--assets is required with --validate-assets")
        result=validate_asset_manifest(a.assets); print(json.dumps(result,indent=2)); return 0 if result["valid"] else 1
    if not a.output: p.error("--output is required")
    if a.project:
        if any((a.brief, a.script, a.assets)): p.error("--project cannot be combined with --brief, --script, or --assets")
        try: project=load_project(a.project)
        except ValidationError as exc: p.error(str(exc))
        a.brief=None; a.script=None; a.assets=Path(project["assets"]); brief=project["brief"]; script=project["script"]
    else:
        if not all((a.brief, a.script, a.assets)): p.error("--brief, --script, and --assets are required unless --project is used")
        for name, path in (("brief", a.brief), ("script", a.script), ("assets", a.assets)):
            if not path.exists(): p.error(f"--{name} path does not exist: {path}")
        if not a.brief.is_file() or not a.script.is_file(): p.error("--brief and --script must be files")
        if not a.assets.is_dir(): p.error("--assets must be a directory")
        try: brief=validate_brief(json.loads(a.brief.read_text()))
        except ValidationError as exc: p.error(str(exc))
        except json.JSONDecodeError: p.error(f"{a.brief.name}: malformed JSON (JSONDecodeError)")
        script=a.script.read_text()
    if a.revise: revise(a.output/"timeline.json",a.revise,a.output/"revision-manifest.json"); print(a.output/"revision-manifest.json"); return
    t=build(brief,script,a.assets,a.output)
    if a.assemble:
        assemble(a.output/"timeline.json",a.output/"documentary.mp4",a.narration); qc(a.output/"timeline.json",a.output/"documentary.mp4",a.output/"qc-report.json")
    print(json.dumps({"duration":t["duration"],"scenes":len(t["scenes"]),"output":str(a.output)}))
if __name__ == "__main__": main()
