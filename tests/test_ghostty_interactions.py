from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image,ImageDraw,ImageFont
from tintprobe.ghostty_interactions import shape_check,selection_check,blink_gate,drag_points,fixtures,CURSOR_CODES
from tintprobe.ghostty_quality import ansi_cells
from test_ghostty_native_cursor import specimen


def test_inactive_outline_requires_outline_and_intact_glyph():
    from tintprobe.ghostty_interactions import inactive_check
    im,g,p,ref,cell=specimen();draw=ImageDraw.Draw(im)
    draw.rectangle((0,48,11,71),fill=p['backgrounds']['base'],outline=p['highlight']['cursor'])
    draw.text((0,48),'=',font=ImageFont.load_default_imagefont(),fill='black')
    assert inactive_check(im,g,cell,p,ref)['status']=='pass'
    draw.rectangle((0,48,11,71),fill=p['highlight']['cursor'])
    draw.text((0,48),'=',font=ImageFont.load_default_imagefont(),fill='black')
    assert inactive_check(im,g,cell,p,ref)['status']=='fail'
    draw.rectangle((0,48,11,71),fill=p['backgrounds']['base'],outline=p['highlight']['cursor'])
    assert inactive_check(im,g,cell,p,ref)['status']!='pass'


def shape(style):
    im,g,p,ref,cell=specimen();d=ImageDraw.Draw(im)
    shifted=Image.new('RGB',ref[0].size,p['backgrounds']['base']);shifted.paste(ref[0],(2,0));ref=(shifted,g)
    d.rectangle((0,48,11,71),fill=p['backgrounds']['base'])
    d.text((2,48),'=',font=ImageFont.load_default_imagefont(),fill='black')
    if style=='bar':d.rectangle((0,48,1,71),fill=p['highlight']['cursor'])
    if style=='underline':d.rectangle((0,70,11,71),fill=p['highlight']['cursor'])
    return im,g,p,ref,cell


def test_shapes_reject_missing_wrong_position_and_block():
    for style in ('bar','underline','hidden'):
        im,g,p,ref,cell=shape(style)
        assert shape_check(im,g,cell,p,'steady-'+style if style!='hidden' else style,ref)['status']=='pass'
        for wrong in ('bar','underline','hidden'):
            if wrong==style:continue
            bad=shape(wrong)[0]
            assert shape_check(bad,g,cell,p,'steady-'+style if style!='hidden' else style,ref)['status']!='pass'
        if style!='hidden':
            bad=specimen()[0]
            assert shape_check(bad,g,cell,p,'steady-'+style,ref)['status']=='fail'
            bad=shape('hidden')[0];d=ImageDraw.Draw(bad)
            d.rectangle((6,55,7,65),fill=p['highlight']['cursor'])
            assert shape_check(bad,g,cell,p,'steady-'+style,ref)['status']=='fail'


def selection_fixture():
    _,g,p,ref,_=specimen();text='a <= b\nc >= d\n';cells,lines=ansi_cells(text,p)
    spec={'start':[0,2],'end':[1,4]}
    im=Image.new('RGB',(1440,120),p['backgrounds']['base']);d=ImageDraw.Draw(im)
    from tintprobe.ghostty_interactions import selected
    for row in range(3):
        for col in range(120):
            if selected(spec,row,col):d.rectangle((col*12,(row+2)*24,col*12+11,(row+3)*24-1),fill=p['highlight']['background'])
    for c in cells:d.text((c['column']*12,(c['row']+2)*24),c['text'],font=ImageFont.load_default_imagefont(),fill='black')
    return im,g,p,ref,cells,lines,spec


def test_native_bar_at_left_boundary_is_visible_and_still_requires_glyph():
    im,g,p,ref,cell=shape('hidden')
    def padded(source):
        result=Image.new('RGB',(source.width+12,source.height),p['backgrounds']['base'])
        result.paste(source,(12,0))
        return result
    im=padded(im);g=dict(g,x=12);ref=(padded(ref[0]),g)
    d=ImageDraw.Draw(im);d.line((11,48,11,71),fill=p['highlight']['cursor'])
    assert shape_check(im,g,cell,p,'steady-bar',ref)['status']=='pass'
    assert shape_check(im,g,cell,p,'hidden',ref)['status']=='fail'
    # A bar a further pixel away cannot satisfy the narrow boundary allowance.
    bad=im.copy();draw=ImageDraw.Draw(bad)
    draw.line((11,48,11,71),fill=p['backgrounds']['base'])
    draw.line((10,48,10,71),fill=p['highlight']['cursor'])
    assert shape_check(bad,g,cell,p,'steady-bar',ref)['status']=='fail'
    # The boundary allowance must not rescue an erased equals sign.
    d.rectangle((12,48,23,71),fill=p['backgrounds']['base'])
    assert shape_check(im,g,cell,p,'steady-bar',ref)['status']!='pass'


