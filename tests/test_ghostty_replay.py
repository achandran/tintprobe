from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.ghostty_replay import fixtures
from tintprobe.context import ROOT


def source(tmp_path,modifiers='BOLD | DIM'):
    path=tmp_path/'codex-cells.json'
    path.write_text(json.dumps([{'file':'request','width':60,'cells':[
        {'row':0,'col':0,'text':'=','fg':'Rgb(0, 0, 0)','bg':'Reset','modifiers':modifiers}]}]))
    (tmp_path/'report.json').write_text(json.dumps({'status':'pass','source_revision':'fixture',
        'theme_sha256':hashlib.sha256((port_path('codex_theme')).read_bytes()).hexdigest()}))
    return path


def test_native_replay_preserves_dim_and_bold_in_bytes_and_oracle(tmp_path):
    path=source(tmp_path);out=tmp_path/'out';out.mkdir()
    row=fixtures(out,path)[0]
    assert ';1;2m=' in (out/row['ansi']).read_text()
    cell=json.loads((out/(row['id']+'.cells.json')).read_text())['cells'][0]
    assert cell['text']=='=' and cell['bold'] and cell['dim']
    assert row['kind']=='native-codex-replay'
    assert 'not live' in row['scope']


def test_stale_theme_and_unknown_modifiers_are_not_native_acceptance(tmp_path):
    path=source(tmp_path,'SLOW_BLINK');out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError,match='Unsupported native modifiers'):fixtures(out,path)
    path=source(tmp_path)
    report=json.loads((tmp_path/'report.json').read_text());report['theme_sha256']='stale'
    (tmp_path/'report.json').write_text(json.dumps(report))
    with pytest.raises(ValueError,match='current exported theme'):fixtures(out,path)


def test_clipped_native_replay_is_rejected(tmp_path):
    path=source(tmp_path);out=tmp_path/'out';out.mkdir()
    shots=json.loads(path.read_text());shots[0]['cells'][0]['row']=36;path.write_text(json.dumps(shots))
    with pytest.raises(ValueError,match='viewport'):fixtures(out,path)
