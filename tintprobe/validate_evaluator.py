from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Native held-out mutation checks. Never modify the shipped palette."""
import argparse, hashlib, html, json, shutil
from pathlib import Path
from tintprobe.context import ROOT
from tintprobe.compare_themes import check_adapter, render
from tintprobe.evaluate_theme import capture
from tintprobe.evaluation_gates import evaluate_gates

VARIANTS={
 'baseline':('',None),
 'invisible-inline':("for _,g in ipairs({'DiffText','DiffTextAdd'}) do local h=vim.api.nvim_get_hl(0,{name=g,link=false});h.fg=h.bg;vim.api.nvim_set_hl(0,g,h) end",'text_contrast'),
 'merged-inline':("local h=vim.api.nvim_get_hl(0,{name='DiffChange',link=false});for _,g in ipairs({'DiffText','DiffTextAdd'}) do vim.api.nvim_set_hl(0,g,h) end",'critical_inline_background'),
 'alternate-hue':("for _,g in ipairs({'DiffText','DiffTextAdd'}) do vim.api.nvim_set_hl(0,g,{fg=0,bg=0xC09CCC}) end",None),
}

def verdict(gates, expected):
    failures=gates['failures']
    return any(f['gate']==expected for f in failures) if expected else not failures

def run(out):
    out.mkdir(parents=True,exist_ok=True)
    adapter=check_adapter(json.loads((evaluation_path('themes.json')).read_text())[0])
    rubric=json.loads((evaluation_path('rubric.json')).read_text());rubric['inline_oracles']={}
    cases=[]
    for name,token in [('boundary','='),('literal','_')]:
        after=evaluation_path('fixtures/holdout')/f'{name}.after.py'
        line=after.read_text().splitlines()[1]
        cases.append({'id':name,'before':f'fixtures/holdout/{name}.before.py','after':f'fixtures/holdout/{name}.after.py','filetype':'python'})
        rubric['inline_oracles'][name]=[{'side':'after','line':2,'byte':line.index(token)+1,'text':token}]
    results=[];gallery=[]
    for name,(override,expected) in VARIANTS.items():
        print('Validating '+name,flush=True)
        shots=[capture(c,w,'diff',shutil.which('nvim'),None,dict(adapter,evaluation_override=override)) for c in cases for w in (100,160)]
        gates=evaluate_gates(shots,rubric)
        checks=[{'case':s['case'],'width':s['width'],'pass':verdict(evaluate_gates([s],rubric),expected)} for s in shots]
        results.append({'variant':name,'expected_gate':expected,'pass':all(c['pass'] for c in checks),'checks':checks,'gates':gates})
        (out/(name+'.cells.json')).write_text(json.dumps(shots))
        gallery.extend('<details><summary>'+html.escape(name+' / '+s['case']+' / '+str(s['width']))+'</summary>'+render(s)+'</details>' for s in shots)
    report={'pass':all(r['pass'] for r in results),'results':results,'scope':'Native Neovim held-out fixtures; no palette optimization, no comfort or Ghostty claim. Positive controls must pass; each negative control must trigger its specific gate.','fixture_hashes':{str(p.relative_to(evaluation_path('fixtures/holdout'))):hashlib.sha256(p.read_bytes()).hexdigest() for p in (evaluation_path('fixtures/holdout')).glob('*.py')}}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:16px system-ui;padding:24px}pre{font:16pt "Berkeley Mono Medium",monospace}</style><h1>Evaluator validation</h1><p>'+report['scope']+'</p><p>Validation passed: '+str(report['pass'])+'</p><a href="report.json">Gate evidence</a>'+''.join(gallery))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raise SystemExit(0 if run(a.output)['pass'] else 1)
