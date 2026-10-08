import json, os, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from narrativecut.claude_plan import PLAN_SCHEMA, PlanningError, load_scene_plan, plan_scenes, validate_plan
from narrativecut.core import build, parse_script

SCRIPT='In 1969 the archive opened to the public. Visitors could read the original letters. Today the collection holds 40,000 documents.'

def scene(ids, role='document-evidence', claim='context'):
    return {'beat_ids':ids,'summary':'s','purpose':'context','claim_type':claim,'visual_role':role,'search_query':'archive reading room 1969','on_screen_text':'','rationale':'r'}

class FakeClient:
    def __init__(self, payload, stop_reason='end_turn'):
        self.calls=[]; text=payload if isinstance(payload,str) else json.dumps(payload)
        self.response=SimpleNamespace(stop_reason=stop_reason,stop_details=SimpleNamespace(category='cyber'),model='claude-opus-5-5',
            content=[SimpleNamespace(type='thinking',thinking=''),SimpleNamespace(type='text',text=text)],usage=SimpleNamespace(input_tokens=120,output_tokens=80))
        self.beta=SimpleNamespace(messages=SimpleNamespace(create=self._create))
    def _create(self, **kwargs):
        self.calls.append(kwargs); return self.response

def test_plan_derives_timing_from_beats_and_writes_file(tmp_path):
    client=FakeClient({'logline':'An archive opens.','scenes':[scene(['scene-001','scene-002'],claim='event'),scene(['scene-003'],'data-chart','number')],'editorial_risks':['verify 40,000 count']})
    plan=plan_scenes({'title':'Archive'},SCRIPT,tmp_path,client=client)
    beats=parse_script(SCRIPT)
    assert [s['beat_ids'] for s in plan['scenes']]==[['scene-001','scene-002'],['scene-003']]
    assert plan['scenes'][0]['start']==0 and plan['scenes'][0]['duration']==round(beats[0].duration+beats[1].duration,3)
    assert plan['scenes'][1]['start']==beats[2].start
    assert plan['planner']=={'provider':'anthropic','model':'claude-opus-5-5','input_tokens':120,'output_tokens':80}
    assert json.loads((tmp_path/'scene-plan.json').read_text())==plan
    call=client.calls[0]
    assert call['output_config']['format']=={'type':'json_schema','schema':PLAN_SCHEMA}
    assert '[scene-003] Today the collection holds 40,000 documents.' in call['messages'][0]['content']

@pytest.mark.parametrize('scenes,message',[
    ([scene(['scene-001']),scene(['scene-002'])],'not assigned'),
    ([scene(['scene-001','scene-001','scene-002','scene-003'])],'more than once'),
    ([scene(['scene-001','scene-002','scene-009'])],'unknown beat id'),
    ([scene(['scene-002']),scene(['scene-001','scene-003'])],'script order'),
    ([scene(['scene-001','scene-002','scene-003'],'stock-photo')],'invalid visual_role'),
    ([],'non-empty list'),
])
def test_validate_plan_rejects_bad_coverage(scenes,message):
    with pytest.raises(PlanningError,match=message): validate_plan({'scenes':scenes},parse_script(SCRIPT))

@pytest.mark.parametrize('stop_reason,payload,message',[('refusal','','declined'),('max_tokens','{','truncated'),('end_turn','not json','not valid JSON')])
def test_unusable_responses_raise_and_write_nothing(tmp_path,stop_reason,payload,message):
    with pytest.raises(PlanningError,match=message): plan_scenes({},SCRIPT,tmp_path,client=FakeClient(payload,stop_reason))
    assert not (tmp_path/'scene-plan.json').exists()

@pytest.mark.skipif(not os.environ.get('NARRATIVECUT_LIVE_CLAUDE'),reason='set NARRATIVECUT_LIVE_CLAUDE=1 and Anthropic credentials to call the real API')
def test_live_claude_plan(tmp_path):
    plan=plan_scenes({'title':'Archive'},SCRIPT,tmp_path)
    assert sum(len(s['beat_ids']) for s in plan['scenes'])==plan['beat_count']==3

def asset(root, name, role, subject):
    (root/f'{name}.png').write_bytes(name.encode())
    (root/f'{name}.png.json').write_text(json.dumps({'kind':'public_domain','source':'archive','rights':'public domain','subject':subject,'role':role}))

