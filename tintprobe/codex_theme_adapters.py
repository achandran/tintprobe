from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Explicit, reproducible Neovim-to-tmTheme conversions for comparison only."""
import json,plistlib,subprocess,hashlib,tempfile
from pathlib import Path
from tintprobe.compare_themes import check_adapter
from tintprobe.context import ROOT,load_palette

SCOPES={'comment':'Comment','string':'String','constant.numeric':'Number','constant.language':'Boolean','keyword':'Keyword','storage.type':'Type','entity.name.function':'Function','entity.name.type':'Type','variable.parameter':'Identifier','support.function':'Function','markup.inserted':'DiffAdd','markup.deleted':'DiffDelete','markup.changed':'DiffText'}

def prepare(adapter,output,nvim):
    output.mkdir(parents=True,exist_ok=True)
    resolved=check_adapter(adapter)
    if adapter.get('codex_theme'):
        path=ROOT/adapter['codex_theme'];palette=load_palette(adapter['id']);kind='project-provided TextMate export'
    else:
        with tempfile.TemporaryDirectory(prefix='codex-theme-') as tmp:
            destination=Path(tmp)/'colors.json'
            lua='\n'.join('vim.opt.rtp:prepend('+json.dumps(str(p))+')' for p in resolved['paths'])
            lua+='\nvim.o.termguicolors=true;vim.o.background='+json.dumps(adapter.get('background','light'))+'\n'+adapter['setup']
            lua+='\nlocal out={groups={},ansi={}}\n'
            for group in sorted(set(SCOPES.values())|{'Normal'}):lua+=f'out.groups.{group}=vim.api.nvim_get_hl(0,{{name="{group}",link=false}})\n'
            lua+='for i=0,15 do out.ansi[tostring(i)]=vim.g["terminal_color_"..i] end\n'
            lua+='vim.fn.writefile({vim.json.encode(out)},'+json.dumps(str(destination))+')\n'
            script=Path(tmp)/'export.lua';script.write_text(lua)
            subprocess.run([nvim,'--headless','-n','-u','NONE','-i','NONE','-l',str(script)],check=True,capture_output=True,timeout=30)
            data=json.loads(destination.read_text())
        normal=data['groups']['Normal'];fg=f'#{normal["fg"]:06X}';bg=f'#{normal["bg"]:06X}'
        if len(data['ansi'])!=16:raise ValueError('Theme must define all sixteen terminal colors')
        palette={'foregrounds':{'text':fg},'backgrounds':{'base':bg},'ansi':{str(i):data['ansi'][str(i)] for i in range(16)}}
        settings=[{'settings':{'foreground':fg,'background':bg}}]
        for scope,group in SCOPES.items():
            h=data['groups'][group];a=h.get('fg',normal['fg']);b=h.get('bg')
            if h.get('reverse'):a,b=b or normal['bg'],a
            style={'foreground':f'#{a:06X}'}
            if b is not None:style['background']=f'#{b:06X}'
            # Force explicit diff backgrounds, as required by the native adapter.
            if scope.startswith('markup.'):style.setdefault('background',bg)
            styles=[name for name in ('bold','italic','underline') if h.get(name)]
            if styles:style['fontStyle']=' '.join(styles)
            settings.append({'scope':scope,'settings':style})
        path=output/'theme.tmTheme';path.write_bytes(plistlib.dumps({'name':adapter['id']+' (evaluation conversion)','settings':settings}))
        (output/'resolved-neovim.json').write_text(json.dumps(data,indent=2))
        kind='evaluation conversion from pinned Neovim highlights; not an upstream Codex port'
    metadata={'id':adapter['id'],'provenance':kind,'mapping_version':1,'source_adapter':adapter,'theme_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (output/'adapter.json').write_text(json.dumps(metadata,indent=2));(output/'terminal-palette.json').write_text(json.dumps(palette,indent=2))
    return path,palette,metadata
