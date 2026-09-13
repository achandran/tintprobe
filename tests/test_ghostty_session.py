from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tintprobe.capture_ghostty as capture
from tintprobe.ghostty_coverage import synchronize


def test_cleanup_only_closes_owned_window_and_records_confirmation(tmp_path,monkeypatch):
    session=capture.FixtureSession(tmp_path,Path('/helper'))
    session.window=123
    responses=iter([b'{"windows":[123]}',b'{"windows":[]}'])
    monkeypatch.setattr(capture.subprocess,'check_output',lambda *a,**k:next(responses))
    calls=[]
    monkeypatch.setattr(capture.subprocess,'run',lambda command,**k:calls.append(command))
    session.close()
    assert calls==[['/helper','close',session.title,'123']]
    assert session.stop.exists()
    assert json.loads((tmp_path/'session-cleanup.json').read_text())['closed']


def test_cleanup_refuses_changed_window_identity(tmp_path,monkeypatch):
    session=capture.FixtureSession(tmp_path,Path('/helper'));session.window=123
    monkeypatch.setattr(capture.subprocess,'check_output',lambda *a,**k:b'{"windows":[456]}')
    monkeypatch.setattr(capture.subprocess,'run',lambda *a,**k:pytest.fail('Must not close unrelated window'))
    with pytest.raises(RuntimeError,match='identity changed'):session.close()
    assert session.stop.exists()
    assert not (tmp_path/'session-cleanup.json').exists()


def test_one_session_is_closed_when_capture_fails(tmp_path,monkeypatch):
    calls=[]
    class Session:
        title='Ithilien evaluation test';window=123
        def __init__(self,*a):pass
        def open(self):calls.append('open')
        def scene(self,*a):raise RuntimeError('render failed')
        def close(self):calls.append('close')
    monkeypatch.setattr(capture,'FixtureSession',Session)
    monkeypatch.setattr(capture,'build_helper',lambda *a:Path('/helper'))
    monkeypatch.setattr(capture.subprocess,'run',lambda *a,**k:None)
    with pytest.raises(RuntimeError,match='render failed'):
        capture.capture(tmp_path,{'results':[{'id':'case','status':'prepared'}]})
    assert calls==['open','close']


def test_reanalysis_updates_counts_without_claiming_full_coverage(tmp_path):
    report={'results':[{'id':'cursor-block','cursor':{}},{'id':'selection-single','selection':{}}], 'status':'incomplete'}
    quality={'results':[{'id':'cursor-block','status':'pass'},{'id':'selection-single','status':'unverified'}]}
    (tmp_path/'quality.json').write_text(json.dumps(quality))
    synchronize(tmp_path,report,quality)
    saved=json.loads((tmp_path/'report.json').read_text())
    assert saved['coverage']['cursor'].startswith('1/1')
    assert saved['coverage']['selection'].startswith('0/1')
    assert saved['remaining_native_coverage']
    assert saved['pass'] is False
