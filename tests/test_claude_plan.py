import json, os, sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from narrativecut.claude_plan import PLAN_SCHEMA, PlanningError, plan_scenes, validate_plan
from narrativecut.core import parse_script

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
