from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Stage-specific native Codex readability gates, without a composite agent score."""
from tintprobe.codex_native import color
from tintprobe.context import wcag

ROLES={'request':'user request','commentary':'prose','approval':'approval prompt','test-failure':'tool error','patch-running':'tool status','patch-complete':'patch','test-success':'tool output','final':'prose and Python code'}

def assess(records,palette):
    from tintprobe.codex_flows import STAGES
    stages=[]
    for record in records:
        failures=[];ratios=[];dim=0
        for c in record['cells']:
            if not c['text'].strip():continue
            fg=color(c['fg'],palette,palette['foregrounds']['text']);bg=color(c['bg'],palette,palette['backgrounds']['base'])
            if 'REVERSED' in c['modifiers']:fg,bg=bg,fg
            value=wcag(fg,bg);ratios.append(value);dim+=('DIM' in c['modifiers'])
            if value<4.5:failures.append({'row':c['row'],'col':c['col'],'text':c['text'],'foreground':fg,'background':bg,'contrast':round(value,3)})
        # Locate required native content fragments, retaining cell coordinates.
        chars=[];refs=[]
        for c in record['cells']:
            for char in c['text']:
                if char.isspace():
                    if chars and chars[-1]!=' ':chars.append(' ');refs.append(c)
                else:chars.append(char);refs.append(c)
        blob=''.join(chars);focus=[]
        for fragment in STAGES.get(record['file'],[]):
            start=blob.find(fragment)
            if start<0:focus.append({'fragment':fragment,'status':'missing'});continue
            selected={(c['row'],c['col']):c for c in refs[start:start+len(fragment)] if c['text'].strip()}
            bad=[f for f in failures if (f['row'],f['col']) in selected]
            focus.append({'fragment':fragment,'status':'fail' if bad else 'pass','failures':bad,'cells':len(selected)})
        stages.append({'stage':record['file'],'role':ROLES.get(record['file'],'diff code'),'width':record['width'],'status':'fail' if failures or not ratios or any(f['status']!='pass' for f in focus) else 'pass','minimum_contrast':round(min(ratios),3) if ratios else None,'required_content':focus,'dim_cells_unverified':dim,'failures':failures})
    return {'status':'fail' if not stages or any(s['status']!='pass' for s in stages) else 'pass','stages':stages,'scope':'Whole native frames grouped by workflow stage, including accumulated history. Text contrast only; DIM, cursor, selection and native terminal appearance unverified. No overall agent score.'}
