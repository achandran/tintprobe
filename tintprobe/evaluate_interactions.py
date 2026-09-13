from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Native fzf PTY and Neovim interaction evidence; never native Ghostty pixels."""
import argparse, hashlib, html, json, os, shlex, shutil, signal, subprocess, tempfile
from pathlib import Path
import pynvim
from tintprobe.context import ROOT, wcag
from tintprobe.compare_themes import check_adapter, render
from tintprobe.evaluation_checks import effective_colors

FZF_EXACT_QUERY = "\x15'git"  # Clear the query, then request an exact substring.

GROUPS = ['Normal','DiagnosticError','DiagnosticWarn','DiagnosticInfo','DiagnosticHint',
          'DiagnosticVirtualTextError','DiagnosticVirtualTextWarn','DiagnosticVirtualTextInfo','DiagnosticVirtualTextHint',
          'Pmenu','PmenuSel','PmenuKindSel','PmenuExtraSel','PmenuMatch','PmenuMatchSel',
          'LspSignatureActiveParameter','LspInlayHint','Visual','Cursor','MatchParen']


def pair(fg, bg):
    ratio=wcag(fg,bg)
    return {'foreground':fg,'background':bg,'contrast':round(ratio,4),'minimum':4.5,'pass':ratio>=4.5}


def fzf_roles(options):
    """Read the final emitted --color option, not palette assumptions."""
    colors={}
    for word in shlex.split(options):
        if word.startswith('--color='):
            for token in word[8:].split(','):
                parts=token.split(':')
                if len(parts)>1 and parts[1].startswith('#'):colors[parts[0]]=parts[1]
    backgrounds={'fg':'bg','fg+':'bg+','hl':'bg','hl+':'bg+','prompt':'bg','spinner':'bg',
                 'info':'bg','header':'bg','query':'bg','pointer':'gutter','marker':'gutter'}
    return {role:pair(colors[role],colors.get(bg,colors['bg'])) for role,bg in backgrounds.items() if role in colors}


def capture(adapter, width, scene, fixture=None, options=None, fzf=None, nvim=None, action='', workflow=None):
    resolved=check_adapter(adapter)
    def timeout(*_):raise TimeoutError('Interaction capture timed out')
    old=signal.signal(signal.SIGALRM,timeout);signal.alarm(20)
    with tempfile.TemporaryDirectory(prefix='ithilien-interaction-') as tmp:
        n=pynvim.attach('child',argv=['env','XDG_STATE_HOME='+tmp,'XDG_CACHE_HOME='+tmp,nvim,'--embed','--headless','-n','-u','NONE','-i','NONE'])
        grid={};attrs={};attr_info={};defaults={};groups={};job=None;exit_status=None
        def notify(name,args):
            if name=='interaction_done':n.stop_loop();return
            if name!='redraw':return
            for event in args:
                for item in event[1:]:
                    kind=event[0]
                    if kind=='default_colors_set':defaults.update(fg=item[0],bg=item[1])
                    elif kind=='hl_attr_define':
                        attrs[item[0]]=item[1]
                        if len(item)>3:attr_info[item[0]]=item[3]
                    elif kind=='grid_clear':grid.clear()
                    elif kind=='grid_line':
                        _,row,col,cells,*_=item;a=0
                        for cell in cells:
                            if len(cell)>1:a=cell[1]
                            for _ in range(cell[2] if len(cell)>2 else 1):grid[row,col]=(cell[0],a);col+=1
                    elif kind=='grid_scroll':
                        _,top,bot,left,right,rows,cols=item;prev=dict(grid)
                        for r in range(top,bot):
                            for c in range(left,right):grid[r,c]=prev.get((r+rows,c+cols),(' ',0))
        def setup():
            nonlocal groups,job
            n.ui_attach(width,40 if workflow else 24,rgb=True,ext_linegrid=True,ext_hlstate=bool(workflow))
            n.command('set termguicolors background=light laststatus=0 noshowmode noruler')
            for p in resolved['paths']:n.exec_lua('vim.opt.rtp:prepend(...)',str(p))
            if workflow:n.command('cd '+n.funcs.fnameescape(tmp))
            n.exec_lua(adapter['setup'])
            groups=n.exec_lua('local out={};for _,g in ipairs(...) do out[g]=vim.api.nvim_get_hl(0,{name=g,link=false}) end;return out',GROUPS)
            if workflow:
                n.exec_lua('local path,scene,state=...;dofile(path)(scene,state)',workflow,scene,action)
            elif scene=='fzf':
                env={'FZF_DEFAULT_OPTS':options,'FZF_CTRL_R_OPTS':'','FZF_DEFAULT_COMMAND':'','TERM':'xterm-256color','COLORTERM':'truecolor','NO_COLOR':''}
                command=shlex.quote(fzf)+' --read0 --sync --no-sort --layout=reverse --height=100% --query=ghostty < '+shlex.quote(str(fixture))
                job=n.exec_lua('local cmd,env=...;return vim.fn.termopen({"/bin/sh","-c",cmd},{env=env})',command,env)
                if action:n.exec_lua('local job,keys=...;vim.defer_fn(function() if vim.fn.jobwait({job},0)[1] == -1 then vim.fn.chansend(job,keys) end end,350)',job,action)
            else:
                n.api.buf_set_lines(0,0,-1,False,['def read_config(path: str) -> str:', '    content = path.read_text()', '    return content', '', 'read_config("ghostty.conf")'])
                n.command('setfiletype python');n.command('syntax on')
                if scene=='diagnostics':
                    n.exec_lua('''local ns=vim.api.nvim_create_namespace('fixture');local ds={};for i,label in ipairs({'ERROR invalid path','WARN deprecated call','INFO return type','HINT unused name'}) do ds[#ds+1]={lnum=i-1,col=0,severity=i,message=label,source='fixture'} end;vim.diagnostic.config({virtual_text={prefix='●'},signs=true,underline=true});vim.diagnostic.set(ns,0,ds)''')
                elif scene=='completion':
                    n.command('normal! Go');n.command('startinsert')
                    n.exec_lua('''vim.defer_fn(function() vim.fn.complete(1,{{word='read_config',kind='f',menu='local function'},{word='read_configuration',kind='f',menu='module helper'}}) end,100)''')
                elif scene=='diagnostic-float':
                    n.exec_lua("local ns=vim.api.nvim_create_namespace('fixture');vim.diagnostic.set(ns,0,{{lnum=1,col=4,severity=1,message='Cannot access read_text on str',source='Python fixture'}});vim.api.nvim_win_set_cursor(0,{2,4});vim.diagnostic.open_float(0,{scope='line',focus=false})")
                elif scene in ('documentation','signature'):
                    n.exec_lua("local scene=...;local lines=scene=='documentation' and {'read_config(path: str) -> str','','Read a UTF-8 configuration file.','','Raises OSError when the path is unavailable.'} or {'read_config(path: str) -> str','Active parameter: path'};local b=vim.lsp.util.open_floating_preview(lines,'python',{border='single',focus=false});if scene=='signature' then vim.api.nvim_buf_set_extmark(b,vim.api.nvim_create_namespace('signature-fixture'),0,12,{end_col=16,hl_group='LspSignatureActiveParameter'}) end",scene)
                elif scene=='references':
                    n.exec_lua("vim.fn.setqflist({{bufnr=vim.api.nvim_get_current_buf(),lnum=1,col=5,text='definition: read_config'},{bufnr=vim.api.nvim_get_current_buf(),lnum=5,col=1,text='reference: read_config'}});vim.cmd('copen 6')")
                elif scene=='inlay':
                    n.exec_lua("vim.api.nvim_buf_set_extmark(0,vim.api.nvim_create_namespace('inlay-fixture'),1,11,{virt_text={{': str','LspInlayHint'}},virt_text_pos='inline'});vim.api.nvim_buf_set_extmark(0,vim.api.nvim_create_namespace('reference-fixture'),4,0,{end_col=11,hl_group='LspReferenceText'})")
            n.exec_lua("local ch=...;vim.defer_fn(function() vim.cmd('redraw!');vim.rpcnotify(ch,'interaction_done') end,900)",n.channel_id)
        setup_errors=[]
        def safe_setup():
            try:setup()
            except Exception as exc:
                setup_errors.append(str(exc));n.stop_loop()
        try:
            n.run_loop(None,notify,setup_cb=safe_setup)
            if setup_errors:raise RuntimeError(setup_errors[0])
            if job:exit_status=n.funcs.jobwait([job],0)[0]
            shot={'case':scene,'width':width,'state':action or 'initial','defaults':defaults,'attrs':attrs,'highlights':groups,'cells':[{'row':r,'col':c,'text':t,'attr':a} for (r,c),(t,a) in sorted(grid.items())]}
            text='\n'.join(''.join(grid.get((r,c),(' ',0))[0] for c in range(width)) for r in range(40 if workflow else 24))
            shot['text']=text
            if workflow:
                shot['attr_info']=attr_info
                shot['evidence']=n.exec_lua('return _G.ithilien_workflow_evidence()')
            if scene=='fzf' and (exit_status!=-1 or 'ghostty' not in text):raise RuntimeError('fzf did not render a live result list: '+' | '.join(line.strip() for line in text.splitlines() if line.strip()))
            if scene=='diagnostics' and not all(label in text for label in ('ERROR','WARN','INFO','HINT')):raise RuntimeError('Diagnostic fixture did not render all severities')
            if scene=='completion' and 'module helper' not in text:raise RuntimeError('Completion popup did not render')
            required={'diagnostic-float':'Cannot access read_text','documentation':'Read a UTF-8','signature':'Active parameter: path','references':'reference: read_config','inlay':'content: str'}
            if scene in required and required[scene] not in text:raise RuntimeError('Missing workflow content: '+scene)
            shot['workflow_provenance']=('installed plugin renderer; live LSP evidence recorded for python-lsp' if workflow else 'deterministic native renderer fixture; not a live language-server response')
            return shot
        finally:
            try:
                if job:n.funcs.jobstop(job)
                n.command('qa!')
            except (EOFError,OSError):pass
            n.close();signal.alarm(0);signal.signal(signal.SIGALRM,old)


def isolated_capture(*args, **kwargs):
    # Bound the entire child, including setup and cleanup; failed RPC must not hang the suite.
    with tempfile.TemporaryDirectory() as tmp:
        request=Path(tmp)/'request.json';output=Path(tmp)/'shot.json'
        request.write_text(json.dumps({'args':[str(a) if isinstance(a,Path) else a for a in args],'kwargs':kwargs}))
        process=subprocess.Popen([__import__('sys').executable,__file__,'--worker',str(request),'--output',str(output)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            stdout,stderr=process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.communicate(timeout=5)
            raise TimeoutError('Native interaction capture exceeded 15 seconds')
        if process.returncode:raise RuntimeError((stderr or stdout)[-1500:])
        return json.loads(output.read_text())


def inactive_fzf_pointer(shot, cell):
    # This fixture uses reverse layout with two header rows and a one-cell pointer
    # gutter. fzf draws the same block in canvas color on unselected result rows.
    if shot['case']!='fzf' or cell['col']!=0 or cell['row']<2 or cell['text']!='▌':
        return False
    fg,bg=effective_colors(shot,cell)
    return fg==bg==shot['defaults']['bg']


def assess(shot):
    failures=[];contrasts=[];inactive=0
    for c in shot['cells']:
        if not c['text'].strip():continue
        if inactive_fzf_pointer(shot,c):
            inactive+=1
            continue
        fg,bg=effective_colors(shot,c);p=pair(f'#{fg:06X}',f'#{bg:06X}');contrasts.append(p['contrast'])
        if not p['pass']:failures.append(dict(row=c['row'],col=c['col'],text=c['text'],**p))
    return {'scene':shot['case'],'width':shot['width'],'state':shot['state'],'minimum_contrast':min(contrasts) if contrasts else None,'failures':failures,'inactive_gutter_cells':inactive}


def fzf_oracle(shot,roles):
    bg=int(roles['fg+']['background'][1:],16);fg=int(roles['fg+']['foreground'][1:],16)
    selected=[c for c in shot['cells'] if effective_colors(shot,c)[1]==bg]
    expected={'initial':'3993','\x0e':'3992',FZF_EXACT_QUERY:'3989'}[shot['state']]
    rows={}
    for c in selected:rows.setdefault(c['row'],[]).append(c)
    if not any(expected in ''.join(c['text'] for c in sorted(row,key=lambda c:c['col'])) for row in rows.values()):
        return ['Expected selected history item '+expected+' absent from selection background']
    if not any(c['col']==0 and c['text']=='▌' and effective_colors(shot,c)[0]==fg for c in selected):
        return ['Active history pointer missing or unreadable']
    if any(c['text'].strip() and effective_colors(shot,c)[0]!=fg for c in selected):return ['Selected text foreground differs from generated role']
    return []


def group_pairs(groups):
    normal=groups['Normal'];result={}
    for name,h in groups.items():
        if not h:result[name]={'status':'undefined'};continue
        parent=groups.get('PmenuSel' if name.endswith('Sel') else 'Pmenu',normal) if name.startswith('Pmenu') else normal
        fg=h.get('fg',parent.get('fg',normal['fg']));bg=h.get('bg',parent.get('bg',normal['bg']))
        if h.get('reverse'):fg,bg=bg,fg
        result[name]=pair(f'#{fg:06X}',f'#{bg:06X}')
    return result


def run(entries,out,nvim=None,include_fzf=True):
    out.mkdir(parents=True,exist_ok=True);nvim=nvim or shutil.which('nvim');fzf=shutil.which('fzf')
    records=[];results=[]
    fixture=evaluation_path('fixtures/fzf/history.txt')
    with tempfile.TemporaryDirectory() as tmp:
        input_path=Path(tmp)/'history';input_path.write_bytes(fixture.read_bytes().replace(b'\n',b'\0').replace(b'\\n',b'\n'))
        for entry in entries:
            result={'id':entry['id'],'captures':[],'errors':[],'coverage':{'diagnostics':'native fixture','completion':'native fixture','plugins':'highlight contracts only','fzf':'not evaluated'}};results.append(result)
            print('Interactions: '+entry['id'],flush=True)
            for scene in ('diagnostics','completion','diagnostic-float','documentation','signature','references','inlay'):
                for width in (100,160):
                    try:
                        shot=isolated_capture(entry,width,scene,nvim=nvim);records.append((entry['id'],shot));result['captures'].append(assess(shot));result['group_pairs']=group_pairs(shot['highlights'])
                    except Exception as exc:result['errors'].append(str(exc))
            if entry.get('zsh_theme') and include_fzf:
                options=subprocess.check_output(['zsh','-f','-c','source '+shlex.quote(str(ROOT/entry['zsh_theme']))+'; print -rn -- "$FZF_CTRL_R_OPTS"'],cwd=ROOT,text=True,env={**os.environ,'FZF_DEFAULT_OPTS':'','FZF_CTRL_R_OPTS':''})
                result['coverage']['fzf']='native capture attempted';result['fzf_roles']=fzf_roles(options);result['fzf_provenance']='native shipped shell export'
                if not fzf:result['errors'].append('fzf unavailable')
                else:
                    for width in (100,160):
                        for action in ('','\x0e',FZF_EXACT_QUERY):
                            try:
                                shot=isolated_capture(entry,width,'fzf',input_path,options,fzf,nvim,action);records.append((entry['id'],shot));result['captures'].append(assess(shot));result['errors'].extend(fzf_oracle(shot,result['fzf_roles']))
                            except Exception as exc:result['errors'].append(str(exc))
            else:result['fzf_provenance']='not evaluated: no native upstream fzf adapter declared'
            result['diagnostic_color_collisions']=[name for name in ('DiagnosticError','DiagnosticWarn','DiagnosticInfo','DiagnosticHint') if result.get('group_pairs',{}).get(name,{}).get('foreground')==result.get('group_pairs',{}).get('Normal',{}).get('foreground')]
            result['quality_pass']=not result['errors'] and not any(c['failures'] for c in result['captures']) and all(p['pass'] for p in result.get('fzf_roles',{}).values())
    report={'adapters':entries,'palette_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest(),'results':results,'fzf_version':subprocess.check_output([fzf,'--version'],text=True).strip() if fzf else None,'nvim_version':subprocess.check_output([nvim,'--version'],text=True).splitlines()[0], 'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'render_profile':json.loads((evaluation_path('render-profile.json')).read_text()),'scope':'Native fzf rendered through Neovim terminal emulator; native Neovim diagnostics and completion. Plugin group contracts only, not plugin workflows. No Ghostty pixels, cursor glyph proof, or comfort score.'}
    (out/'report.json').write_text(json.dumps(report,indent=2));(out/'cells.json').write_text(json.dumps(records))
    blocks=''.join('<details><summary>'+html.escape(name+' / '+shot['case']+' / '+str(shot['width'])+' / '+repr(shot['state']))+'</summary>'+render(shot)+'</details>' for name,shot in records)
    (out/'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>Interaction coverage</title><style>body{font:16px system-ui;background:#eee;padding:24px}pre{font:16pt/1.4 "Berkeley Mono Medium",monospace;overflow:auto}summary{padding:12px}</style><h1>Native interaction coverage</h1><p>'+report['scope']+'</p><a href="report.json">Measured results</a>'+blocks)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--themes',nargs='+');parser.add_argument('--skip-fzf',action='store_true');parser.add_argument('--worker',type=Path);args=parser.parse_args()
    if args.worker:
        request=json.loads(args.worker.read_text());args.output.write_text(json.dumps(capture(*request['args'],**request['kwargs'])));raise SystemExit(0)
    entries=json.loads((evaluation_path('themes.json')).read_text())
    if args.themes and set(args.themes)-{e['id'] for e in entries}:parser.error('Unknown theme')
    entries=[e for e in entries if not args.themes or e['id'] in args.themes]
    r=run(entries,args.output,include_fzf=not args.skip_fzf);raise SystemExit(int(any(x['errors'] for x in r['results'])))
