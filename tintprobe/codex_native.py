from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Run our adapter inside a pinned native Codex diff renderer, restoring source."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tintprobe.context import ROOT, load_palette, wcag


def color(value,palette,default):
    if value=='Reset':return default
    m=re.fullmatch(r'Rgb\((\d+), (\d+), (\d+)\)',value)
    if m:return '#'+''.join(f'{int(v):02X}' for v in m.groups())
    m=re.fullmatch(r'Indexed\((\d+)\)',value)
    names=['Black','Red','Green','Yellow','Blue','Magenta','Cyan','Gray','DarkGray','LightRed','LightGreen','LightYellow','LightBlue','LightMagenta','LightCyan','White']
    if m:i=int(m[1])
    elif value in names:i=names.index(value)
    else:raise ValueError('Unknown native terminal color: '+value)
    if i<16:return list(palette['ansi'].values())[i]
    if i>=232:return '#'+f'{8+10*(i-232):02X}'*3
    i-=16; levels=[0,95,135,175,215,255]
    return '#'+''.join(f'{levels[x]:02X}' for x in [i//36,(i//6)%6,i%6])


def run_native(source,output,theme=None,palette=None):
    output.mkdir(parents=True,exist_ok=True)
    theme=theme or port_path('codex_theme')
    pin=json.loads((evaluation_path('sources.json')).read_text())['codex']['revision']
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==pin
    cargo=shutil.which('cargo')
    if not cargo:return {'status':'not_run','reason':'cargo is unavailable'}
    target=source/'codex-rs/tui/src/diff_render.rs'
    original=target.read_bytes()
    pristine=subprocess.check_output(['git','-C',str(source),'show','HEAD:codex-rs/tui/src/diff_render.rs'])
    if original!=pristine:raise ValueError('Codex diff renderer has local changes; refusing to patch it')
    cells_path=(output/'codex-cells.json').resolve()
    try:
        target.write_bytes(original+('\ninclude!('+json.dumps(str(evaluation_path('codex_adapter.rs')))+');\n').encode())
        env=dict(os.environ,ITHILIEN_CODEX_THEME=str(theme),ITHILIEN_ROOT=str(ROOT),TINTPROBE_FIXTURES=str(EVALUATION/"fixtures"),ITHILIEN_CODEX_OUTPUT=str(cells_path))
        with (output/'codex-test.log').open('w') as log:
            result=subprocess.run([cargo,'test','--locked','-p','codex-tui','--lib','exported_theme_native_cells'],cwd=source/'codex-rs',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        if result.returncode:return {'status':'fail','reason':'Native adapter failed; see codex-test.log'}
    finally:target.write_bytes(original)
    palette=palette or load_palette();failures=[];modifiers=set()
    records=json.loads(cells_path.read_text())
    write_gallery(records,output,palette)
    for record in records:
        for cell in record['cells']:
            if not cell['text'].strip():continue
            fg=color(cell['fg'],palette,palette['foregrounds']['text']);bg=color(cell['bg'],palette,palette['backgrounds']['base'])
            ratio=wcag(fg,bg);modifiers.add(cell['modifiers'])
            if ratio<4.5:failures.append({'file':record['file'],'kind':record['kind'],'level':record['level'],'text':cell['text'],'contrast':round(ratio,3)})
    return {'status':'pass' if not failures else 'fail','captures':len(records),'failures':failures,'modifiers':sorted(modifiers),'scope':'Native custom-theme diff cells; terminal dim/selection rendering and general agent prose still require separate checks'}


def write_gallery(records, output, palette):
    import html
    blocks=[]
    for record in records:
        lines={}
        for cell in record['cells']:
            fg=color(cell['fg'],palette,palette['foregrounds']['text'])
            bg=color(cell['bg'],palette,palette['backgrounds']['base'])
            if 'REVERSED' in cell['modifiers']:fg,bg=bg,fg
            style=f'color:{fg};background:{bg};'
            if 'BOLD' in cell['modifiers']:style+='font-weight:bold;'
            if 'ITALIC' in cell['modifiers']:style+='font-style:italic;'
            if 'UNDERLINED' in cell['modifiers']:style+='text-decoration:underline;'
            lines.setdefault(cell['row'],[]).append(f'<span title="{html.escape(cell["modifiers"])}" style="{style}">{html.escape(cell["text"])}</span>')
        title=html.escape(f'{record["file"]} / {record["kind"]} / {record["level"]} / {record["width"]} columns')
        blocks.append('<h2>'+title+'</h2><pre>'+'\n'.join(''.join(row) for row in lines.values())+'</pre>')
    (output/'codex-gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>Native Codex cells</title><style>body{background:#f6f6f3;padding:24px}pre{font:16pt/1.4 "Berkeley Mono Medium",monospace}h2{font:18px sans-serif}</style><h1>Native Codex diff renderer</h1><p>Actual Ratatui cells with the selected theme adapter. DIM is recorded in tooltips but not simulated; its appearance depends on the terminal. This is not a complete agent-session capture.</p>'+''.join(blocks))
    gallery=output/'codex-gallery.html'
    gallery.write_text(gallery.read_text().replace('background:#f6f6f3', 'background:'+palette['backgrounds']['base']))