def test_selection_extent_fill_and_operator_are_independent_gates():
    im,g,p,ref,cells,lines,spec=selection_fixture()
    check=lambda img:selection_check(img,g,cells,lines,p,spec,ref)
    assert check(im)['status']=='pass'
    for kind in ('missing','overselect','erase-equals','wrong-color','white-text'):
        bad=im.copy();d=ImageDraw.Draw(bad)
        if kind=='missing':d.rectangle((24,48,35,71),fill=p['backgrounds']['base'])
        elif kind=='overselect':d.rectangle((0,48,11,71),fill=p['highlight']['background'])
        elif kind=='wrong-color':d.rectangle((24,48,35,71),fill='#C9CECB')
        else:
            d.rectangle((36,48,47,71),fill=p['highlight']['background'])
            if kind=='white-text':d.text((36,48),'=',font=ImageFont.load_default_imagefont(),fill='white')
        assert check(bad)['status']!='pass',kind
    assert selection_check(im,g,cells,lines,p,spec,None)['status']=='unverified'


def test_blink_requires_repeated_on_off_and_rejects_unknown_or_static():
    assert blink_gate(['on']*3+['off']*3+['on']*3)['status']=='pass'
    for states in (['on']*16,['off']*16,['on']*8+['off']*8,['unknown']*16,['on','off']):
        assert blink_gate(states)['status']!='pass'


def test_fixtures_and_retina_coordinates_are_explicit(tmp_path):
    rows=fixtures(tmp_path)
    assert {r['cursor']['style'] for r in rows if 'cursor' in r}==set(CURSOR_CODES)
    spec={'start':[0,2],'end':[1,4]}
    g={'x':10,'y':20,'cell_width':12,'cell_height':24}
    first=drag_points(g,(1500,1000),spec)
    second=drag_points({k:v*2 for k,v in g.items()},(3000,2000),spec)
    assert first==second


def test_emitter_requests_native_shapes_without_painting(tmp_path):
    import subprocess
    from tintprobe.capture_ghostty import write_launcher
    payload=tmp_path/'text';payload.write_text('a=b\n')
    for style,code in CURSOR_CODES.items():
        ready=tmp_path/'ready';release=tmp_path/'release';release.touch()
        launcher,_,_=write_launcher(tmp_path,'fixture',payload,ready,release,{'row':0,'column':1,'style':style})
        out=subprocess.check_output(['/bin/sh',str(launcher)])
        visibility='l' if style=='hidden' else 'h'
        assert out.endswith(f'\x1b[{code} q\x1b[?25{visibility}\x1b[3;2H'.encode())
        assert b'48;2' not in out


def test_transition_emitter_acknowledges_each_native_mode(tmp_path):
    import subprocess,time,json
    from tintprobe.capture_ghostty import write_launcher
    payload=tmp_path/'text';payload.write_text('a=b\n')
    ready=tmp_path/'ready';release=tmp_path/'release';control=tmp_path/'control'
    launcher,_,log=write_launcher(tmp_path,'transition',payload,ready,release,{'row':0,'column':1,'style':'steady-bar'},control)
    process=subprocess.Popen(['/bin/sh',str(launcher)],stdout=subprocess.PIPE)
    def wait_for(value):
        deadline=time.monotonic()+3
        while not ready.exists() or ready.read_text()!=value:
            assert process.poll() is None,log.read_text()
            assert time.monotonic()<deadline
            time.sleep(.01)
    try:
        wait_for('ready')
        for i,style in enumerate(('steady-block','hidden','steady-bar')):
            pending=tmp_path/'pending';pending.write_text(json.dumps({'sequence':i,'style':style}));pending.replace(control)
            wait_for(str(i))
    finally:
        release.touch()
        output,_=process.communicate(timeout=3)
    assert b'\x1b[2 q\x1b[?25h' in output
    assert b'\x1b[2 q\x1b[?25l' in output
    assert output.endswith(b'\x1b[6 q\x1b[?25h\x1b[3;2H')


def test_full_capture_assessment_cannot_bypass_selection_gate(tmp_path,monkeypatch):
    import json,subprocess
    from tintprobe.ghostty_quality import assess_capture
    im,g,p,ref,cells,lines,spec=selection_fixture()
    d=ImageDraw.Draw(im)
    for i,color in enumerate(list(p['ansi'].values())[1:7]):d.rectangle((i*72,0,i*72+71,23),fill=color)
    png=tmp_path/'selection.png';im.save(png)
    ansi=tmp_path/'selection.ansi';ansi.write_text('a <= b\nc >= d\n')
    # Perfect OCR deliberately cannot rescue a damaged native selection glyph.
    recognized={'rows':[{'row':i,'fragments':[{'text':line}]} for i,line in enumerate(lines)]}
    monkeypatch.setattr(subprocess,'run',lambda *a,**kw:subprocess.CompletedProcess(a,0,json.dumps(recognized),''))
    assert assess_capture(png,ansi,Path('unused'),p,ref,selection=spec)['status']=='pass'
    d.rectangle((36,48,47,71),fill=p['highlight']['background']);im.save(png)
    assert assess_capture(png,ansi,Path('unused'),p,ref,selection=spec)['status']=='fail'


def test_partial_capture_keeps_accessibility_error(tmp_path,monkeypatch):
    import tintprobe.capture_ghostty as capture_ghostty
    from tintprobe.evaluate_ghostty import prepare
    def interrupted(output,report):
        report['native_captures']=[{'id':'git-status','reason':'partial'}]
        raise RuntimeError('Accessibility permission is unavailable')
    monkeypatch.setattr(capture_ghostty,'capture',interrupted)
    result=prepare(tmp_path,True)
    assert result['reason']=='Native capture failed: Accessibility permission is unavailable'
    assert result['status']=='blocked' and not result['pass']
