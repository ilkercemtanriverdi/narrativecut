import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from fluxengine_video_studio.core import parse_script, build, revise

def test_parse_and_outputs(tmp_path):
    assets=tmp_path/'assets'; assets.mkdir(); (assets/'archive.png').write_bytes(b'fixture')
    (assets/'archive.png.json').write_text(json.dumps({'kind':'public_domain','source':'fixture archive','rights':'public domain','subject':'history archive'}))
    out=tmp_path/'out'; t=build({'title':'Test'},'History changes quickly. The archive reveals why.',assets,out)
    assert t['scenes'][0]['asset']['kind']=='public_domain'; assert (out/'subtitles.srt').exists(); assert (out/'asset-license-report.json').exists()
    revise(out/'timeline.json','scene-001',out/'revision-manifest.json'); assert 'scene-001' in (out/'revision-manifest.json').read_text()
