from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Experimental evidence-backed scores; unavailable axes never become zero or passes."""
from coloraide import Color
import html
import json
from pathlib import Path
from statistics import mean
from tintprobe.evaluation_checks import effective_colors
from tintprobe.context import ROOT, wcag


def ratio(a,b):return wcag(f'#{a:06x}',f'#{b:06x}')


def distance(a,b):return Color(f"#{a:06x}").delta_e(Color(f"#{b:06x}"),method="2000")

def score(shots,rubric):
    observations=[]; failures=[]
    for shot in shots:
        if shot['state']!='diff':continue
        cells={(c['row'],c['col']):c for c in shot['cells']}
        regions=shot.get('regions',[]);text=[];inline=[];line=[]
        changed_bgs=[]
        for r in regions:
            c=cells.get((r['row'],r['col']))
            if c and r['group']=='DiffChange':changed_bgs.append(effective_colors(shot,c)[1])
        for r in regions:
            c=cells.get((r['row'],r['col']))
            if c is None:continue
            fg,bg=effective_colors(shot,c)
            if c['text'].strip():text.append(min(1,ratio(fg,bg)/rubric['text_contrast_target']))
            if r['group'] in ('DiffText','DiffTextAdd') and changed_bgs:
                separation=min(distance(bg,b) for b in set(changed_bgs))
                inline.append(min(1,max(0,separation/rubric['inline_delta_e_target'])))
            elif r['group']=='DiffChange':
                separation=distance(bg,shot['defaults']['bg'])
                line.append(min(1,max(0,separation/rubric['line_delta_e_target'])))
        for expected in rubric['inline_oracles'].get(shot['case'],[]):
            matches=[r for r in regions if r.get('side')==expected['side'] and r['source_line']==expected['line'] and r['source_byte']==expected['byte'] and r['text']==expected['text'] and r['group'] in ('DiffText','DiffTextAdd')]
            if not matches:failures.append({'case':shot['case'],'width':shot['width'],'expected_inline_cell':expected})
        observations.append({'case':shot['case'],'width':shot['width'],'evidence':f'gallery.html#{shot["case"]}-{shot["width"]}-diff','text_readability':mean(text)*100 if text else None,'inline_distinction':mean(inline)*100 if inline else None,'line_distinction':mean(line)*100 if line else None,'source_cells':len(regions)})
    components={k:round(mean(o[k] for o in observations if o[k] is not None),2) if any(o[k] is not None for o in observations) else None for k in rubric['weights']}
    total=round(sum(components[k]*w for k,w in rubric['weights'].items()),1) if all(v is not None for v in components.values()) and not failures else None
    return {'diff':{'status':'provisional' if total is not None else 'incomplete_or_failed','score':total,'components':components,'coverage':'Neovim plain diff only; overlays, terminal rendering and agent diffs unscored','oracle_failures':failures,'observations':observations},'agents':{'score':None,'status':'not_evaluated','codex':'not evaluated in cross-theme comparison','claude_code':'not evaluated'},'long_session':{'score':None,'status':'not_evaluated','readability_indicator':components['text_readability'],'reason':'Diff-screen contrast is not evidence of long-session comfort'}}


def write_scorecard(output,report):
    rubric=json.loads((evaluation_path('rubric.json')).read_text());results=[]
    for theme in report['themes']:
        name=theme['theme']['id'];shots=json.loads((output/(name+'.cells.json')).read_text())
        from tintprobe.evaluation_gates import evaluate_gates
        result={'theme':name,**score(shots,rubric),'gates':evaluate_gates(shots,rubric)}
        if not rubric.get('legacy_weighted_score', False):
            result['diff']['score']=None
            result['diff']['status']='measurements_only'
        results.append(result)
    (output/'scorecard.json').write_text(json.dumps({'rubric':rubric,'results':results},indent=2))
    rows=[];details=[]
    for item in results:
        name=html.escape(item['theme']);d=item['diff'];value='Not scored' if d['score'] is None else f'{d["score"]:.1f}/100 (provisional)'
        g=item['gates'];dist=g['distributions']
        rows.append(f'<tr><td>{name}</td><td>{g["status"]}</td><td>{dist["text_contrast"]["minimum"]}</td><td>{dist["inline_delta_e"]["minimum"]}</td><td>{dist["line_delta_e"]["minimum"]}</td><td>Not evaluated</td></tr>')
        failures=''.join('<li><a href="'+f['evidence']+'">'+html.escape(f['case']+' / '+f['state']+' / '+f['gate'])+'</a> '+html.escape(str(f['value']))+'</li>' for f in g['failures'])
        details.append(f'<details><summary>{name}: {len(g["failures"])} cell-level findings</summary><p>{g["scope"]}</p><pre>{html.escape(json.dumps(dist,indent=2))}</pre><ul>{failures}</ul></details>')
        evidence=''.join(f'<li><a href="{o["evidence"]}">{html.escape(o["case"])} / {o["width"]}</a>: '+html.escape(str({k:o[k] for k in rubric['weights']}))+'</li>' for o in d['observations'])
        details.append(f'<details><summary>{name}: components and evidence</summary><pre>{html.escape(json.dumps(d["components"],indent=2))}</pre><ul>{evidence}</ul><p>Inline oracle failures: {len(d["oracle_failures"])}</p></details>')
    (output/'scorecard.html').write_text('<!doctype html><meta charset="utf-8"><title>Theme scorecard</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:20px}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccc}summary{cursor:pointer;margin-top:20px}</style><h1>Theme comparison scorecard</h1><p>Experimental rubric '+rubric['version']+'. Gate thresholds are experimental, not validated measures of excellence. There is no headline ranking. Native Neovim only. Missing axes are not zero and are not included in an overall score.</p><table><tr><th>Theme</th><th>Current gates</th><th>Worst text contrast</th><th>Worst critical inline ΔE</th><th>Worst line ΔE</th><th>Agents / comfort</th></tr>'+''.join(rows)+'</table><p>A weighted total is disabled by default. Projects may explicitly opt into the legacy diagnostic, which is not a ranking. Minimum, median and maximum measurements and individual findings appear below. CIEDE2000 background distances omit typography; inspect evidence before drawing conclusions.</p>'+''.join(details))
    return results

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('--strict-gates',action='store_true');a=p.parse_args()
    results=write_scorecard(a.results,json.loads((a.results/'report.json').read_text()))
    if a.strict_gates: raise SystemExit(int(any(r['gates']['failures'] for r in results)))