def test_scene_plan_guides_asset_selection(tmp_path):
    assets=tmp_path/'assets'; assets.mkdir()
    asset(assets,'room','context-broll','archive public room')
    asset(assets,'ledger','document-evidence','donation ledger')
    script='The archive opened to the public.'
    baseline=build({},script,assets,tmp_path/'base')
    assert baseline['scenes'][0]['asset']['subject']=='archive public room' and 'scene_plan' not in baseline
    plan=plan_scenes({},script,tmp_path/'plan',client=FakeClient({'scenes':[dict(scene(['scene-001']),search_query='donation ledger')]}))
    guided=build({},script,assets,tmp_path/'guided',plan=plan)
    s=guided['scenes'][0]
    assert s['asset']['subject']=='donation ledger'
    assert s['plan']=={'scene':'plan-001','visual_role':'document-evidence','search_query':'donation ledger'}
    assert guided['scene_plan']['planner']['model']=='claude-opus-5-5'
    assert [x['start'] for x in guided['scenes']]==[x['start'] for x in baseline['scenes']]
    assert build({},script,assets,tmp_path/'again',plan=plan)==guided

def test_load_scene_plan_rejects_plan_for_other_script(tmp_path):
    plan_scenes({},SCRIPT,tmp_path,client=FakeClient({'scenes':[scene(['scene-001','scene-002','scene-003'])]}))
    assert load_scene_plan(tmp_path/'scene-plan.json',SCRIPT)['beat_count']==3
    with pytest.raises(PlanningError,match='does not match the script'):
        load_scene_plan(tmp_path/'scene-plan.json',SCRIPT.replace('1969','1970'))
    saved=json.loads((tmp_path/'scene-plan.json').read_text())
    for broken in ({k:v for k,v in saved.items() if k!='planner'}, {**saved,'scenes':[{k:v for k,v in saved['scenes'][0].items() if k!='id'}]}):
        (tmp_path/'broken.json').write_text(json.dumps(broken))
        with pytest.raises(PlanningError): load_scene_plan(tmp_path/'broken.json',SCRIPT)
    (tmp_path/'bad.json').write_text('{')
    with pytest.raises(PlanningError,match='malformed JSON'): load_scene_plan(tmp_path/'bad.json',SCRIPT)

def test_cli_builds_with_saved_scene_plan(tmp_path):
    import subprocess
    assets=tmp_path/'assets'; assets.mkdir(); asset(assets,'ledger','document-evidence','donation ledger')
    (tmp_path/'script.txt').write_text(SCRIPT); (tmp_path/'brief.json').write_text('{}')
    plan_scenes({},SCRIPT,tmp_path/'plan',client=FakeClient({'scenes':[scene(['scene-001','scene-002','scene-003'])]}))
    args=[sys.executable,'-m','narrativecut','--brief',str(tmp_path/'brief.json'),'--script',str(tmp_path/'script.txt'),'--assets',str(assets),'--output',str(tmp_path/'out')]
    ok=subprocess.run([*args,'--scene-plan',str(tmp_path/'plan'/'scene-plan.json')],capture_output=True,text=True,cwd=Path(__file__).parents[1])
    assert ok.returncode==0, ok.stderr
    assert json.loads((tmp_path/'out'/'timeline.json').read_text())['scenes'][2]['plan']['scene']=='plan-001'
    (tmp_path/'script.txt').write_text('Something else entirely.')
    bad=subprocess.run([*args,'--scene-plan',str(tmp_path/'plan'/'scene-plan.json')],capture_output=True,text=True,cwd=Path(__file__).parents[1])
    assert bad.returncode==1 and 'does not match the script' in bad.stderr

def test_keychain_key_used_when_env_missing(monkeypatch):
    from narrativecut import claude_plan
    calls=[]
    def fake_run(cmd, **kw):
        calls.append(cmd); return SimpleNamespace(returncode=0, stdout='sk-test\n')
    monkeypatch.setattr(claude_plan.sys,'platform','darwin')
    monkeypatch.setattr(claude_plan.subprocess,'run',fake_run)
    monkeypatch.setenv('NARRATIVECUT_KEYCHAIN_SERVICE','my-service')
    assert claude_plan._keychain_api_key()=='sk-test'
    assert calls[0][:4]==['security','find-generic-password','-s','my-service']

def test_keychain_missing_entry_returns_none(monkeypatch):
    from narrativecut import claude_plan
    monkeypatch.setattr(claude_plan.sys,'platform','darwin')
    monkeypatch.setattr(claude_plan.subprocess,'run',lambda cmd, **kw: SimpleNamespace(returncode=44, stdout=''))
    assert claude_plan._keychain_api_key() is None
    monkeypatch.setattr(claude_plan.sys,'platform','linux')
    assert claude_plan._keychain_api_key() is None
