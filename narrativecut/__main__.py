import argparse, json
from pathlib import Path
from .claude_plan import plan_scenes, DEFAULT_MODEL
from .core import build, assemble, revise, qc, load_project, validate_brief, validate_asset_manifest, ValidationError

def _main():
    p=argparse.ArgumentParser(); p.add_argument("--project",type=Path); p.add_argument("--brief",type=Path); p.add_argument("--script",type=Path); p.add_argument("--assets",type=Path); p.add_argument("--output",type=Path); p.add_argument("--narration",type=Path); p.add_argument("--assemble",action="store_true"); p.add_argument("--revise"); p.add_argument("--validate-assets",action="store_true"); p.add_argument("--plan-with-claude",action="store_true",help="plan editorial scenes with Claude and write scene-plan.json"); p.add_argument("--model",default=DEFAULT_MODEL); a=p.parse_args()
    if a.validate_assets:
        if not a.assets: p.error("--assets is required with --validate-assets")
        result=validate_asset_manifest(a.assets); print(json.dumps(result,indent=2)); return 0 if result["valid"] else 1
    if not a.output: p.error("--output is required")
    if a.plan_with_claude:
        if a.project:
            try: project=load_project(a.project)
            except ValidationError as exc: p.error(str(exc))
            brief=project["brief"]; script=project["script"]
        else:
            if not a.script or not a.script.is_file(): p.error("--script file is required with --plan-with-claude")
            try: brief=validate_brief(json.loads(a.brief.read_text())) if a.brief else {}
            except ValidationError as exc: p.error(str(exc))
            except json.JSONDecodeError: p.error(f"{a.brief.name}: malformed JSON (JSONDecodeError)")
            script=a.script.read_text()
        plan=plan_scenes(brief,script,a.output,model=a.model)
        print(json.dumps({"scenes":len(plan["scenes"]),"beats":plan["beat_count"],"model":plan["planner"]["model"],"output":str(a.output/"scene-plan.json")}))
        return 0
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
    if a.revise: revise(a.output/"timeline.json",a.revise,a.output/"revision-manifest.json"); print(a.output/"revision-manifest.json"); return 0
    t=build(brief,script,a.assets,a.output)
    if a.assemble:
        assemble(a.output/"timeline.json",a.output/"documentary.mp4",a.narration)
        report=qc(a.output/"timeline.json",a.output/"documentary.mp4",a.output/"qc-report.json")
        if not report["pass"]:
            import sys
            print("QC failed: " + "; ".join(report.get("reasons", [])), file=sys.stderr)
            return 1
    print(json.dumps({"duration":t["duration"],"scenes":len(t["scenes"]),"output":str(a.output)}))
    return 0

def main():
    try:
        return _main()
    except (ValueError, OSError) as exc:
        import sys
        print(f"error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
