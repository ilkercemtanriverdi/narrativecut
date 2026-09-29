import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from narrativecut import core
from narrativecut import __main__ as cli


def test_module_and_console_preserve_validation_exit_codes(tmp_path):
    for command in ([sys.executable, '-m', 'narrativecut'],
                    [str(Path(sys.executable).with_name('narrativecut'))]):
        result = subprocess.run([*command, '--validate-assets', '--assets', str(tmp_path)],
                                capture_output=True, text=True)
        assert result.returncode == 1
        assert not json.loads(result.stdout)['valid']
        missing = subprocess.run([*command, '--validate-assets', '--assets', str(tmp_path/'missing')],
                                 capture_output=True, text=True)
        assert missing.returncode != 0
        assert 'directory does not exist' in missing.stderr
        assert 'Traceback' not in missing.stderr


def test_cli_returns_failure_when_qc_rejects_render(tmp_path, monkeypatch, capsys):
    project = tmp_path/'project.json'
    project.write_text(json.dumps({'schema_version': '1.0', 'brief': {},
                                   'script': 'A scene.', 'assets': str(tmp_path)}))
    monkeypatch.setattr(sys, 'argv', ['narrativecut', '--project', str(project),
                                    '--output', str(tmp_path/'out'), '--assemble'])
    monkeypatch.setattr(cli, 'assemble', lambda *args: None)
    monkeypatch.setattr(cli, 'qc', lambda *args: {'pass': False, 'reasons': ['decode failed']})
    assert cli.main() == 1
    assert 'QC failed' in capsys.readouterr().err


@pytest.fixture
def qc_inputs(tmp_path, monkeypatch):
    timeline = tmp_path/'timeline.json'
    timeline.write_text(json.dumps({'duration': 3, 'fps': 30, 'editorial_gate': {'pass': True}}))
    probe = {'format': {'duration': '3'}, 'streams': [
        {'codec_type': 'video', 'width': 1920, 'height': 1080, 'duration': '3',
         'avg_frame_rate': '30/1', 'nb_read_frames': '90'},
        {'codec_type': 'audio', 'duration': '3', 'sample_rate': '48000', 'channels': 1}]}

    def run(command, **kwargs):
        if command[0] == 'ffprobe':
            return subprocess.CompletedProcess(command, 0, json.dumps(probe), '')
        return subprocess.CompletedProcess(command, 0, '', 'I: -21.0 LUFS\n')

    monkeypatch.setattr(core.subprocess, 'run', run)
    return timeline, tmp_path/'video.mp4', tmp_path/'qc.json', probe


@pytest.mark.parametrize(('field', 'value', 'reason'), [
    ('duration', '2.8', 'duration'), ('duration', '3.2', 'duration'),
    ('duration', 'nan', 'duration'), ('duration', 'inf', 'duration'),
    ('avg_frame_rate', '24/1', 'fps'), ('avg_frame_rate', '0/0', 'fps'),
    ('nb_read_frames', '0', 'frame'), ('nb_read_frames', '70', 'frame'),
    ('nb_read_frames', 'N/A', 'frame'), ('width', 1280, 'resolution'),
    ('sample_rate', '0', 'audio'), ('channels', 0, 'audio'),
])
def test_qc_rejects_invalid_media_metadata(qc_inputs, field, value, reason):
    timeline, video, out, probe = qc_inputs
    if field == 'duration': probe['format'][field] = value
    elif field in {'sample_rate', 'channels'}: probe['streams'][1][field] = value
    else: probe['streams'][0][field] = value
    result = core.qc(timeline, video, out)
    assert not result['pass']
    assert reason in ' '.join(result['reasons']).lower()
    assert json.loads(out.read_text()) == result


@pytest.mark.parametrize('duration', ['2.91', '3', '3.09'])
def test_qc_accepts_duration_rounding(qc_inputs, duration):
    timeline, video, out, probe = qc_inputs
    probe['format']['duration'] = duration
    assert core.qc(timeline, video, out)['pass']


@pytest.mark.parametrize('index', [0, 1])
def test_qc_checks_each_stream_duration(qc_inputs, index):
    timeline, video, out, probe = qc_inputs
    probe['streams'][index]['duration'] = '1'
    assert not core.qc(timeline, video, out)['pass']


@pytest.mark.parametrize('loudness', ['', 'I: -70.0 LUFS', 'I: -inf LUFS'])
def test_qc_rejects_missing_or_silent_audio(qc_inputs, monkeypatch, loudness):
    timeline, video, out, probe = qc_inputs
    original = core.subprocess.run
    monkeypatch.setattr(core.subprocess, 'run', lambda command, **kwargs:
                        original(command, **kwargs) if command[0] == 'ffprobe' else
                        subprocess.CompletedProcess(command, 0, '', loudness))
    assert not core.qc(timeline, video, out)['pass']


@pytest.mark.parametrize(('tool', 'failure'), [
    ('ffprobe', FileNotFoundError()), ('ffmpeg', PermissionError()),
    ('ffprobe', subprocess.CalledProcessError(1, 'ffprobe')),
    ('ffmpeg', subprocess.CalledProcessError(1, 'ffmpeg')),
])
def test_qc_tool_failures_are_reported(qc_inputs, monkeypatch, tool, failure):
    timeline, video, out, probe = qc_inputs
    original = core.subprocess.run

    def run(command, **kwargs):
        if command[0] == tool: raise failure
        return original(command, **kwargs)

    monkeypatch.setattr(core.subprocess, 'run', run)
    result = core.qc(timeline, video, out)
    assert not result['pass']
    assert tool in ' '.join(result['reasons'])
    assert json.loads(out.read_text()) == result


