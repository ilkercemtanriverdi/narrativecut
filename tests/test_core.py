import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from fluxengine_video_studio.core import build, parse_script, revise, srt_time, write_srt

def test_parse_and_outputs(tmp_path):
    assets=tmp_path/'assets'; assets.mkdir(); (assets/'archive.png').write_bytes(b'fixture')
    (assets/'archive.png.json').write_text(json.dumps({'kind':'public_domain','source':'fixture archive','rights':'public domain','subject':'history archive'}))
    out=tmp_path/'out'; t=build({'title':'Test'},'History changes quickly. The archive reveals why.',assets,out)
    assert t['scenes'][0]['asset']['kind']=='public_domain'; assert (out/'subtitles.srt').exists(); assert (out/'asset-license-report.json').exists()
    revise(out/'timeline.json','scene-001',out/'revision-manifest.json'); assert 'scene-001' in (out/'revision-manifest.json').read_text()

def test_parse_script_splits_beats_and_uses_minimum_duration():
    beats = parse_script("First point. Second point.")
    assert [b.id for b in beats] == ["scene-001", "scene-002"]
    assert beats[0].duration == 3.0
    assert beats[1].start == 3.0

def test_srt_time_formats_milliseconds():
    assert srt_time(3661.234) == "01:01:01,234"

def test_write_srt_contains_ordered_cues(tmp_path):
    path = tmp_path / "captions.srt"
    write_srt(parse_script("One sentence. Two sentence."), path)
    text = path.read_text()
    assert "1\n00:00:00,000 --> 00:00:03,000\nOne sentence." in text
    assert text.count("\n\n") == 1

def test_build_is_deterministic(tmp_path):
    assets = tmp_path / "assets"; assets.mkdir()
    (assets / "archive.png").write_bytes(b"fixture")
    (assets / "archive.png.json").write_text(json.dumps({'kind':'public_domain','source':'archive','rights':'public domain','subject':'history archive'}))
    first = build({'title':'Test'}, 'History changes.', assets, tmp_path / 'one')
    second = build({'title':'Test'}, 'History changes.', assets, tmp_path / 'two')
    assert first == second
    assert (tmp_path / 'one' / 'timeline.json').read_text() == (tmp_path / 'two' / 'timeline.json').read_text()

def test_missing_asset_is_reported_as_unmatched(tmp_path):
    out = tmp_path / 'out'
    timeline = build({'title':'Test'}, 'No matching asset.', tmp_path / 'missing-assets', out)
    assert timeline['scenes'][0]['asset'] is None
    report = json.loads((out / 'asset-license-report.json').read_text())
    assert report['unmatched_scenes'] == ['scene-001']

def test_empty_script_produces_empty_outputs(tmp_path):
    out = tmp_path / 'out'
    timeline = build({'title':'Empty'}, '', tmp_path / 'assets', out)
    assert timeline['scenes'] == []
    assert timeline['duration'] == 0
    assert json.loads((out / 'asset-license-report.json').read_text())['assets'] == []

def test_invalid_revision_scene_is_rejected(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    (out / 'timeline.json').write_text(json.dumps({'scenes': []}))
    import pytest
    with pytest.raises(ValueError, match='unknown scene'):
        revise(out / 'timeline.json', 'scene-999', out / 'revision.json')
