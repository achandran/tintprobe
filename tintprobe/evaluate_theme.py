from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Offline corpus + native Neovim UI capture. Missing native Codex is never a pass."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import signal
import tempfile
import pynvim
from tintprobe.context import ROOT, load_palette, wcag
from tintprobe.evaluation_checks import state_failures, compare_reports


def capture(case, width, state, nvim_bin, kanso, adapter=None, python_runtime=None):
    def timed_out(*_): raise TimeoutError('Neovim UI capture timed out')
    signal.signal(signal.SIGALRM, timed_out); signal.alarm(45 if python_runtime else 10)
    sandbox = tempfile.TemporaryDirectory(prefix='ithilien-nvim-')
    n = pynvim.attach('child', argv=['env','XDG_STATE_HOME='+sandbox.name,'XDG_CACHE_HOME='+sandbox.name,nvim_bin, '--embed', '--headless', '-n', '-u', 'NONE', '-i', 'NONE'])
    grid, attrs, defaults = {}, {}, {}
    syntax_groups = []
    highlights = {}
    regions = []
    overlay = {}
    runtime_evidence = None
    attr_info = {}
    cursor = None
    def notify(name, args):
        nonlocal cursor
        if name == 'evaluation_done':
            n.stop_loop(); return
        if name != 'redraw': return
        for event in args:
            for item in event[1:]:
                if event[0] == 'default_colors_set': defaults.update(fg=item[0], bg=item[1])
                elif event[0] == 'hl_attr_define':
                    attrs[item[0]] = item[1]
                    attr_info[item[0]] = item[3] if len(item)>3 else []
                elif event[0] == 'grid_cursor_goto': cursor = item[1:3]
                elif event[0] == 'grid_clear': grid.clear()
                elif event[0] == 'grid_line':
                    _, row, col, cells, *_ = item
                    attr = 0
                    for cell in cells:
                        if len(cell) > 1: attr = cell[1]
                        for _ in range(cell[2] if len(cell) > 2 else 1):
                            grid[row, col] = (cell[0], attr); col += 1
    def setup():
        nonlocal syntax_groups, highlights, regions, overlay, runtime_evidence
        n.ui_attach(width, 30, rgb=True, ext_linegrid=True, ext_hlstate=True)
        selected = adapter or default_adapter()
        background = selected.get('background', 'light')
        if background not in ('light', 'dark'): raise ValueError('Invalid adapter background')
        n.command('set termguicolors splitright background='+background)
        for path in selected['paths']: n.exec_lua('vim.opt.rtp:prepend(...)',str(path))
        n.exec_lua(selected['setup'])
        highlights = n.exec_lua("local out={}; for _,name in ipairs({'Normal','Visual','Search','DiffAdd','DiffDelete','DiffChange','DiffText'}) do out[name]=vim.api.nvim_get_hl(0,{name=name,link=false}) end; return out")
        n.command('filetype on'); n.command('syntax on')
        before = evaluation_path(case['before']); after = evaluation_path(case['after'])
        # Keep native filename labels independent of checkout/install paths.
        n.command('cd '+n.funcs.fnameescape(str(before.parent)))
        n.command('edit '+n.funcs.fnameescape(os.path.relpath(before, before.parent)))
        n.command('setlocal filetype='+case['filetype'])
        n.command('diffthis')
        n.command('vsplit '+n.funcs.fnameescape(os.path.relpath(after, before.parent)))
        n.command('setlocal filetype='+case['filetype'])
        n.command('diffthis')
        n.command('setlocal nofoldenable')
        n.command('windo setlocal nofoldenable')
        if selected.get('after_diff'): n.exec_lua(selected['after_diff'])
        if python_runtime:
            runtime_evidence=n.exec_lua((evaluation_path('python-runtime.lua')).read_text(),str(python_runtime),shutil.which('basedpyright-langserver') or str(Path(sys.executable).parent/'basedpyright-langserver'))
        if adapter and adapter.get('evaluation_override'):
            n.exec_lua(adapter['evaluation_override'])
            highlights=n.exec_lua('local out={};for _,name in ipairs(...) do out[name]=vim.api.nvim_get_hl(0,{name=name,link=false}) end;return out',list(highlights))
        if state=='syntax':
            n.command('only');n.command('diffoff');n.command('set laststatus=0')
        n.command('normal! gg')
        if state == 'search' or 'search' in state:
            n.funcs.setreg('/', case.get('search','return\\|font\\|println')); n.command('set hlsearch')
        if state.startswith('selection'):
            n.command('normal! '+str(case.get('selection_line',2))+'G0')
            keys={'selection':'V2j','selection-char':'v3l','selection-block':'\x163l2j'}.get(state,'V2j')
            n.command('normal! '+keys)
        if 'diagnostic' in state:
            n.exec_lua("local ns=vim.api.nvim_create_namespace('overlap-fixture');vim.diagnostic.config({virtual_text=true,underline=true});vim.diagnostic.set(ns,0,{{lnum=vim.fn.line('.')-1,col=0,severity=1,message='overlap diagnostic'}})")
        overlay = n.exec_lua("""
            local a=vim.fn.getpos('v');local b=vim.fn.getpos('.')
            return {diagnostic_count=#vim.diagnostic.get(0),search_pattern=vim.fn.getreg('/'),mode=vim.fn.mode(),anchor={a[2],a[3]},finish={b[2],b[3]},
            anchor_vcol=vim.fn.virtcol('v',true)[1],finish_vcol=vim.fn.virtcol('.',true)[2],selection=vim.o.selection}
        """)
        syntax_groups = n.exec_lua("local groups = {}; for row,line in ipairs(vim.api.nvim_buf_get_lines(0,0,-1,false)) do for col=1,#line do local name=vim.fn.synIDattr(vim.fn.synID(row,col,1),'name'); if name ~= '' then groups[name]=true end end end; return vim.tbl_keys(groups)")
        regions = n.exec_lua("""
            local out={}
            for _,win in ipairs(vim.api.nvim_list_wins()) do
                vim.api.nvim_win_call(win,function()
                    local lines=vim.api.nvim_buf_get_lines(0,0,-1,false)
                    for row,line in ipairs(lines) do
                        local matches={}; local offset=0
                        if vim.o.hlsearch and vim.fn.getreg('/')~='' then
                            while offset<=#line do
                                local m=vim.fn.matchstrpos(line,vim.fn.getreg('/'),offset)
                                if m[2]<0 then break end
                                matches[#matches+1]={m[2]+1,m[3]};offset=math.max(m[3],offset+1)
                            end
                        end
                        local byte=1
                        for _,char in ipairs(vim.fn.split(line,[=[\\zs]=])) do
                            local pos=vim.fn.screenpos(win,row,byte)
                            if pos.row>0 and pos.col>0 then
                                local matched=false; for _,m in ipairs(matches) do if byte>=m[1] and byte<=m[2] then matched=true end end
                                local group=vim.fn.synIDattr(vim.fn.diff_hlID(row,byte),'name')
                                for col=pos.col,math.max(pos.col,pos.endcol) do
                                    out[#out+1]={row=pos.row-1,col=col-1,search_match=matched,source_line=row,source_byte=byte,vcol=vim.fn.virtcol({row,byte},true),side=vim.api.nvim_buf_get_name(0):find(".before.",1,true) and "before" or "after",group=group,text=char}
                                end
                            end
                            byte=byte+#char
                        end
                    end
                end)
            end
            return out
        """)
        n.command('redraw!')
        n.exec_lua("local ch=...; vim.defer_fn(function() vim.cmd('redraw!'); vim.rpcnotify(ch,'evaluation_done') end,100)",n.channel_id)
    try:
        n.run_loop(None, notify, setup_cb=setup)
        result = {'case':case['id'],'width':width,'state':state,'python_runtime':runtime_evidence,'cursor':cursor,'overlay':overlay,'attr_info':attr_info,'regions':regions,'highlights':highlights,'syntax_groups':syntax_groups,'require_syntax':case.get('require_syntax',False),'defaults':defaults,'attrs':attrs,
                  'cells':[{'row':r,'col':c,'text':t,'attr':a} for (r,c),(t,a) in sorted(grid.items())]}
        assert result['cells'], 'No native UI cells received'
        return result
    finally:
        try: n.command('qa!')
        except (EOFError, OSError): pass
        n.close()
        signal.alarm(0)
        sandbox.cleanup()
