from __future__ import annotations
import hashlib, json, math, re, subprocess, tempfile
from dataclasses import dataclass, asdict
from fractions import Fraction
from pathlib import Path

TYPE_WEIGHT = {"footage": 1.0, "public_domain": .95, "stock": .9, "screenshot": .85, "document": .82, "chart": .8, "ai": .35, "unknown": .1}
VISUAL_ROLES = {"primary-footage","specific-entity","document-evidence","data-chart","screenshot","context-broll","explanatory-graphic","title-card"}
DIRECT = {"direct", "supporting"}
SCHEMA_VERSION = "1.0"

class ValidationError(ValueError):
    """A deterministic project schema validation failure."""

class MediaError(ValueError):
    """A deterministic local media or FFmpeg failure."""

def _media_run(command, label):
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise MediaError(f"{label}: required executable '{command[0]}' was not found; install FFmpeg") from None
    except OSError:
        raise MediaError(f"{label}: cannot start '{command[0]}'; check its installation and permissions") from None
    except subprocess.CalledProcessError as exc:
        raise MediaError(f"{label}: {command[0]} failed (exit {exc.returncode})") from None

def _object(value, label):
    if not isinstance(value, dict): raise ValidationError(f"{label}: expected an object")
    return value

def validate_brief(data):
    data = _object(data, "brief")
    if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(f"brief.schema_version: unsupported version {data['schema_version']!r}; expected '{SCHEMA_VERSION}'")
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        raise ValidationError("brief.title: expected a non-empty string")
    return data

def validate_timeline(data):
    data = _object(data, "project")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"project.schema_version: unsupported or missing version {data.get('schema_version')!r}; expected '{SCHEMA_VERSION}'")
    if not isinstance(data.get("brief"), dict): raise ValidationError("project.brief: required object")
    validate_brief(data["brief"])
    if not isinstance(data.get("script"), str) or not data["script"].strip(): raise ValidationError("project.script: required non-empty string")
    if not isinstance(data.get("assets"), str) or not data["assets"].strip(): raise ValidationError("project.assets: required non-empty path string")
    return data

def load_project(path: Path):
    try: raw = path.read_text()
    except OSError as exc: raise ValidationError(f"cannot read project file: {exc.strerror or exc}") from None
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            try: import yaml
            except ImportError: raise ValidationError("YAML input requires the optional dependency: pip install 'narrativecut[yaml]'") from None
            data = yaml.safe_load(raw)
        else: data = json.loads(raw)
    except ValidationError: raise
    except json.JSONDecodeError as exc:
        # Parser diagnostics can vary between versions; keep CLI errors stable.
        raise ValidationError(f"{path.name}: malformed {('YAML' if path.suffix.lower() in {'.yaml', '.yml'} else 'JSON')} ({type(exc).__name__})") from None
    except Exception as exc:
        if path.suffix.lower() not in {".yaml", ".yml"}: raise
        raise ValidationError(f"{path.name}: malformed YAML ({type(exc).__name__})") from None
    return validate_timeline(data)

