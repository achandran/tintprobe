from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Replay deterministic upstream ChatWidget events; no model calls or commands run."""
import argparse,json,os,subprocess,hashlib
from pathlib import Path
from tintprobe.context import ROOT,load_palette,wcag
from tintprobe.codex_native import color,write_gallery

STAGES={
    'request':['Fix the Python retry limit'],
    'commentary':['I will inspect','worker.py'],
    'approval':['Would you like to run','python -m pytest','Yes, proceed'],
    'test-failure':['FAILED test_retry_limit','AssertionError'],
    'patch-running':['Working'],
    'patch-complete':['Edited worker.py','return 2','return 3'],
    'test-success':['1 passed'],
    'final':['Updated the retry limit.','Validation:','return 3'],
}

def validate_records(records):
    expected={(stage,width) for stage in STAGES for width in (60,100)}
    if len(records)!=len(expected) or {(r['file'],r['width']) for r in records}!=expected:raise ValueError('Missing or duplicate flow stages')
    for r in records:
        text=' '.join(''.join(c['text'] for c in r['cells']).split())
        for fragment in STAGES[r['file']]:
            if fragment not in text:raise ValueError(f'Missing {fragment!r} in {r["file"]}')


def run(source,output,theme=None,palette=None):
    theme=theme or port_path('codex_theme')
    pin=json.loads((evaluation_path('sources.json')).read_text())['codex']['revision']
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('Codex revision mismatch')
    target=source/'codex-rs/tui/src/chatwidget/tests.rs';original=target.read_bytes()
    if original!=subprocess.check_output(['git','-C',str(source),'show','HEAD:codex-rs/tui/src/chatwidget/tests.rs']):raise ValueError('Refusing to modify dirty Codex test source')
    output.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,ITHILIEN_CODEX_THEME=str(theme),ITHILIEN_ROOT=str(ROOT),TINTPROBE_FIXTURES=str(EVALUATION/"fixtures"),ITHILIEN_CODEX_OUTPUT=str((output/'codex-cells.json').resolve()))
    try:
        target.write_bytes(original+('\ninclude!('+json.dumps(str(evaluation_path('codex_flow_adapter.rs')))+');\n').encode())
        with (output/'native.log').open('w') as log:
            result=subprocess.run(['cargo','test','--locked','-p','codex-tui','--lib','ithilien_complete_flow_cells','--','--test-threads=1'],cwd=source/'codex-rs',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        if result.returncode:raise RuntimeError('Native flow test failed; inspect '+str(output/'native.log'))
    finally:target.write_bytes(original)
    records=json.loads((output/'codex-cells.json').read_text());validate_records(records);palette=palette or load_palette();findings=[]
    for r in records:
        for c in r['cells']:
            if not c['text'].strip():continue
            fg=color(c['fg'],palette,palette['foregrounds']['text']);bg=color(c['bg'],palette,palette['backgrounds']['base'])
            if 'REVERSED' in c['modifiers']:fg,bg=bg,fg
            contrast=wcag(fg,bg)
            if contrast<4.5:findings.append({'stage':r['file'],'width':r['width'],'text':c['text'],'contrast':round(contrast,3)})
    write_gallery(records,output,palette)
    gallery=output/'codex-gallery.html'
    gallery.write_text(gallery.read_text().replace('Native Codex diff renderer','Native Codex workflow replay'))
    report={'status':'fail' if findings else 'pass','captures':len(records),'source_revision':pin,'theme_sha256':hashlib.sha256(theme.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256((evaluation_path('codex_flow_adapter.rs')).read_bytes()).hexdigest(),'findings':findings,'scope':'Deterministic native ChatWidget event replay with accumulated history; not a live app-server, model session or terminal screenshot. Colors are native; DIM and terminal-specific appearance unverified.'}
    (output/'report.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'evaluation/results/codex-flows');a=p.parse_args()
    print(json.dumps(run(a.source.resolve(),a.output.resolve()),indent=2))
