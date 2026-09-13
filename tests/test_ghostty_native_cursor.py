from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image, ImageDraw, ImageFont
from tintprobe.ghostty_quality import cursor_check
from tintprobe.ghostty_glyphs import reference_sheet
from tintprobe.context import load_palette


def specimen():
    p=load_palette();g={'x':0,'y':0,'cell_width':12,'cell_height':24}
    font=ImageFont.load_default_imagefont()
    atlas=Image.new('RGB',(1440,624),p['backgrounds']['base']);draw=ImageDraw.Draw(atlas)
    for c in reference_sheet()[1]:
        reference_font=font if ord(c['text'])<256 else ImageFont.load_default(size=16)
        draw.text((c['column']*12,(c['row']+2)*24),c['text'],font=reference_font,fill='black')
    im=Image.new('RGB',(1440,72),p['backgrounds']['base']);draw=ImageDraw.Draw(im)
    draw.rectangle((0,48,11,71),fill=p['highlight']['cursorBlock'])
    draw.text((0,48),'=',font=font,fill='black')
    return im,g,p,(atlas,g),{'row':0,'column':0,'text':'=','fg':'#000000'}


def test_real_cursor_gate_requires_fill_and_readable_covered_glyph():
    im,g,p,ref,cell=specimen()
    assert cursor_check(im,g,cell,p,ref)['status']=='pass'
    for kind in ('missing','outline','erased','wrong'):
        bad=im.copy();draw=ImageDraw.Draw(bad)
        draw.rectangle((0,48,11,71),fill=p['highlight']['cursorBlock'] if kind in ('erased','wrong') else p['backgrounds']['base'])
        if kind=='outline':draw.rectangle((0,48,11,71),outline=p['highlight']['cursorBlock'])
        if kind!='erased':draw.text((0,48),'-' if kind=='wrong' else '=',font=ImageFont.load_default_imagefont(),fill='black')
        assert cursor_check(bad,g,cell,p,ref)['status']!='pass',kind
    assert cursor_check(im,g,cell,p,None)['status']=='unverified'
    # Antialiased strokes can miss the floor despite nominal black/Briar passing.
    low=im.copy();draw=ImageDraw.Draw(low)
    draw.rectangle((0,48,11,71),fill=p['highlight']['cursorBlock'])
    draw.text((0,48),'=',font=ImageFont.load_default(size=16),fill='black')
    assert cursor_check(low,g,cell,p,ref)['status']=='fail'
    wrong_geometry=dict(g,cell_width=13)
    assert cursor_check(low,g,cell,p,(ref[0],wrong_geometry))['status']=='fail'



def test_cursor_emitter_positions_actual_terminal_cursor(tmp_path):
    import subprocess
    from tintprobe.capture_ghostty import write_launcher
    payload=tmp_path/'cursor.ansi';payload.write_text('a=b\n')
    ready=tmp_path/'ready';release=tmp_path/'release';release.touch()
    launcher,_,_=write_launcher(tmp_path,'cursor',payload,ready,release,{'row':0,'column':1})
    result=subprocess.check_output(['/bin/sh',str(launcher)])
    assert result.endswith(b'\x1b[2 q\x1b[?25h\x1b[3;2H')
    assert b'48;2' not in result  # No painted RGB cursor imitation.
    assert ready.exists()
