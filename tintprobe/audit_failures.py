from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Summarize representative native-cell failures with exact styles and source context."""
import json,html,argparse
from collections import Counter
from pathlib import Path
from tintprobe.evaluation_gates import evaluate_gates
from tintprobe.evaluation_checks import effective_colors
from tintprobe.context import ROOT


def main(output):
    rubric=json.loads((evaluation_path('rubric.json')).read_text());report=json.loads((output/'report.json').read_text())
    records=[];blocks=[]
    for entry in report['themes']:
        name=entry['theme']['id'];shots=json.loads((output/(name+'.cells.json')).read_text());index={(s['case'],s['width'],s['state']):s for s in shots}
        gates=evaluate_gates(shots,rubric);groups={}
        for failure in gates['failures']:
            shot=index[failure['case'],failure['width'],failure['state']];r=failure['region'] or {};cell=next((c for c in shot['cells'] if (c['row'],c['col'])==(r.get('row'),r.get('col'))),None)
            fg,bg=effective_colors(shot,cell) if cell else (0,0xffffff)
            attrs=shot['attrs'].get(str(cell['attr']),{}) if cell else {}
            key=(failure['gate'],fg,bg,str(attrs))
            if key not in groups:
                line=[c for c in shot['cells'] if c['row']==r.get('row')]
                groups[key]={'count':0,'example':failure,'foreground':f'#{fg:06X}','background':f'#{bg:06X}','attributes':attrs,'context':line,'shot':shot}
            groups[key]['count']+=1
        ordered=sorted(groups.values(),key=lambda x:-x['count']);samples=[];rows=[]
        for g in ordered[:8]:
            shot=g.pop('shot');line=g.pop('context');samples.append(g)
            spans=[]
            for c in line:
                fg,bg=effective_colors(shot,c);a=shot['attrs'].get(str(c['attr']),{});style=f'color:#{fg:06x};background:#{bg:06x};'
                if a.get('bold'):style+='font-weight:bold;'
                if a.get('italic'):style+='font-style:italic;'
                if a.get('underline'):style+='text-decoration:underline;'
                spans.append(f'<span style="{style}">{html.escape(c["text"])}</span>')
            f=g['example'];rows.append('<h3>'+html.escape(f['gate'])+'</h3><p>'+html.escape(f'{g["count"]} repeated cells; {g["foreground"]} on {g["background"]}; measurement {f["value"]}')+'</p><pre>'+''.join(spans)+'</pre><a href="'+f['evidence']+'">Full fixture</a>')
        records.append({'theme':name,'counts':dict(Counter(f['gate'] for f in gates['failures'])),'representative_pairs':samples})
        blocks.append('<h2>'+html.escape(name)+'</h2>'+(''.join(rows) or '<p>No current gate failures.</p>'))
    (output/'failure-audit.json').write_text(json.dumps(records,indent=2))
    (output/'failure-audit.html').write_text('<!doctype html><meta charset="utf-8"><title>Failure audit</title><style>body{font:16px/1.5 system-ui;padding:30px}pre{font:16pt/1.4 "Berkeley Mono Medium",monospace;overflow:auto}</style><h1>Representative failure audit</h1><p>Actual native cell colors; not a Ghostty screenshot. Berkeley Mono Medium, 16 pt requested; browser font fallback is not verified. Counts repeat across widths and states and do not count unique defects. Up to eight frequent style pairs per theme.</p>'+''.join(blocks))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args();main(a.results)
