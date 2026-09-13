from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tintprobe.codex_ui import MODES, PLACEHOLDER, assess
from tintprobe.context import load_palette


def records():
    output = []
    for width in (60, 100):
        for mode in MODES:
            for phase in range(8):
                cells = [{'row': y, 'col': x, 'text': ' ', 'fg': 'Reset', 'bg': 'Reset', 'modifiers': ''}
                         for y in range(6) for x in range(width)]
                for row, col, text in ((0, 0, 'Working'), (3, 0, '»' if mode == 'ultra' else '›'), (3, 2, PLACEHOLDER)):
                    for i, char in enumerate(text):
                        cells[row*width+col+i]['text'] = char
                output.append({'width': width, 'height': 6, 'mode': mode, 'phase': phase,
                               'elapsed_ms': phase*300, 'cells': cells})
    return output


def test_readable_clean_timed_stock_ui_passes():
    result = assess(records(), load_palette())
    assert result['status'] == 'pass'
    assert result['captures'] == 48
    assert result['remaining_gaps']


@pytest.mark.parametrize('mutation', ['fade', 'dim', 'particle', 'fill', 'missing-text', 'missing-cell', 'short-time', 'readable-flicker'])
def test_one_bad_animation_phase_cannot_hide_in_other_passing_frames(mutation):
    rows = records()
    r = rows[5]
    if mutation == 'fade':
        r['cells'][0]['fg'] = 'Rgb(220, 220, 220)'
    elif mutation == 'dim':
        r['cells'][0]['modifiers'] = 'DIM'
    elif mutation == 'particle':
        r['cells'][2*r['width']+35]['text'] = '⠁'
    elif mutation == 'fill':
        r['cells'][4*r['width']+40]['bg'] = 'Red'
    elif mutation == 'missing-text':
        r['cells'][0]['text'] = ' '
    elif mutation == 'missing-cell':
        r['cells'].pop()
    elif mutation == 'readable-flicker':
        r['cells'][0]['fg'] = 'DarkGray'
    else:
        for r in rows:
            r['elapsed_ms'] = r['phase']
    result = assess(rows, load_palette())
    assert result['status'] == 'fail'


def test_constant_dim_text_never_counts_as_verified_contrast():
    rows = records()
    for r in rows:
        r['cells'][0]['modifiers'] = 'DIM'
    result = assess(rows, load_palette())
    assert result['status'] == 'unverified'
    assert result['findings'] == []
    assert len(result['unverified']) == 48


def test_missing_or_duplicate_frame_is_rejected():
    rows = records()
    for bad in (rows[:-1], rows[:-1]+[copy.deepcopy(rows[0])]):
        with pytest.raises(ValueError):
            assess(bad, load_palette())
