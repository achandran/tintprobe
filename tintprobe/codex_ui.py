from tintprobe.context import evaluation_output
from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Evaluate stock Codex status and composer cells across timed effort transitions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tomllib

from tintprobe.codex_native import color, write_gallery
from tintprobe.context import ROOT, load_palette, wcag

from tintprobe.context import CONFIG
PROFILE = ROOT / CONFIG['ports']['codex_config'] if CONFIG.get('ports', {}).get('codex_config') else evaluation_output('codex.toml')


def animations_enabled():
    return tomllib.loads(PROFILE.read_text())['tui']['animations']


PLACEHOLDER = 'Ask Codex to do anything'
MODES = ('low', 'max', 'ultra')


def assess(records, palette):
    expected = {(w, m, p) for w in (60, 100) for m in MODES for p in range(8)}
    if len(records) != len(expected) or {(r['width'], r['mode'], r['phase']) for r in records} != expected:
        raise ValueError('Missing or duplicate stock UI frames')
    findings = []
    unverified = []
    minima = []
    stable_regions = {}
    for width in (60, 100):
        for mode in MODES:
            frames = sorted((r for r in records if r['width'] == width and r['mode'] == mode), key=lambda r: r['phase'])
            times = [r['elapsed_ms'] for r in frames]
            if any(b <= a for a, b in zip(times, times[1:])) or times[-1] - times[0] < 2000:
                findings.append({'width': width, 'mode': mode, 'reason': 'Insufficient timed coverage'})
    for r in records:
        def fail(reason, **detail):
            findings.append({'width': r['width'], 'mode': r['mode'], 'phase': r['phase'], 'reason': reason, **detail})
        cells = {(c['row'], c['col']): c for c in r['cells']}
        if len(cells) != r['width'] * r['height'] or len(cells) != len(r['cells']) or set(cells) != {(y,x) for y in range(r['height']) for x in range(r['width'])}:
            fail('Incomplete frame geometry')
            continue
        lines = [''.join(cells[y, x]['text'] for x in range(r['width'])) for y in range(r['height'])]
        anchors = {}
        for label in ('Working', PLACEHOLDER):
            hits = [(y, line.index(label)) for y, line in enumerate(lines) if label in line]
            if len(hits) != 1:
                fail('Required UI text missing or ambiguous', text=label)
            else:
                anchors[label] = hits[0]
        if len(anchors) != 2:
            continue
        for label, (y, x) in anchors.items():
            dim_columns = []
            for col in range(x, x + len(label)):
                c = cells[y, col]
                if not c['text'].strip():
                    continue
                fg = color(c['fg'], palette, palette['foregrounds']['text'])
                bg = color(c['bg'], palette, palette['backgrounds']['base'])
                if 'REVERSED' in c['modifiers']:
                    fg, bg = bg, fg
                ratio = wcag(fg, bg)
                minima.append(ratio)
                if ratio < 4.5:
                    fail('UI text contrast below 4.5', text=c['text'], row=y, col=col, contrast=round(ratio, 3))
                if 'DIM' in c['modifiers']:
                    dim_columns.append(col)
            if dim_columns:
                unverified.append({'width': r['width'], 'mode': r['mode'], 'phase': r['phase'],
                                   'text': label, 'row': y, 'columns': dim_columns,
                                   'reason': 'Terminal DIM requires native pixel evidence'})
        y, x = anchors[PLACEHOLDER]
        # Stock empty-composer layout: one padding row above and below the input.
        # Bounds derive from the fixed text anchor, never from observed fill/noise.
        if x != 2 or y < 1 or y + 1 >= r['height']:
            fail('Unexpected composer layout')
            continue
        bg = cells[y, x]['bg']
        prompt = '»' if r['mode'] == 'ultra' else '›'
        working_y, working_x = anchors['Working']
        region = [cells[working_y, col] for col in range(working_x, working_x + len('Working'))]
        region += [cells[row, col] for row in range(y - 1, y + 2) for col in range(r['width'])]
        key = (r['width'], r['mode'])
        if key in stable_regions and region != stable_regions[key]:
            fail('Reduced-motion status or composer changed across frames')
        stable_regions.setdefault(key, region)
        for row in range(y - 1, y + 2):
            for col in range(r['width']):
                c = cells[row, col]
                wanted = PLACEHOLDER[col-x] if row == y and x <= col < x+len(PLACEHOLDER) else prompt if row == y and col == 0 else ' '
                if c['text'] != wanted or c['bg'] != bg:
                    fail('Composer artifact or uneven fill', row=row, col=col, observed=c['text'])
    return {'status': 'fail' if findings else 'unverified' if unverified else 'pass',
            'captures': len(records), 'findings': findings, 'unverified': unverified,
            'minimum_nominal_text_contrast': round(min(minima), 3) if minima else None,
            'remaining_gaps': ['Stock Codex shares composer and user-message surfaces',
                               'Stock Codex does not expose separate transcript metadata colors',
                               'Native terminal pixels and font rasterization are not certified by cell replay']}


