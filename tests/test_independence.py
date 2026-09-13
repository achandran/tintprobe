"""Public entry points must work without an Ithilien profile or checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys


def isolated(tmp_path, code):
    env = dict(os.environ, TINTPROBE_PROJECT_ROOT=str(tmp_path))
    return subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)


def test_color_math_and_packaged_fixtures_need_no_theme(tmp_path):
    result = isolated(tmp_path, '''
from tintprobe.colors import wcag
from tintprobe.context import evaluation_path, CONFIG
assert CONFIG == {}
assert abs(wcag('#000000','#FFFFFF') - 21) < 1e-12
assert evaluation_path('fixtures/edges/punctuation.after.py').is_file()
print('independent')
''')
    assert result.stdout.strip() == 'independent'


def test_missing_adapter_is_explicit(tmp_path):
    isolated(tmp_path, '''
from tintprobe.context import default_adapter
try:
    default_adapter()
except ValueError as error:
    assert 'Provide a theme adapter' in str(error)
else:
    raise AssertionError('No implicit theme is allowed')
''')


def test_custom_project_role_palette_and_data_override(tmp_path):
    (tmp_path/'tintprobe.json').write_text(json.dumps({'default_theme':'example','palettes':{'variants':{'example':'example.json'}}}))
    (tmp_path/'example.json').write_text(json.dumps({'foregrounds':{'text':'#101010'},'backgrounds':{'base':'#FFFFFF'}}))
    (tmp_path/'evaluation').mkdir()
    (tmp_path/'evaluation/rubric.json').write_text('{"custom":true}')
    isolated(tmp_path, '''
import json
from tintprobe.context import load_palette, evaluation_path
assert load_palette()['foregrounds']['text'] == '#101010'
assert json.loads(evaluation_path('rubric.json').read_text())['custom']
''')


def test_command_help_reaches_the_adapter(tmp_path):
    result = isolated(tmp_path, "import subprocess, sys; subprocess.run([sys.executable, '-m', 'tintprobe', 'compare', '--help'], check=True)")
    assert '--manifest' in result.stdout


def test_native_capture_has_portable_filename_labels():
    import shutil
    import pytest
    from tintprobe.evaluate_theme import capture
    nvim = shutil.which('nvim')
    if not nvim:
        pytest.skip('Neovim is required for native capture')
    shot = capture({'id': 'portable', 'before': 'fixtures/readme/before.py',
                    'after': 'fixtures/readme/after.py', 'filetype': 'python'},
                   160, 'diff', nvim, None,
                   {'paths': [], 'setup': "vim.cmd('colorscheme default')", 'background': 'dark'})
    text = ''.join(c['text'] for c in shot['cells'])
    assert 'before.py' in text and 'after.py' in text
    assert 'fixtures/readme' not in text and 'site-packages' not in text


def test_custom_evaluation_directory_resolves_inputs_outputs_and_sources(tmp_path):
    (tmp_path/'tintprobe.json').write_text(json.dumps({'evaluation_dir': 'tests/evaluation'}))
    data = tmp_path/'tests/evaluation'
    data.mkdir(parents=True)
    (data/'rubric.json').write_text('{"custom": true}')
    isolated(tmp_path, """
import json
from tintprobe.context import ROOT, EVALUATION, evaluation_path, evaluation_output, project_resource
from tintprobe.evaluation_dependencies import dependencies
assert json.loads(evaluation_path('rubric.json').read_text())['custom']
assert evaluation_path('cases.json') == EVALUATION/'cases.json'
assert project_resource('evaluation/rubric.json') == ROOT/'tests/evaluation/rubric.json'
assert evaluation_output('results/comparison') == ROOT/'tests/evaluation/results/comparison'
deps = dependencies()
assert 'tests/evaluation/deps/codex' in deps
assert 'tests/evaluation/deps/tree-sitter-python' in deps
assert not (ROOT/'evaluation').exists()
""")


def test_compare_uses_custom_directory_for_default_output(tmp_path):
    import shutil
    import pytest
    if not shutil.which('nvim'):
        pytest.skip('Neovim is required for native capture')
    from tintprobe.context import EVALUATION
    (tmp_path/'tintprobe.json').write_text(json.dumps({'evaluation_dir': 'tests/evaluation'}))
    data = tmp_path/'tests/evaluation'
    data.mkdir(parents=True)
    (data/'themes.json').write_text(json.dumps([{'id': 'native-default', 'paths': [],
                                               'setup': "vim.cmd('colorscheme default')"}]))
    (data/'cases.json').write_text(json.dumps(json.loads((EVALUATION/'cases.json').read_text())[:1]))
    isolated(tmp_path, "import subprocess, sys; subprocess.run([sys.executable, '-m', 'tintprobe', 'compare'], check=True)")
    report = json.loads((data/'results/comparison/report.json').read_text())
    assert report['themes'][0]['captures'] == 14
    assert not (tmp_path/'evaluation').exists()
