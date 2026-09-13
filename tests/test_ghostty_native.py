from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.capture_ghostty import pixel_gate
from tintprobe.evaluate_ghostty import prepare


def test_blank_or_wrong_capture_fails_calibration():
    colors = ['#8B3037', '#315F46']
    assert not pixel_gate({'counts':{}}, colors)['pass']
    assert not pixel_gate({'counts':{'#8B3037':500}}, colors)['pass']
    assert pixel_gate({'counts':dict.fromkeys(colors, 500)}, colors)['pass']


def test_real_command_fixtures_are_not_native_validation(tmp_path):
    result = prepare(tmp_path)
    assert result['status'] == 'blocked'
    assert not result['pass']
    assert result['coverage']['cursor'] == 'untested'
    rows = {r['id']:r for r in result['results']}
    assert rows['pytest']['exit_code'] == 1  # Intentional failure, not fixture failure.
    assert rows['pytest']['status'] == 'prepared'
    import re
    plain = re.sub(rb'\x1b\[[0-9;]*m', b'', (tmp_path/'pytest.ansi').read_bytes())
    assert b'1 failed, 1 passed' in plain
    assert rows['git-word-diff']['contains_ansi']
    assert b'worker.py' in (tmp_path/'git-diff.ansi').read_bytes()
    assert json.loads((tmp_path/'report.json').read_text())['pass'] is False


def test_capture_failure_remains_blocked(tmp_path, monkeypatch):
    import tintprobe.capture_ghostty as capture_ghostty
    def denied(*args):
        raise RuntimeError('Screen Recording permission is unavailable')
    monkeypatch.setattr(capture_ghostty, 'capture', denied)
    result = prepare(tmp_path, native_capture=True)
    assert result['status'] == 'blocked'
    assert not result['pass']
    assert 'Screen Recording' in result['reason']


def test_capture_subprocess_stderr_is_preserved(tmp_path, monkeypatch):
    import subprocess
    import tintprobe.capture_ghostty as capture_ghostty
    def denied(*args):
        raise subprocess.CalledProcessError(1, ['helper', 'windows'],
            stderr=b'Screen Recording permission is unavailable\n')
    monkeypatch.setattr(capture_ghostty, 'capture', denied)
    result = prepare(tmp_path, native_capture=True)
    assert result['reason'] == 'Native capture failed: Screen Recording permission is unavailable'
    assert not result['pass']


def test_launcher_handles_spaces_without_optional_python_imports(tmp_path):
    import subprocess
    from tintprobe.capture_ghostty import write_launcher
    output=tmp_path/'space and apostrophe\x27s directory'
    output.mkdir()
    payload=output/'payload.ansi';payload.write_bytes(b'hello\n')
    ready=output/'ready marker';release=output/'release marker';release.touch()
    launcher,started,log=write_launcher(output,'fixture',payload,ready,release)
    # -S disables site-packages: emitting bytes must require only stdlib.
    import shlex
    launcher.write_text(launcher.read_text().replace('exec '+shlex.quote(sys.executable)+' ', 'exec '+shlex.quote(sys.executable)+' -S '))
    result=subprocess.run(['/bin/sh',str(launcher)],capture_output=True,timeout=10,
                          env={'PATH':'/usr/bin:/bin','PYTHONNOUSERSITE':'1'})
    assert result.returncode == 0, log.read_text()
    assert b'hello' in result.stdout
    assert ready.exists() and started.exists()


def test_timeout_distinguishes_child_and_window_errors(tmp_path):
    from tintprobe.capture_ghostty import timeout_reason
    ready,started,log=[tmp_path/x for x in ('ready','started','log')]
    assert 'did not start' in timeout_reason(ready,started,log)
    started.touch();log.write_text('ModuleNotFoundError: dependency')
    assert 'ModuleNotFoundError' in timeout_reason(ready,started,log)
    ready.touch()
    assert 'no uniquely titled' in timeout_reason(ready,started,log)