def validate_asset_manifest(root: Path):
    """Validate local asset files and their adjacent <filename>.json metadata."""
    if not root.exists() or not root.is_dir():
        raise ValidationError(f"assets: directory does not exist: {root}")
    errors=[]; ids={}; hashes={}; media=[]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.endswith(".json") or path.suffix.lower() in {".txt", ".md"}: continue
        media.append(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes: errors.append(f"{path}: duplicate file content also found at {hashes[digest]}")
        else: hashes[digest]=path
        sidecar=path.with_suffix(path.suffix+".json")
        if not sidecar.is_file():
            errors.append(f"{path}: missing metadata sidecar {sidecar.name}"); continue
        try: meta=json.loads(sidecar.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{sidecar}: malformed JSON ({type(exc).__name__})"); continue
        if not isinstance(meta, dict):
            errors.append(f"{sidecar}: expected an object"); continue
        for field in ("source", "rights", "subject"):
            if not isinstance(meta.get(field), str) or not meta[field].strip():
                errors.append(f"{sidecar}: required non-empty string '{field}'")
        reference=meta.get("path")
        if reference is not None and (not isinstance(reference, str) or not reference.strip()):
            errors.append(f"{sidecar}: 'path' must be a non-empty relative path")
        elif reference is not None:
            target=(sidecar.parent/reference).resolve()
            if Path(reference).is_absolute() or target != path.resolve():
                errors.append(f"{sidecar}: path reference must resolve to asset {path.name}")
        identity=meta.get("id")
        if identity is not None:
            if not isinstance(identity, str) or not identity.strip(): errors.append(f"{sidecar}: 'id' must be a non-empty string")
            elif identity in ids:
                kind="duplicate" if ids[identity][1] == meta else "conflicting"
                errors.append(f"{sidecar}: {kind} id '{identity}' also used by {ids[identity][0]}")
            else: ids[identity]=(sidecar,meta)
    if not media: errors.append(f"{root}: no asset files found")
    return {"valid":not errors,"asset_count":len(media),"errors":errors}

@dataclass
class Beat:
    id: str; text: str; start: float; duration: float; query: str

def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_script(text: str, target_wpm=145):
    chunks = [re.sub(r"\s+", " ", x.strip()) for x in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text) if x.strip()]
    out=[]; cursor=0.0
    for i, chunk in enumerate(chunks, 1):
        duration=max(3.0, len(chunk.split()) / target_wpm * 60)
        out.append(Beat(f"scene-{i:03d}", chunk, round(cursor,3), round(duration,3), " ".join(chunk.split()[:8])))
        cursor += duration
    return out

def catalog_assets(root: Path):
    items=[]
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() in {".json", ".txt"}: continue
        meta_path=p.with_suffix(p.suffix+".json")
        if not meta_path.is_file(): continue
        meta=json.loads(meta_path.read_text())
        if not all(meta.get(k) for k in ("source","rights","subject")): continue
        kind=meta.get("kind","unknown"); terms=(p.stem+" "+meta["subject"]).lower()
        items.append({"path":str(p.resolve()),"sha256":sha(p),"kind":kind,"terms":terms,"source":meta["source"],"rights":meta["rights"],"subject":meta["subject"],"role":meta.get("role","explanatory-graphic"),"match_level":meta.get("match_level","abstract"),"specificity":meta.get("specificity","none"),"chapter":meta.get("chapter","general"),"claim_type":meta.get("claim_type","context"),"treatment":meta.get("treatment","static")})
    return items

def select(beat: Beat, assets, used):
    words=set(re.findall(r"[a-z0-9]+", (beat.query+" "+beat.text).lower()))
    ranked=[]
    for a in assets:
        overlap=len(words & set(re.findall(r"[a-z0-9]+", a["terms"])))
        repeat=.15 if a["sha256"] in used else 0
        ranked.append((overlap + TYPE_WEIGHT.get(a["kind"],.1) - repeat, a))
    return max(ranked, key=lambda x:x[0])[1] if ranked else None

def srt_time(s):
    ms=round(s*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); sec,ms=divmod(ms,1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

def write_srt(beats, path):
    path.write_text("\n\n".join(f"{i}\n{srt_time(b.start)} --> {srt_time(b.start+b.duration)}\n{b.text}" for i,b in enumerate(beats,1))+"\n")

def editorial_gate(timeline):
    scenes=timeline["scenes"]; dur=timeline["duration"]
    reasons=[]; assets=[s.get("asset") for s in scenes if s.get("asset")]
    if not assets: reasons.append("no admitted visual assets")
    if len({a["role"] for a in assets}) < 5: reasons.append("fewer than 5 visual classes")
    if len({a["sha256"] for a in assets}) < 5: reasons.append("tiny asset pool")
    totals={}
    prev=None; untreated_static=0; treatments=[]; compositions=[]; static_equiv=0; prev_class=None
    for s in scenes:
        a=s.get("asset")
        if not a: reasons.append(f"{s['id']}: unmatched scene"); continue
        totals[a["sha256"]]=totals.get(a["sha256"],0)+s["duration"]
        if prev==a["sha256"]: reasons.append(f"{s['id']}: adjacent asset reuse")
        prev=a["sha256"]
        treatments.append(s.get("treatment", "static")); compositions.append(s.get("composition", "fit"))
        if prev_class == (a.get("role"), s.get("treatment", "static")): static_equiv += 1
        prev_class=(a.get("role"), s.get("treatment", "static"))
        if a["role"] in {"explanatory-graphic","title-card"} and a["treatment"]=="static": untreated_static+=s["duration"]
        if a["role"] not in VISUAL_ROLES: reasons.append(f"{s['id']}: invalid visual role")
        if a["match_level"]=="mismatch": reasons.append(f"{s['id']}: mismatch")
        if a["match_level"]=="abstract" and a["claim_type"] in {"entity","event","number"}: reasons.append(f"{s['id']}: abstract-only critical claim")
    if totals and max(totals.values())/dur > .20: reasons.append("one asset exceeds 20% screen-time")
    first60=[s for s in scenes if s["start"]<60 and s.get("asset") and s["asset"]["specificity"] in {"topic","entity","event"}]
    if len(first60)<2: reasons.append("fewer than 2 topic-specific assets in first 60s")
    if dur and untreated_static/dur > .25: reasons.append("untreated static ratio exceeds 25%")
    direct=sum(s["duration"] for s in scenes if s.get("asset") and s["asset"]["match_level"] in DIRECT)/dur if dur else 0
    static=sum(s["duration"] for s in scenes if s.get("asset") and s["asset"]["role"] in {"explanatory-graphic","title-card"})/dur if dur else 0
    return {"pass":not reasons,"reasons":reasons,"metrics":{"asset_count":len({a['sha256'] for a in assets}),"visual_classes":len({a['role'] for a in assets}),"direct_or_supporting_coverage":round(direct,3),"static_treated_or_graphic_ratio":round(static,3),"untreated_static_ratio":round(untreated_static/dur,3) if dur else 1,"critical_mismatch_count":sum(1 for s in scenes if (s.get('asset') or {}).get('match_level')=='mismatch'),"first_60s_topic_specific_assets":len(first60),"treatment_diversity":len(set(treatments)),"composition_diversity":len(set(compositions)),"consecutive_static_equivalent_shots":static_equiv}}

def choose_treatment(asset, index, start):
    role=asset.get("role", "context-broll")
    if role in {"primary-footage", "context-broll"}: choices=[("trim_reframe", "wide"), ("cut_reframe", "close"), ("trim_reframe", "left")]
    elif role == "document-evidence": choices=[("document_zoom", "evidence"), ("pan_reveal", "wide"), ("callout", "evidence")]
    elif role in {"data-chart", "explanatory-graphic"}: choices=[("push_in", "wide"), ("pan_reveal", "left"), ("callout", "evidence")]
    elif role == "screenshot": choices=[("crop_reframe", "close"), ("push_in", "evidence"), ("pan_reveal", "wide")]
    else: choices=[("chapter_card", "wide"), ("push_in", "close"), ("crop_reframe", "left")]
    return choices[(index + (1 if start < 60 else 0)) % len(choices)]

def build(brief, script, assets_dir, output):
    output.mkdir(parents=True,exist_ok=True); beats=parse_script(script); assets=catalog_assets(assets_dir); used=set(); scenes=[]
    for b in beats:
        a=select(b,assets,used)
        if a: used.add(a["sha256"])
        treatment, composition = choose_treatment(a, len(scenes), b.start) if a else ("static", "fit")
        scenes.append({"id":b.id,"text":b.text,"start":b.start,"duration":b.duration,"query":b.query,"asset":a,"treatment":treatment,"composition":composition})
    timeline={"format":"youtube-documentary-v1","width":1920,"height":1080,"fps":30,"title":brief.get("title","Untitled"),"scenes":scenes,"duration":round(sum(b.duration for b in beats),3)}
    timeline["editorial_gate"]=editorial_gate(timeline)
    (output/"timeline.json").write_text(json.dumps(timeline,indent=2)+"\n"); write_srt(beats,output/"subtitles.srt")
    report={"assets": [s["asset"] for s in scenes if s["asset"]],"unmatched_scenes":[s["id"] for s in scenes if not s["asset"]],"policy":"retrieval-first; AI optional and penalized","rights_basis":"sidecar metadata supplied by user"}
    (output/"asset-license-report.json").write_text(json.dumps(report,indent=2)+"\n")
    return timeline

def assemble(timeline_path: Path, out: Path, narration: Path | None = None):
    t=json.loads(timeline_path.read_text()); dur=t["duration"]
    if not t.get("editorial_gate",{}).get("pass"):
        raise ValueError("editorial gate failed: " + "; ".join(t.get("editorial_gate",{}).get("reasons",[])))
    if narration is None or not narration.is_file():
        raise ValueError("real narration audio is required; refusing silent fallback")
    # Detect unavailable tools before allocating temporary render output.
    _media_run(["ffmpeg", "-version"], "FFmpeg preflight")
    _media_run(["ffprobe", "-version"], "ffprobe preflight")
    for path, label in ((narration, "narration"), *((Path(s.get("asset", {}).get("path", "")), f"scene {s['id']} media") for s in t["scenes"])):
        probe = _media_run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)], f"{label} decode preflight")
        try:
            streams = json.loads(probe.stdout).get("streams", [])
        except (ValueError, AttributeError):
            raise MediaError(f"{label}: ffprobe returned invalid metadata") from None
        expected = "audio" if label == "narration" else None
        if not streams or (expected and not any(s.get("codec_type") == expected for s in streams)):
            raise MediaError(f"{label}: no decodable {expected or 'media'} stream found")
        _media_run(["ffmpeg", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(path), "-map", "0:a:0" if expected else "0:v:0", "-f", "null", "-"], f"{label} decode")
    with tempfile.TemporaryDirectory(prefix="documentary-render-") as td:
        td=Path(td); clips=[]; manifest=[]
        for i, scene in enumerate(t["scenes"]):
            asset=(scene.get("asset") or {}).get("path")
            if not asset or not Path(asset).is_file():
                raise ValueError(f"scene {scene['id']} has no decodable selected asset")
            clip=td/f"{i:03d}.mp4"
            source=Path(asset)
            if source.suffix.lower()==".svg":
                raise MediaError(f"scene {scene['id']}: SVG rasterization is not supported by the FFmpeg-only renderer; use a raster image")
            elif source.suffix.lower() in {".mp4",".mov",".m4v",".webm",".mkv"}:
                input_args=["-stream_loop","-1","-i",asset]
            else:
                input_args=["-loop","1","-i",asset]
            treatment=scene.get("treatment", "static")
            if source.suffix.lower() in {".mp4",".mov",".m4v",".webm",".mkv"}: vf="scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p"
            elif treatment in {"push_in","document_zoom","crop_reframe"}: vf="scale=2200:1238,crop=1920:1080:x='(iw-1920)*(0.15+0.7*t/{d})':y='(ih-1080)*(0.1+0.5*t/{d})',format=yuv420p".format(d=max(scene["duration"],1))
            elif treatment == "pan_reveal": vf="scale=2100:1181,crop=1920:1080:x='(iw-1920)*t/{d}':y=40,format=yuv420p".format(d=max(scene["duration"],1))
            else: vf="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
            _media_run(["ffmpeg","-y","-v","error","-xerror",*input_args,"-t",str(scene["duration"]),"-vf",vf,"-r","30","-an","-c:v","libx264","-preset","ultrafast",str(clip)],f"scene {scene['id']} render")
            clips.append(clip); manifest.append(f"file '{clip}'")
        concat=td/"concat.txt"; concat.write_text("\n".join(manifest)+"\n")
        video=td/"video.mp4"
        _media_run(["ffmpeg","-y","-v","error","-xerror","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(video)],"clip concatenation")
        _media_run(["ffmpeg","-y","-v","error","-xerror","-i",str(video),"-i",str(narration),"-filter_complex","[1:a]aresample=48000,apad,atrim=duration="+str(dur)+"[a]","-map","0:v:0","-map","[a]","-t",str(dur),"-c:v","copy","-c:a","aac","-shortest",str(out)],"final render")

def revise(timeline_path: Path, scene_id: str, out: Path):
    t=json.loads(timeline_path.read_text()); ids={s["id"] for s in t["scenes"]}
    if scene_id not in ids: raise ValueError(f"unknown scene: {scene_id}")
    out.write_text(json.dumps({"base_timeline":str(timeline_path),"affected_scenes":[scene_id],"preserved_scenes":sorted(ids-{scene_id}),"status":"READY_FOR_REGIONAL_RERENDER"},indent=2)+"\n")

def qc(timeline_path: Path, video: Path, out: Path):
    t=json.loads(timeline_path.read_text())
    editorial=t.get("editorial_gate",{"pass":False,"reasons":["missing editorial gate"]})
    expected=float(t["duration"]); fps=float(t.get("fps", 30)); reasons=[]; probe={}; v=audio=None; actual=None; actual_fps=frames=None; audio_duration=None; integrated=None
    try:
        probe_result=_media_run(["ffprobe","-v","error","-count_frames","-show_format","-show_streams","-of","json",str(video)],"QC ffprobe")
        probe=json.loads(probe_result.stdout)
        v=next((s for s in probe["streams"] if s["codec_type"]=="video"),None)
        audio=next((s for s in probe["streams"] if s["codec_type"]=="audio"),None)
        if not v: reasons.append("QC: video stream is missing")
        if not audio: reasons.append("QC: audio stream is missing")
        if v:
            try: actual_fps=float(Fraction(v["avg_frame_rate"]))
            except (ValueError, ZeroDivisionError): raise ValueError("QC: invalid video fps metadata") from None
            try: frames=int(v["nb_read_frames"])
            except (ValueError, TypeError): raise ValueError("QC: invalid decoded frame count") from None
            if actual_fps <= 0 or not math.isfinite(actual_fps) or abs(actual_fps-fps) > .01: reasons.append(f"QC: fps must be {fps:g} (got {actual_fps:g})")
            if frames <= 0: reasons.append("QC: video has no decoded frames")
        if audio:
            audio_duration=float(audio["duration"])
            if int(audio["sample_rate"]) <= 0 or int(audio["channels"]) <= 0: reasons.append("QC: audio stream has invalid sample rate or channel count")
        actual=float(probe["format"]["duration"])
        if not math.isfinite(actual) or abs(actual-expected) > .1: reasons.append(f"QC: duration {actual:g}s is outside expected {expected:g}s ±0.1s")
        for label, stream_duration in (("video", float(v["duration"]) if v else None), ("audio", audio_duration)):
            if stream_duration is not None and (not math.isfinite(stream_duration) or abs(stream_duration-expected) > .1): reasons.append(f"QC: {label} duration is outside expected {expected:g}s ±0.1s")
        tolerance=max(2, math.ceil(fps*.1))
        expected_frames=round(expected*fps)
        if frames is not None and abs(frames-expected_frames) > tolerance: reasons.append(f"QC: decoded frame count {frames} differs from expected {expected_frames} by more than {tolerance}")
        if v and (int(v["width"])!=1920 or int(v["height"])!=1080): reasons.append("QC: resolution must be 1920x1080")
        loudness=_media_run(["ffmpeg","-v","info","-xerror","-err_detect","explode","-i",str(video),"-map","0:v:0","-map","0:a:0","-af","ebur128=framelog=verbose","-f","null","-"],"QC ffmpeg decode and audio analysis")
        match=re.findall(r"I:\s*(-?(?:\d+(?:\.\d+)?|inf)) LUFS",loudness.stdout + loudness.stderr)
        if match: integrated=float(match[-1])
        if integrated is None or not math.isfinite(integrated) or integrated <= -70: reasons.append("QC: audio is silent, undecodable, or has no integrated loudness measurement")
    except MediaError as exc:
        reasons.append(str(exc))
    except (ValueError, TypeError, KeyError, StopIteration, ZeroDivisionError, OverflowError) as exc:
        reasons.append(str(exc) if str(exc).startswith("QC:") else f"QC: ffprobe returned invalid media metadata ({type(exc).__name__})")
    checks={"duration_expected":expected,"duration_actual":actual if actual is None or math.isfinite(actual) else None,"resolution":[v.get("width"),v.get("height")] if v else None,"has_audio":audio is not None,"integrated_lufs":integrated,"fps":actual_fps,"frame_count":frames,"expected_frame_count":round(expected*fps) if math.isfinite(fps) else None,"audio_duration":audio_duration if audio_duration is None or math.isfinite(audio_duration) else None}
    technical=not reasons
    if not editorial.get("pass"):
        reasons.append("QC: editorial gate failed: " + "; ".join(editorial.get("reasons", [])))
    result={"pass":technical and editorial["pass"],"technical_pass":technical,"editorial_pass":editorial["pass"],"checks":checks,"reasons":reasons,"editorial":editorial,"treatment_qc":{"treatment_diversity":editorial.get("metrics",{}).get("treatment_diversity",0),"composition_diversity":editorial.get("metrics",{}).get("composition_diversity",0),"consecutive_static_equivalent_shots":editorial.get("metrics",{}).get("consecutive_static_equivalent_shots",0)}}
    out.write_text(json.dumps(result,indent=2)+"\n"); return result
