from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Deterministic native interaction fixtures and offline acceptance gates."""
from collections import Counter
import hashlib
import math

CURSOR_CODES={'blinking-block':1,'steady-block':2,'blinking-underline':3,
              'steady-underline':4,'blinking-bar':5,'steady-bar':6,'hidden':2}


def fixtures(output):
    records=[]
    for style in CURSOR_CODES:
        name='cursor-block' if style=='steady-block' else 'cursor-'+style
        text='return attempt <= 3\n'
        cursor={'row':0,'column':text.index('='),'text':'=','style':style}
        records.append(_record(output,name,text,cursor=cursor))
    text='return attempt <= 3\n'
    records.append(_record(output,'cursor-transitions',text,
        cursor={'row':0,'column':text.index('='),'text':'=','style':'steady-bar'},
        transitions=['steady-bar','steady-block','steady-underline','hidden','steady-block']))
    records.append(_record(output,'cursor-inactive-block',text,
        cursor={'row':0,'column':text.index('='),'text':'=','style':'steady-block'},inactive=True))
    for name,text,start,end in (
        ('selection-single','return \x1b[34mattempt\x1b[0m <= 3\n',[0,7],[0,18]),
        ('selection-multiline','return attempt <= 3\nreturn retries >= 2\n',[0,7],[1,14]),
    ):
        records.append(_record(output,name,text,selection={'start':start,'end':end}))
    return records


def _record(output,name,text,**state):
    (output/(name+'.ansi')).write_text(text)
    return {'id':name,'kind':'interaction','status':'prepared','ansi':name+'.ansi',
            'sha256':hashlib.sha256(text.encode()).hexdigest(),'contains_ansi':'\x1b[' in text,**state}


def selected(spec,row,column):
    return tuple(spec['start']) <= (row,column) < tuple(spec['end'])


def inactive_check(image,g,cell,palette,reference):
    from tintprobe.ghostty_quality import rgb,cell_checks
    from tintprobe.ghostty_glyphs import crop_cell,mask,classify,templates_from_capture
    crop=crop_cell(image,g,cell['row'],cell['column'])
    w,h=crop.size;target=rgb(palette['highlight']['cursor'])
    points=[(x,y) for y in range(h) for x in range(w)
            if max(abs(a-b) for a,b in zip(crop.getpixel((x,y)),target))<=3]
    perimeter=[(x,y) for x,y in points if x<2 or x>=w-2 or y<2 or y>=h-2]
    outline=bool(points) and len(perimeter)>=len(points)*.9 and len({x for x,y in points})>=w*.8 and len({y for x,y in points})>=h*.8
    clean=crop.copy()
    for x,y in points:clean.putpixel((x,y),rgb(palette['backgrounds']['base']))
    pixels=cell_checks(image,g,[cell],palette['backgrounds']['base'])
    result={'status':'pass' if outline and pixels['status']=='pass' else 'fail','shape':'inactive-outline','outline_pass':outline,'pixels':pixels}
    if reference and (g['cell_width'],g['cell_height'])==(reference[1]['cell_width'],reference[1]['cell_height']):
        glyph,distance=classify(mask(clean),templates_from_capture(*reference))
        result.update(observed_glyph=glyph,glyph_distance=distance)
        if result['status']=='pass' and glyph!=cell['text']:result['status']='unverified'
    elif result['status']=='pass':result['status']='unverified'
    return result


def drag_points(geometry,size,spec):
    """Image fractions, converted by the helper to global window points (Retina safe).

    Begin in the leading half of the first cell; end in the trailing half of the
    last cell. The expected range is half-open and is never inferred from pixels.
    """
    points=[]
    for (row,col),offset in ((spec['start'],.15),(spec['end'], -.15)):
        x=geometry['x']+(col+offset)*geometry['cell_width']
        y=geometry['y']+(row+2.5)*geometry['cell_height']
        if not 0<x<size[0] or not 0<y<size[1]:raise ValueError('Selection target outside captured window')
        points.extend((x/size[0],y/size[1]))
    return points


def shape_check(image,g,cell,palette,style,reference):
    from tintprobe.ghostty_quality import rgb,cell_checks,cursor_check
    from tintprobe.ghostty_glyphs import crop_cell,mask,classify,templates_from_capture
    if style.endswith('block'):
        return cursor_check(image,g,cell,palette,reference)
    crop=crop_cell(image,g,cell['row'],cell['column']).convert('RGB')
    w,h=crop.size;target=rgb(palette['highlight']['cursor'])
    x0=round(g['x']+cell['column']*g['cell_width']);y0=g['y']+(cell['row']+2)*h
    # Native Ghostty can rasterize its one-pixel bar just left of the cell.
    # Include exactly that boundary pixel, also when testing the hidden phase.
    points=[(x,y) for y in range(h) for x in range(-1 if x0>0 else 0,w)
            if max(abs(a-b) for a,b in zip(image.getpixel((x0+x,y0+y)),target))<=3]
    shape='hidden' if style=='hidden' else style.split('-')[-1]
    good=not points if shape=='hidden' else False
    if points:
        xs=[x for x,y in points];ys=[y for x,y in points]
        if shape=='bar':
            good=max(xs)<max(2,math.ceil(w*.3)) and len(set(ys))>=h*.8 and len(points)>=h
        elif shape=='underline':
            good=min(ys)>=h*.7 and len(set(xs))>=w*.8 and len(points)>=w
    # Remove only the independently located cursor-colored strokes for glyph
    # classification. All pixels (including the cursor) still face color checks.
    clean=image.copy()
    for x,y in points:clean.putpixel((x0+x,y0+y),rgb(palette['backgrounds']['base']))
    pixels=cell_checks(image,g,[cell],palette['backgrounds']['base'])
    result={'status':'pass' if good and pixels['status']=='pass' else 'fail',
            'shape':shape,'shape_pass':good,'cursor_pixels':len(points),'pixels':pixels}
    if not reference or (reference[1]['cell_width'],reference[1]['cell_height'])!=(g['cell_width'],g['cell_height']):
        if result['status']=='pass':result['status']='unverified'
        result['reason']='Missing or incompatible native glyph reference'
    else:
        glyph,distance=classify(mask(crop_cell(clean,g,cell['row'],cell['column'])),templates_from_capture(*reference))
        result.update(observed_glyph=glyph,glyph_distance=distance)
        if result['status']=='pass' and glyph!=cell['text']:result['status']='unverified'
    return result


def selection_check(image,g,cells,lines,palette,spec,reference):
    from tintprobe.ghostty_quality import rgb,cell_checks
    from tintprobe.ghostty_glyphs import crop_cell,mask,classify,templates_from_capture
    bg=palette['highlight']['background'];fg=palette['highlight']['foreground']
    findings=[];chosen=[]
    # Check spaces and trailing blanks as well: a whole-line paint must not pass
    # for a substring drag. Multiline selection includes the first row's tail.
    for row,line in enumerate(lines):
        for col in range(120):
            wanted=selected(spec,row,col)
            expected=bg if wanted else palette['backgrounds']['base']
            crop=crop_cell(image,g,row,col)
            if crop.size!=(round(g['cell_width']),g['cell_height']):
                findings.append({'row':row,'column':col,'reason':'clipped'});continue
            modal=Counter(zip(*[iter(crop.convert('RGB').tobytes())]*3)).most_common(1)[0][0]
            if max(abs(a-b) for a,b in zip(modal,rgb(expected)))>3:
                findings.append({'row':row,'column':col,'reason':'selection extent or fill mismatch'})
    chosen=[dict(c,fg=fg) for c in cells if selected(spec,c['row'],c['column'])]
    pixels=cell_checks(image,g,chosen,bg)
    result={'status':'fail' if findings or pixels['status']=='fail' or not chosen else 'pass',
            'extent_findings':findings,'pixels':pixels,'selected_cells':len(chosen)}
    if not reference:
        if result['status']=='pass':result['status']='unverified'
        result['reason']='Native glyph reference missing'
    else:
        templates=templates_from_capture(*reference);misses=[]
        if (g['cell_width'],g['cell_height'])!=(reference[1]['cell_width'],reference[1]['cell_height']):
            result.update(status='fail' if result['status']=='fail' else 'unverified',reason='Reference geometry differs')
            return result
        for c in chosen:
            if c['text']==' ':continue
            glyph,distance=classify(mask(crop_cell(image,g,c['row'],c['column'])),templates)
            if glyph!=c['text']:misses.append({**c,'observed':glyph,'distance':distance})
        result['glyph_mismatches']=misses
        if result['status']=='pass' and misses:result['status']='unverified'
    return result


def blink_gate(states):
    """Do not pass a blinking request based on a lucky single on-phase frame."""
    on=states.count('on');off=states.count('off')
    transitions=sum(a!=b for a,b in zip(states,states[1:]) if a in ('on','off') and b in ('on','off'))
    return {'status':'pass' if len(states)>=8 and on>=2 and off>=2 and transitions>=2 and all(s in ('on','off') for s in states) else 'unverified',
            'states':states,'on_frames':on,'off_frames':off,'transitions':transitions}
