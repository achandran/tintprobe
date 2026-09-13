from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Build and verify pinned Python parser assets for native evaluation."""
import hashlib,json,shutil,subprocess
from pathlib import Path
from tintprobe.context import ROOT

def prepare(source,output):
    spec=json.loads((evaluation_path('python-runtime.json')).read_text())
    from importlib.metadata import version
    if version('basedpyright')!=spec['language_server_version']:raise ValueError('BasedPyright version mismatch')
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if actual!=spec['tree_sitter_revision']:raise ValueError('Python parser revision mismatch')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():raise ValueError('Python parser checkout is modified')
    (output/'parser').mkdir(parents=True,exist_ok=True);(output/'queries/python').mkdir(parents=True,exist_ok=True)
    subprocess.run(['cc','-shared','-fPIC','-O2','-I',str(source/'src'),str(source/'src/parser.c'),str(source/'src/scanner.c'),'-o',str(output/'parser/python.so')],check=True)
    shutil.copy2(source/'queries/highlights.scm',output/'queries/python/highlights.scm')
    return str(output.resolve())