def test_qc_rejects_malformed_probe_json(qc_inputs, monkeypatch):
    timeline, video, out, _ = qc_inputs
    monkeypatch.setattr(core.subprocess, 'run', lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 0, '{', ''))
    result = core.qc(timeline, video, out)
    assert not result['pass']
    assert 'ffprobe' in ' '.join(result['reasons'])


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    missing = [name for name in ('ffmpeg', 'ffprobe') if not shutil.which(name)]
    if missing:
        if os.environ.get('NARRATIVECUT_REQUIRE_FFMPEG') == '1':
            pytest.fail('required render tools missing: ' + ', '.join(missing))
        pytest.skip('install ffmpeg and ffprobe to run render integration tests')
    root = tmp_path_factory.mktemp('render')
    assets = root/'assets'; assets.mkdir()
    roles = ['primary-footage', 'specific-entity', 'document-evidence', 'data-chart', 'screenshot']
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo']
    for i, (word, role) in enumerate(zip(words, roles)):
        asset = assets/f'{word}.ppm'
        asset.write_bytes(b'P6\n16 9\n255\n' + bytes((30+i*40, 80, 120))*16*9)
        asset.with_suffix('.ppm.json').write_text(json.dumps({
            'source': 'synthetic test fixture', 'rights': 'CC0', 'subject': word,
            'role': role, 'kind': 'public_domain', 'match_level': 'direct', 'specificity': 'topic'}))
    # Exercise the looping video path as well as still-image treatments.
    clip = assets/'Alpha.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=red:s=160x90:r=30:d=1', '-c:v', 'libx264', str(clip)], check=True)
    (assets/'Alpha.ppm').unlink()
    (assets/'Alpha.ppm.json').rename(assets/'Alpha.mp4.json')
    narration = root/'narration.wav'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=15', str(narration)], check=True)
    project = root/'project.json'
    project.write_text(json.dumps({'schema_version': '1.0', 'brief': {'title': 'Synthetic render'},
                                   'script': '. '.join(words)+'.', 'assets': str(assets)}))
    command = [sys.executable, '-m', 'narrativecut', '--project', str(project),
               '--output', str(root/'out'), '--assemble', '--narration', str(narration)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return root, command


def test_real_render_and_qc(rendered):
    root, _ = rendered
    out = root/'out'
    timeline = json.loads((out/'timeline.json').read_text())
    report = json.loads((out/'qc-report.json').read_text())
    assert timeline['editorial_gate']['pass']
    assert [s['start'] for s in timeline['scenes']] == [0, 3, 6, 9, 12]
    assert report['pass'] and report['checks']['resolution'] == [1920, 1080]
    assert report['checks']['fps'] == 30
    assert report['checks']['frame_count'] == 450
    assert report['checks']['has_audio']
    # The first looping red clip must end at the planned scene boundary.
    pixels = []
    for time in ('2.8', '3.2'):
        pixels.append(subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', time,
            '-i', str(out/'documentary.mp4'), '-frames:v', '1', '-vf', 'scale=1:1',
            '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']))
    assert pixels[0][0] > 200 and pixels[0][1] < 20
    assert pixels[1][0] < 100 and pixels[1][1] > 50


@pytest.mark.parametrize('duration', [14, 16])
def test_real_qc_rejects_long_and_short_output(rendered, tmp_path, duration):
    root, _ = rendered
    timeline = json.loads((root/'out/timeline.json').read_text())
    timeline['duration'] = duration
    path = tmp_path/'timeline.json'; path.write_text(json.dumps(timeline))
    result = core.qc(path, root/'out/documentary.mp4', tmp_path/'qc.json')
    assert not result['pass']
    assert 'duration' in ' '.join(result['reasons'])


def test_real_qc_rejects_corrupt_media(rendered, tmp_path):
    root, _ = rendered
    broken = tmp_path/'broken.mp4'; broken.write_bytes(b'not a video')
    result = core.qc(root/'out/timeline.json', broken, tmp_path/'qc.json')
    assert not result['pass']
    assert 'ffprobe' in ' '.join(result['reasons'])


@pytest.mark.parametrize('failure', ['missing-media', 'broken-media', 'missing-narration', 'broken-narration', 'missing-tools', 'missing-ffprobe'])
def test_real_render_failures_are_clear(rendered, tmp_path, failure):
    root, _ = rendered
    timeline = copy.deepcopy(json.loads((root/'out/timeline.json').read_text()))
    narration = root/'narration.wav'
    env = os.environ.copy()
    if failure.endswith('media'):
        media = tmp_path/'broken.png'
        if failure == 'broken-media': media.write_bytes(b'not an image')
        timeline['scenes'][0]['asset']['path'] = str(media)
    elif failure.endswith('narration'):
        narration = tmp_path/'broken.wav'
        if failure == 'broken-narration': narration.write_bytes(b'not audio')
    else:
        env['PATH'] = str(tmp_path)
        if failure == 'missing-ffprobe':
            (tmp_path/'ffmpeg').symlink_to(shutil.which('ffmpeg'))
    path = tmp_path/'timeline.json'; path.write_text(json.dumps(timeline))
    result = subprocess.run([sys.executable, '-c',
        'import sys; from pathlib import Path; from narrativecut.core import assemble; '
        'assemble(*map(Path, sys.argv[1:]))', str(path), str(tmp_path/'out.mp4'), str(narration)],
        capture_output=True, text=True, env=env)
    assert result.returncode != 0
    assert any(word in result.stderr.lower() for word in ('scene', 'narration', 'ffmpeg'))