def run(source, output, *, animated_control=False):
    source = source.resolve(); output = output.resolve()
    pin = json.loads((evaluation_path('sources.json')).read_text())['codex']['revision']
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip() != pin:
        raise ValueError('Codex revision mismatch')
    paths = [source/'codex-rs/tui/src/chatwidget/tests.rs', source/'codex-rs/tui/src/chatwidget/tests/helpers.rs']
    originals = {p: p.read_bytes() for p in paths}
    for path, original in originals.items():
        if original != subprocess.check_output(['git','-C',str(source),'show','HEAD:'+str(path.relative_to(source))]):
            raise ValueError('Refusing to patch dirty Codex test source: '+str(path))
    output.mkdir(parents=True, exist_ok=True)
    palette = load_palette()
    rgb = lambda value: json.dumps([int(value[i:i+2],16) for i in (1,3,5)])
    animations = True if animated_control else animations_enabled()
    env = dict(os.environ, ITHILIEN_UI_OUTPUT=str(output/'codex-ui-cells.json'),
               ITHILIEN_UI_ANIMATIONS=str(animations).lower(),
               ITHILIEN_UI_FG=rgb(palette['foregrounds']['text']), ITHILIEN_UI_BG=rgb(palette['backgrounds']['base']))
    adapter = evaluation_path('codex_ui_adapter.rs')
    marker = b'    let mut cfg = test_config().await;'
    if originals[paths[1]].count(marker) != 1:
        raise ValueError('Codex configuration helper changed')
    try:
        paths[0].write_bytes(originals[paths[0]] + ('\ninclude!('+json.dumps(str(adapter))+');\n').encode())
        paths[1].write_bytes(originals[paths[1]].replace(marker, marker + b'\n    cfg.animations = std::env::var("ITHILIEN_UI_ANIMATIONS").unwrap().parse().unwrap();'))
        with (output/'native.log').open('w') as log:
            result = subprocess.run(['just','test','--locked','-p','codex-tui','--lib','ithilien_stock_ui_cells'],
                                    cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            raise RuntimeError('Stock UI replay failed; inspect '+str(output/'native.log'))
    finally:
        for path, original in originals.items():
            path.write_bytes(original)
    records = json.loads((output/'codex-ui-cells.json').read_text())
    report = assess(records, palette)
    report.update(source_revision=pin, animations=animations, negative_control=animated_control,
                  profile_sha256=hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
                  adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest(),
                  analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  cells_sha256=hashlib.sha256((output/'codex-ui-cells.json').read_bytes()).hexdigest(),
                  scope='Unmodified stock production widgets, configured from the repository motion profile; 8 timed frames per effort at two widths. No model calls or commands executed by the replay.')
    write_gallery(records, output, palette)
    gallery = output/'codex-gallery.html'
    gallery.write_text(gallery.read_text().replace('Native Codex diff renderer', 'Stock Codex UI motion evaluation'))
    (output/'report.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=evaluation_output('results/codex-ui'))
    parser.add_argument('--animated-control', action='store_true', help='Negative control: enable stock animations in the isolated replay only')
    args = parser.parse_args()
    result = run(args.source, args.output, animated_control=args.animated_control)
    print(json.dumps({k: v for k, v in result.items() if k not in ('findings', 'unverified')}, indent=2))
    print(f"Findings: {len(result['findings'])}; unverified text runs: {len(result['unverified'])}. See {args.output / 'report.json'}")
    raise SystemExit(0 if result['status'] == 'pass' else 1)
