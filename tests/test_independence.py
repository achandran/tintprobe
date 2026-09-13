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
