from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Compare original Neovim themes with identical fixtures; never recolor captures."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
from tintprobe.evaluate_theme import capture
from tintprobe.evaluation_checks import effective_colors, syntax_ready
from tintprobe.context import ROOT, wcag


def check_adapter(adapter):
    resolved=dict(adapter,paths=[(ROOT/p).resolve() for p in adapter['paths']])
    for path in resolved['paths']:
        if not path.is_dir():
            raise FileNotFoundError(f'Missing theme dependency: {path}; run tintprobe prepare --fetch for the pinned source')
    for path,pin in adapter.get('pins',{}).items():
        actual=subprocess.check_output(['git','-C',str(ROOT/path),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:raise ValueError(f'{path}: expected {pin}, found {actual}')
        if subprocess.check_output(['git','-C',str(ROOT/path),'status','--porcelain'],text=True).strip():
            raise ValueError(f'{path}: dependency has local changes')
    return resolved


def assess(shot):
    pairs={}; low=0; text_count=0
    for cell in shot['cells']:
        if not cell['text'].strip():continue
        fg,bg=effective_colors(shot,cell)
        contrast=wcag(f'#{fg:06x}',f'#{bg:06x}')
        pairs[f'{fg:06x}/{bg:06x}']=round(contrast,3)
        text_count+=1; low+=contrast<4.5
    errors=[]
    if shot.get('require_syntax') and not syntax_ready(shot):errors.append('Python syntax missing')
    # Measure backgrounds without imposing Ithilien's preferred hues or decorations.
    h=shot['highlights']; separation={}
    for first,second in [('DiffText','DiffChange'),('Search','DiffText'),('Visual','DiffText')]:
        def bg(name):
            g=h[name];return g.get('fg' if g.get('reverse') else 'bg',shot['defaults']['bg'])
        a,b=bg(first),bg(second)
        separation[first+'/'+second]=round(wcag(f'#{a:06x}',f'#{b:06x}'),3)
    return {'case':shot['case'],'width':shot['width'],'state':shot['state'],'errors':errors,'visible_nonspace_cells':text_count,'cells_below_4_5':low,'pair_contrasts':pairs,'background_contrast':separation}


def render(shot):
    rows={}
    for c in shot['cells']:
        fg,bg=effective_colors(shot,c);a=shot['attrs'].get(c['attr'],{})
        style=f'color:#{fg:06x};background:#{bg:06x};'
        for key,css in [('bold','font-weight:bold;'),('italic','font-style:italic;'),('underline','text-decoration:underline;')]:
            if a.get(key):style+=css
        rows.setdefault(c['row'],[]).append(f'<span style="{style}">{html.escape(c["text"])}</span>')
    return '<pre>'+'\n'.join(''.join(row) for row in rows.values())+'</pre>'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=evaluation_path('themes.json'))
    p.add_argument('--output',type=Path,default=ROOT/'evaluation/results/comparison')
    p.add_argument('--python-source',type=Path,help='Pinned tree-sitter-python checkout; enables Python Tree-sitter/LSP corpus')
    p.add_argument('--strict-gates',action='store_true',help='Fail if any theme fails the experimental gates')
    p.add_argument('--themes',nargs='+');p.add_argument('--nvim',default=shutil.which('nvim'))
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    adapters=json.loads(args.manifest.read_text())
    if args.themes:
        unknown=set(args.themes)-{a['id'] for a in adapters}
        if unknown:p.error('Unknown themes: '+', '.join(sorted(unknown)))
        adapters=[a for a in adapters if a['id'] in args.themes]
    runtime=None
    if args.python_source:
        from tintprobe.python_runtime import prepare
        runtime=prepare(args.python_source.resolve(),args.output/'runtime')
    cases=json.loads((evaluation_path('python-cases.json' if runtime else 'cases.json')).read_text()); reports=[];screens={};failed=False
    for adapter in adapters:
        print('Rendering '+adapter['id'],flush=True)
        resolved=check_adapter(adapter); shots=[]
        for case in cases:
            for width in (100,160):
                for state in ('diff','search','selection','selection-char','selection-block','selection-search','selection-search-diagnostic'):
                    shot=capture(case,width,state,args.nvim,None,resolved,runtime);shots.append(shot)
                    screens.setdefault((case['id'],width,state),[]).append((adapter['id'],shot))
        checks=[assess(s) for s in shots];failed|=any(c['errors'] for c in checks)
        reports.append({'theme':adapter,'captures':len(shots),'checks':checks})
        (args.output/(adapter['id']+'.cells.json')).write_text(json.dumps(shots,ensure_ascii=False))
    report={'tintprobe_version':__import__('tintprobe').__version__,'render_profile':json.loads((evaluation_path('render-profile.json')).read_text()),'mode':'original-theme','nvim':subprocess.check_output([args.nvim,'--version'],text=True).splitlines()[0],
        'corpus_sha256':hashlib.sha256(json.dumps(cases,sort_keys=True).encode()+b''.join(evaluation_path(c[s]).read_bytes() for c in cases for s in ('before','after'))).hexdigest(),
        'themes':reports,'coverage':{'neovim':'Tree-sitter and BasedPyright' if runtime else 'builtin syntax, initial viewport','codex':'not run by comparison runner','ghostty':'not requested; native desktop capture is separate','treesitter_lsp':json.loads((evaluation_path('python-runtime.json')).read_text()) if runtime else 'not run','comfort':'unverified'},
        'interpretation':'Contrast flags are observations, not a theme ranking. Background contrast does not measure hue separation. Browser cell reconstructions are not terminal screenshots.'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    blocks=[]
    for (case,width,state),entries in screens.items():
        blocks.append(f'<details id="{case}-{width}-{state}"><summary>{html.escape(case)} / {width} / {state}</summary>'+''.join('<h3>'+html.escape(name)+'</h3>'+render(shot) for name,shot in entries)+'</details>')
    (args.output/'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>Theme comparison</title><style>body{background:#eee;font:16px sans-serif;padding:20px}pre{font:16pt/1.4 "Berkeley Mono Medium",monospace;overflow:auto}summary{padding:12px;cursor:pointer}details{border-bottom:1px solid #aaa}</style><h1>Original theme comparison</h1><p>Identical native Neovim cells. Expand a fixture to compare themes. Uses each adapter as declared; no implicit theme-specific overrides. Contrast observations and coverage gaps are in report.json.</p>'+''.join(blocks)+'<script>function reveal(){const e=document.getElementById(location.hash.slice(1));if(e)e.open=true;}addEventListener("hashchange",reveal);reveal();</script>')
    from tintprobe.score_themes import write_scorecard
    scored=write_scorecard(args.output,report)
    from tintprobe.audit_failures import main as audit_failures
    audit_failures(args.output)
    failed |= any(s['diff']['oracle_failures'] for s in scored)
    if args.strict_gates: failed |= any(s['gates']['failures'] for s in scored)
    print(f'{sum(r["captures"] for r in reports)} captures; report: {args.output}')
    return int(failed)
if __name__=='__main__':raise SystemExit(main())
