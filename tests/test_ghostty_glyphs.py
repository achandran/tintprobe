from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image, ImageDraw, ImageFont
from tintprobe.ghostty_glyphs import reference_sheet, templates_from_capture, recognize_rows, mask, classify, recover_content

G={'x':0,'y':0,'cell_width':12,'cell_height':24}
FONT=ImageFont.load_default(size=16)


def draw_rows(rows):
    image=Image.new('RGB',(120*12,(len(rows)+2)*24),'white')
    draw=ImageDraw.Draw(image)
    for row,text in enumerate(rows):
        for col,char in enumerate(text):draw.text((col*12,(row+2)*24),char,font=FONT,fill='black')
    return image


def atlas():
    _,labels=reference_sheet()
    image=Image.new('RGB',(120*12,26*24),'white');draw=ImageDraw.Draw(image)
    for cell in labels:draw.text((cell['column']*12,(cell['row']+2)*24),cell['text'],font=FONT,fill='black')
    return image


def test_reference_is_independent_of_fixture_text():
    payload, labels=reference_sheet()
    assert set(c['text'] for c in labels)==set(chr(i) for i in range(33,127)) | set('·•›‹└✔✓√')
    assert 'attempt' not in payload
    assert max(c['row'] for c in labels)<38


def test_punctuation_is_recognized_without_expected_text():
    templates=templates_from_capture(atlas(),G)
    rows,unknown=recognize_rows(draw_rows(['+$<=>!_-']),G,[0],templates)
    assert rows[0].rstrip()=='+$<=>!_-'
    assert not unknown


def test_erased_equals_wrong_operator_and_unexpected_suffix_are_not_recovered():
    reference=atlas()
    content={'status':'unverified','mismatches':[{'row':0,'expected':'<=','observed':'<'}]}
    assert recover_content(content,draw_rows(['<=']),G,reference,G)['status']=='pass'
    for damaged in ('<','< ','>=','<=+',''):
        assert recover_content(content,draw_rows([damaged]),G,reference,G)['status']=='unverified'


def test_ambiguous_shapes_never_pass():
    shape=frozenset([1,2,3])
    assert classify(shape,{'<':[shape],'>':[shape]})[0] is None
    assert classify(frozenset([10,11]),{'<':[shape]})[0] is None


def test_missing_reference_glyph_and_clipping_are_rejected():
    import pytest
    with pytest.raises(ValueError,match='Reference glyph missing'):
        templates_from_capture(Image.new('RGB',(1440,624),'white'),G)
    with pytest.raises(ValueError,match='clipped'):
        recognize_rows(Image.new('RGB',(12,72),'white'),G,[0],{'+':[frozenset([1])]})
