from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Live Neovim TUI fixtures, with an independent screen-cell/pixel comparison.

The application runs inside Ghostty, not in a headless cell replay. The screen
oracle is obtained from that same Neovim process after its native redraw.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from tintprobe.context import ROOT, CONFIG

SCENES = ('diff', 'search', 'selection', 'diagnostic', 'completion')


def fixtures(output):
    records = []
    available = shutil.which('nvim') and all(Path(p).is_dir() for p in default_adapter()['paths'])
    for scene in SCENES:
        name = 'neovim-'+scene
        # A declarative request, not a fabricated ANSI application rendering.
        path = output/(name+'.json')
        path.write_text(json.dumps({'scene': scene, 'application': 'live Neovim TUI'}))
        records.append({'id': name, 'kind': 'native-neovim',
                        'status': 'prepared' if available else 'blocked',
                        'reason': '' if available else 'Neovim or a configured theme dependency is missing',
                        'request': path.name,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def launch(request, ready, release):
    import pynvim
    output = request.parent
    scene = json.loads(request.read_text())['scene']
    socket = Path('/private/tmp')/('ithilien-nvim-'+str(os.getpid())+'.sock')
    init = output/(request.stem+'.lua')
    adapter = default_adapter()
    setup = '\n'.join('vim.opt.rtp:prepend('+json.dumps(str(p))+')' for p in adapter['paths'])
    init.write_text(setup+'\n'+adapter['setup']+'\n'+
                    'vim.opt.termguicolors=true\nvim.opt.swapfile=false\n'
                    'vim.opt.shadafile="NONE"\nvim.opt.mouse=""\nvim.opt.title=false\n'
                    'vim.opt.laststatus=0\nvim.opt.showmode=false\nvim.opt.showcmd=false\n'
                    'vim.opt.ruler=false\nvim.opt.number=false\nvim.opt.signcolumn="no"\n'
                    'vim.opt.fillchars={eob=" ",diff="-",vert="|",fold="-"}\n')
    state = output/(request.stem+'-state'); state.mkdir(exist_ok=True)
    env = dict(os.environ, XDG_STATE_HOME=str(state), XDG_CACHE_HOME=str(state))
    proc = subprocess.Popen([shutil.which('nvim'), '-n', '-i', 'NONE', '-u', str(init), '--listen', str(socket)], env=env)
    n = None
    try:
        deadline = time.monotonic()+15
        while not socket.exists():
            if proc.poll() is not None: raise RuntimeError('Native Neovim exited before RPC startup')
            if time.monotonic()>deadline: raise RuntimeError('Native Neovim RPC startup timed out')
            time.sleep(.05)
        n = pynvim.attach('socket', path=str(socket))
        n.exec_lua('''
          local scene = ...
          local colors = {'#8B3037','#315F46','#795922','#345E77','#70516D','#255354'}
          local tab = ''
          for i, color in ipairs(colors) do
            vim.api.nvim_set_hl(0,'IthilienCalibration'..i,{fg=color,bg=color})
            tab=tab..'%#IthilienCalibration'..i..'#      '
          end
          vim.o.tabline=tab..'%#Normal#%='; vim.o.showtabline=2
          vim.api.nvim_buf_set_lines(0,0,-1,false,{'def retry(attempt):','    return attempt <= 3','','# Boundary comparison: < versus <=','result = retry(3)'})
          vim.bo.filetype='python'; vim.cmd('syntax on')
          if scene == 'diff' then
            vim.cmd('diffthis'); vim.cmd('vnew')
            vim.api.nvim_buf_set_lines(0,0,-1,false,{'def retry(attempt):','    return attempt < 3','','# Boundary comparison: < versus <=','result = retry(3)'})
            vim.bo.filetype='python'; vim.cmd('diffthis'); vim.cmd('wincmd l')
          elseif scene == 'search' then
            vim.fn.setreg('/','attempt'); vim.o.hlsearch=true
            vim.cmd('normal! n')
          elseif scene == 'selection' then
            vim.api.nvim_win_set_cursor(0,{2,4}); vim.cmd('normal! v$')
          elseif scene == 'diagnostic' then
            vim.diagnostic.set(vim.api.nvim_create_namespace('native-diagnostic'),0,
              {{lnum=1,col=4,message='ERROR: boundary must exclude 3',severity=vim.diagnostic.severity.ERROR}},
              {virtual_text={prefix='E'},signs=false,underline=false})
            vim.diagnostic.open_float(0,{scope='buffer',focus=false,border={'+','-','+','|','+','-','+','|'}})
          elseif scene == 'completion' then
            vim.api.nvim_win_set_cursor(0,{5,0})
            vim.cmd('startinsert')
            vim.defer_fn(function() vim.fn.complete(1,{{word='result',menu='local variable'},{word='retry',menu='function'}}) end,100)
          end
          vim.cmd('redraw!')
        ''', scene)
        time.sleep(.5)
        # Attach an observational UI at exactly the TUI's dimensions. The native
        # redraw protocol supplies final composed RGB attributes; screenattr IDs
        # are not syntax-group IDs and must not be passed to synIDattr.
        dimensions = n.exec_lua('return {vim.o.columns,vim.o.lines}')
        grid_cells={}; attrs={}; defaults={}; cursor=[0,0]
        def notify(name, args):
            if name=='native_snapshot': n.stop_loop(); return
            if name!='redraw': return
            for event in args:
                for item in event[1:]:
                    kind=event[0]
                    if kind=='default_colors_set': defaults.update(fg=item[0],bg=item[1])
                    elif kind=='hl_attr_define': attrs[item[0]]=item[1]
                    elif kind=='grid_clear': grid_cells.clear()
                    elif kind=='grid_cursor_goto': cursor[:]=item[1:3]
                    elif kind=='grid_line':
                        _,row,col,cells,*_=item;attr=0
                        for cell in cells:
                            if len(cell)>1: attr=cell[1]
                            for _ in range(cell[2] if len(cell)>2 else 1):
                                grid_cells[row,col]=(cell[0],attr);col+=1
                    elif kind=='grid_scroll':
                        _,top,bottom,left,right,rows,cols=item;previous=dict(grid_cells)
                        for row in range(top,bottom):
                            for col in range(left,right):grid_cells[row,col]=previous.get((row+rows,col+cols),(' ',0))
        def attach():
            n.ui_attach(*dimensions,rgb=True,ext_linegrid=True)
            n.exec_lua("local channel=...;vim.defer_fn(function() vim.cmd('redraw!');vim.rpcnotify(channel,'native_snapshot') end,150)",n.channel_id)
        n.run_loop(None,notify,attach)
        snapshot=n.exec_lua('return {mode=vim.fn.mode(),popup=vim.fn.pumvisible(),version=vim.version()}')
        cells=[]
        for row,col in ((r,c) for r in range(dimensions[1]) for c in range(dimensions[0])):
            text,attr=grid_cells.get((row,col),(' ',0))
            style=attrs.get(attr,{})
            fg,bg=style.get('foreground',defaults['fg']),style.get('background',defaults['bg'])
            if style.get('reverse'):fg,bg=bg,fg
            cells.append({'row':row,'column':col,'text':text,'fg':f'#{fg:06X}','bg':f'#{bg:06X}',
                          'bold':style.get('bold',False),'underline':style.get('underline',False)})
        snapshot.update(cells=cells,columns=dimensions[0],rows=dimensions[1],cursor=cursor,scene=scene,
                        source='Native redraw protocol from an observational UI attached to the same live TUI process at identical dimensions')
        (output/(request.stem+'.cells.json')).write_text(json.dumps(snapshot))
        ready.write_text('ready')
        deadline = time.monotonic()+90
        while not release.exists() and time.monotonic()<deadline:
            if proc.poll() is not None: raise RuntimeError('Native Neovim closed before capture')
            time.sleep(.1)
    finally:
        if n:
            try: n.command('qa!')
            except (OSError, EOFError): pass
            n.close()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate(); proc.wait(timeout=5)
        socket.unlink(missing_ok=True)


def assess(image_path, cells_path, palette, reference):
    from tintprobe.ghostty_quality import srgb_image, grid, cell_checks, rgb
    from tintprobe.ghostty_glyphs import crop_cell, mask, classify, templates_from_capture, reference_sheet, REFERENCE_GLYPHS
    im = srgb_image(image_path)
    g = grid(im, list(palette['ansi'].values())[1:7])
    # Shared helpers reserve two calibration rows; live Neovim owns the entire
    # grid and has a calibration tabline in row zero.
    g = dict(g, y=g['y']-2*g['cell_height'])
    shot = json.loads(cells_path.read_text())
    findings=[]; unknown=[]; grouped=defaultdict(list); cache={}
    if not reference: raise ValueError('Native glyph reference missing')
    if (g['cell_width'],g['cell_height']) != (reference[1]['cell_width'],reference[1]['cell_height']):
        raise ValueError('Native application/reference grid differs')
    templates=templates_from_capture(*reference)
    content_image=im
    cursor_boundary=None
    if shot.get('mode')=='i':
        from tintprobe.ghostty_interactions import shape_check
        covered=next((c for c in shot['cells'] if [c['row'],c['column']]==shot['cursor']),None)
        if covered:
            cursor_boundary=shape_check(im,g,covered,palette,'steady-bar',reference)
            if cursor_boundary['status']=='pass':
                content_image=im.copy()
                x=round(g['x']+covered['column']*g['cell_width'])
                y=g['y']+(covered['row']+2)*g['cell_height']
                for xx in range(x-1,x+round(g['cell_width'])):
                    for yy in range(y,y+g['cell_height']):
                        if max(abs(a-b) for a,b in zip(im.getpixel((xx,yy)),rgb(palette['highlight']['cursor'])))<=3:
                            content_image.putpixel((xx,yy),rgb(covered['bg']))
    # Reference glyphs are followed by a blank cell. An italic stroke may spill
    # into that blank. Require an exact native-reference spill mask, selected
    # using the independently recognized preceding glyph, never expected text.
    spills=defaultdict(set)
    for label in reference[1].get('reference_labels',reference_sheet()[1]):
        spills[label['text']].add(mask(crop_cell(reference[0],reference[1],label['row'],label['column']+1)))
    recovered_spills=[]
    for c in shot['cells']:
        if c['row']==0 or [c['row'],c['column']]==shot['cursor']: continue
        crop=crop_cell(im,g,c['row'],c['column'])
        modal=Counter(crop.get_flattened_data()).most_common(1)[0][0]
        if max(abs(a-b) for a,b in zip(modal,rgb(c['bg'])))>3:
            findings.append(dict(c,reason='background differs from native screen cell'))
        if c['text'] not in (' '+REFERENCE_GLYPHS) or len(c['text'])!=1:
            unknown.append(dict(c,reason='non-ASCII glyph outside reference alphabet')); continue
        ink=mask(crop_cell(content_image,g,c['row'],c['column']))
        if ink not in cache: cache[ink]=classify(ink,templates)
        observed, score=cache[ink]
        if c['text']==' ' and observed is None and c['column']>0:
            preceding=mask(crop_cell(content_image,g,c['row'],c['column']-1))
            if preceding not in cache:cache[preceding]=classify(preceding,templates)
            left,_=cache[preceding]
            if ink in spills.get(left,set()):
                observed=' '
                recovered_spills.append({'row':c['row'],'column':c['column'],'recognized_left_glyph':left})
        if observed!=c['text']: unknown.append(dict(c,observed=observed,distance=score))
        grouped[c['bg']].append(c)
    pixels=[cell_checks(im,g,cells,bg) for bg,cells in grouped.items()]
    findings += [f for p in pixels for f in p['findings']]
    emphasized=[c for c in shot['cells'] if c['bg']==palette['diff']['changeEmphasis'] and c['text'].strip()]
    contracts=[]
    if CONFIG.get('contracts', {}).get('ordinary_weight_diffs', False) and any(c['bold'] or c['underline'] for c in emphasized): contracts.append('Diff emphasis must retain ordinary weight without underline')
    if shot['scene']=='diff':
        if not any(c['text']=='=' for c in emphasized): contracts.append('Exact edited equals sign missing from emphasis')
    if shot['scene']=='completion' and not shot['popup']: contracts.append('Completion menu did not open')
    role={'selection':palette['highlight']['background'],'search':palette['backgrounds']['search']}.get(shot['scene'])
    if role and not any(c['bg']==role for c in shot['cells']): contracts.append('Required overlay is absent')
    if shot['scene']=='diagnostic' and 'ERROR: boundary must exclude 3' not in ''.join(c['text'] for c in shot['cells']):
        contracts.append('Diagnostic message absent')
    return {'status':'fail' if findings or contracts else 'unverified' if unknown else 'pass',
            'pixel_findings':findings,'glyph_mismatches':unknown,'contracts':contracts,
            'exact_reference_spills':recovered_spills,
            'insert_cursor_boundary':cursor_boundary,
            'ordinary_weight_diff_cells':len(emphasized),'screen_cells':len(shot['cells']),
            'image_sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),
            'cells_sha256':hashlib.sha256(cells_path.read_bytes()).hexdigest(),
            'source':shot.get('source'),
            'scope':('Recorded native Codex renderer cells displayed in Ghostty; not live app-server/model interaction.' if shot['scene'].startswith('codex-') else 'Live Neovim TUI pixels versus same-process redraw cells. Cursor cell excluded (separate cursor suite). Not exhaustive plugin/LSP coverage.')+' Fixed reference alphabet; other glyphs remain unverified.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--ready',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True)
    a=p.parse_args();launch(a.request,a.ready,a.release)
