from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import subprocess
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import tintprobe.evaluation_dependencies as deps


def repository(path):
    subprocess.run(['git','init','-q',str(path)],check=True)
    subprocess.run(['git','-C',str(path),'-c','user.name=Test','-c','user.email=test@example.com','commit','--allow-empty','-qm','fixture'],check=True)
    return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()


def test_pins_are_portable_and_shared_sources_are_deduplicated():
    sources=deps.dependencies(['ithilien-dawn'])
    assert len([p for p in sources if p.endswith('/kanso')])==1
    assert all(p.startswith('evaluation/deps/') for p in sources)
    assert not any('gruvbox' in p for p in sources)
    assert any('gruvbox' in p for p in deps.dependencies(['gruvbox-material-light-soft']))
    with pytest.raises(ValueError,match='Unknown themes'):deps.dependencies(['typo'])


def test_missing_sources_are_one_blocker_with_setup_instruction(tmp_path):
    with pytest.raises(FileNotFoundError,match='make setup-evaluation') as error:
        deps.validate({n:{'path':str(tmp_path/n),'revision':'x'} for n in ('a','b')})
    assert str(tmp_path/'a') in str(error.value) and str(tmp_path/'b') in str(error.value)


def test_fetch_is_pinned_idempotent_and_preserves_dirty_checkouts(tmp_path):
    origin=tmp_path/'origin';pin=repository(origin);target=tmp_path/'target'
    d={'path':str(target),'url':str(origin),'revision':pin}
    deps.fetch_one(d);deps.fetch_one(d)
    (target/'personal.txt').write_text('leave me alone')
    with pytest.raises(ValueError,match='local changes'):deps.fetch_one(d)
    assert (target/'personal.txt').read_text()=='leave me alone'
    with pytest.raises(ValueError,match='revision mismatch'):
        deps.validate({'wrong':dict(d,revision='0'*40)})


def test_failed_fetch_does_not_poison_retry(tmp_path):
    target=tmp_path/'target'
    with pytest.raises(subprocess.CalledProcessError):
        deps.fetch_one({'path':str(target),'url':str(tmp_path/'absent'),'revision':'0'*40})
    assert not target.exists()
    assert not list(tmp_path.glob('.fetch-*'))
