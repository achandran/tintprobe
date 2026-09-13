from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Opt-in reference fidelity. Experimental, independent of readability gates."""
import json
import math
from tintprobe.context import ROOT, Color
from tintprobe.codex_native import color


def band(value, spec):
    low, high, falloff = spec
    return max(0., 1. - max(low-value, value-high, 0.)/falloff)


def lch(value):
    return [0. if math.isnan(v) else v for v in Color(value).convert('lab').convert('lch').coords()]


def evaluate(entry, palette, records):
    profile_id = entry.get('aesthetic_profile')
    if not profile_id:
        return {'status':'not_applicable','score':None}
    # Never interpret a manifest value as a filesystem path.
    if profile_id != 'formex-reef-gmt-white-steel':
        return {'status':'unavailable','score':None,'reason':'Unknown aesthetic profile'}
    profile=json.loads((evaluation_path('aesthetic-profiles')/f'{profile_id}.json').read_text())
    result={'profile':profile,'status':'experimental','score':None,'components':{},
            'limitations':['Uncalibrated design targets; reference images not yet visually verified.',
                            'Cell usage is measured only in request frames, not pixel area or all applications.',
                            'Does not measure comfort or override readability gates.']}
    ranges=profile['ranges']
    try:
        bg=palette['backgrounds'];fg=palette['foregrounds']
        dial=lch(bg['base']);text=lch(fg['text'])
        steel=[lch(bg[k]) for k in ('base','mantle','crust')]
        red=lch(palette['accents']['coral'])
    except (KeyError,ValueError) as exc:
        result.update(status='unavailable',reason=f'Missing/invalid semantic roles: {exc}')
        return result
    scores={'dial':min(band(dial[0],ranges['dial_lightness']),band(dial[1],ranges['neutral_chroma'])),
            'steel':min(*(band(c[1],ranges['neutral_chroma']) for c in steel),
                        *(band(steel[i][0]-steel[i+1][0],ranges['steel_gap']) for i in range(2))),
            'markings':min(band(text[0],ranges['text_lightness']),band(text[1],ranges['neutral_chroma']))}
    usage=[]
    for record in records:
        if record.get('file')!='request':continue
        cells=record.get('cells',[])
        if not cells:continue
        reds=neutrals=0
        for cell in cells:
            foreground=color(cell['fg'],palette,fg['text']);background=color(cell['bg'],palette,bg['base'])
            if 'REVERSED' in cell.get('modifiers',''):foreground,background=background,foreground
            samples=[background]+([foreground] if cell.get('text','').strip() else [])
            values=[lch(c) for c in samples]
            reds+=any(15<=v[2]<=40 and v[1]>=25 for v in values)
            neutrals+=all(v[1]<=8 for v in values)
        usage.append({'width':record['width'],'red_fraction':reds/len(cells),'neutral_fraction':neutrals/len(cells)})
    result['measurements']={'dial_lch':dial,'steel_lch':steel,'text_lch':text,'red_lch':red,'request_usage':usage}
    if usage:
        scores['red']=min(band(red[2],ranges['red_hue']),band(red[1],ranges['red_chroma']),*(band(u['red_fraction'],ranges['red_usage']) if u['red_fraction'] else 0 for u in usage))
        scores['restraint']=min(band(u['neutral_fraction'],ranges['neutral_usage']) for u in usage)
    for key,value in scores.items():result['components'][key]={'score':round(value*100,1),'weight':profile['weights'][key]}
    if len(scores)==5:result['score']=round(sum(scores[k]*profile['weights'][k] for k in scores),1)
    else:result.update(status='incomplete',reason='No request-frame usage evidence; no total awarded')
    return result
