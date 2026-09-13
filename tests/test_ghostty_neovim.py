from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.ghostty_glyphs import reference_sheet
from tintprobe.ghostty_neovim import assess
from tintprobe.context import load_palette


def test_live_cell_oracle_rejects_erased_edit_and_heavy_emphasis(tmp_path,monkeypatch):
    import tintprobe.ghostty_quality as ghostty_quality
    p=load_palette()
    g={'x':0,'y':0,'cell_width':12,'cell_height':24}
    monkeypatch.setattr(ghostty_quality,'grid',lambda *a:g)
    font=ImageFont.load_default_imagefont()
    atlas=Image.new('RGB',(1440,624),p['backgrounds']['base'])
    draw=ImageDraw.Draw(atlas)
    for c in reference_sheet()[1]:
        reference_font=font if ord(c['text'])<256 else ImageFont.load_default(size=16)
        draw.text((c['column']*12,(c['row']+2)*24),c['text'],font=reference_font,fill='black')
    im=Image.new('RGB',(24,72),p['backgrounds']['base']);draw=ImageDraw.Draw(im)
    bg=p['diff']['changeEmphasis']
    draw.rectangle((0,24,11,47),fill=bg);draw.text((0,24),'=',font=font,fill='black')
    image=tmp_path/'scene.png';im.save(image)
    shot={'scene':'diff','cursor':[2,0],'cells':[{'row':1,'column':0,'text':'=','fg':'#000000','bg':bg,'bold':False,'underline':False}]}
    shot['cells'].append({'row':1,'column':1,'text':' ','fg':'#000000','bg':p['backgrounds']['base'],'bold':False,'underline':False})
    cells=tmp_path/'scene.cells.json';cells.write_text(json.dumps(shot))
    assert assess(image,cells,p,(atlas,g))['status']=='pass'
    draw.text((12,24),'=',font=font,fill='black');im.save(image)
    assert assess(image,cells,p,(atlas,g))['status']!='pass'
    draw.rectangle((12,24,23,47),fill=p['backgrounds']['base']);im.save(image)
    shot['cells'][0]['bold']=True;cells.write_text(json.dumps(shot))
    assert assess(image,cells,p,(atlas,g))['status']=='fail'
    from tintprobe.ghostty_neovim import CONFIG
    with monkeypatch.context() as settings:
        settings.setitem(CONFIG, 'contracts', {})
        assert assess(image,cells,p,(atlas,g))['status']=='pass'
    shot['cells'][0]['bold']=False;cells.write_text(json.dumps(shot))
    draw.rectangle((0,24,11,47),fill=bg);im.save(image)
    assert assess(image,cells,p,(atlas,g))['status']=='fail'
