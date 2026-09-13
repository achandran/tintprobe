from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Region-level failure evidence; no averaging can conceal a failed gate."""
from statistics import median
from tintprobe.evaluation_checks import effective_colors


def evaluate_gates(shots,rubric):
    from tintprobe.score_themes import distance,ratio
    evidence=[]; stats={'text_contrast':[],'inline_delta_e':[],'line_delta_e':[]}
    plain={(s['case'],s['width']):s for s in shots if s['state']=='diff'}
    for shot in shots:
        cells={(c['row'],c['col']):c for c in shot['cells']}
        regions=shot.get('regions',[])
        link=f'gallery.html#{shot["case"]}-{shot["width"]}-{shot["state"]}'
        def fail(gate,region=None,value=None):
            evidence.append({'gate':gate,'case':shot['case'],'width':shot['width'],'state':shot['state'],'region':region,'value':value,'evidence':link})
        if not regions:fail('source_regions_missing');continue
        for r in regions:
            c=cells.get((r['row'],r['col']))
            if not c:continue
            fg,bg=effective_colors(shot,c)
            if c['text'].strip():
                v=ratio(fg,bg);stats['text_contrast'].append(v)
                if v<rubric['text_contrast_target']:fail('text_contrast',r,round(v,3))
            if shot['state']=='diff' and r['group']=='DiffChange':
                stats['line_delta_e'].append(distance(bg,shot['defaults']['bg']))
        if shot['state']=='diff':
            for oracle in rubric['inline_oracles'].get(shot['case'],[]):
                matches=[r for r in regions if r.get('side')==oracle['side'] and r['source_line']==oracle['line'] and r['source_byte']==oracle['byte'] and r['text']==oracle['text']]
                if not matches:fail('required_edit_missing',oracle);continue
                for r in matches:
                    if r['group'] not in ('DiffText','DiffTextAdd'):fail('inline_emphasis_missing',r);continue
                    c=cells.get((r['row'],r['col']))
                    surrounding=[cells[(q['row'],q['col'])] for q in regions if q.get('side')==r.get('side') and q['source_line']==r['source_line'] and q['group']=='DiffChange' and (q['row'],q['col']) in cells]
                    if not c or not surrounding:fail('inline_context_missing',r);continue
                    bg=effective_colors(shot,c)[1]
                    delta=min(distance(bg,effective_colors(shot,q)[1]) for q in surrounding)
                    stats['inline_delta_e'].append(delta)
                    if delta<rubric['critical_inline_delta_e_min']:
                        cues=alternative_inline_cues(shot,r)
                        fail('inline_cue_review' if cues else 'critical_inline_background',r,{'delta_e':round(delta,3),'alternative_cues':cues})
        else:
            from tintprobe.overlay_checks import overlay_failures
            for error in overlay_failures(shot):
                fail(error['gate'],error.get('region'))
            baseline=plain.get((shot['case'],shot['width']))
            if baseline is None:fail('overlay_baseline_missing');continue
            basecells={(c['row'],c['col']):c for c in baseline['cells']}
            # Presence check only; not an exhaustive selected/search span oracle.
            changed=[]
            for r in regions:
                key=(r['row'],r['col']);a=cells.get(key);b=basecells.get(key)
                if a and b and a['text']==b['text'] and effective_colors(shot,a)!=effective_colors(baseline,b):changed.append(r)
            if not changed:fail('overlay_not_visible')
    distributions={k:{'count':len(v),'minimum':round(min(v),3) if v else None,'median':round(median(v),3) if v else None,'maximum':round(max(v),3) if v else None} for k,v in stats.items()}
    return {'status':'fails_current_checks' if evidence else 'meets_current_checks','failures':evidence,'distributions':distributions,'scope':'Critical inline oracles and source text; exact visible source overlay provenance and text contrast. Blank tail cells, cursor glyphs and perceptual cue effectiveness remain unverified.'}


def alternative_inline_cues(shot,region):
    """Report style cues for review, without claiming they are perceptually sufficient."""
    from tintprobe.score_themes import distance
    h=shot.get('highlights',{});a=h.get('DiffText',{});b=h.get('DiffChange',{})
    cues=[]
    if not region['text'].isspace():
        fg_a=a.get('fg',shot['defaults']['fg']);fg_b=b.get('fg',shot['defaults']['fg'])
        if distance(fg_a,fg_b)>=5:cues.append('foreground')
        for style in ('bold','italic'):
            if bool(a.get(style))!=bool(b.get(style)):cues.append(style)
    for style in ('underline','undercurl','underdouble','underdotted','underdashed','reverse','strikethrough'):
        if bool(a.get(style))!=bool(b.get(style)):cues.append(style)
    return cues
