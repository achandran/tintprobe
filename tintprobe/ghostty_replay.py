from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Present recorded native Codex renderer cells in Ghostty, preserving modifiers.

This closes the terminal-pixel layer of deterministic renderer replay. It is
explicitly not a live model session or an app-server end-to-end test.
"""
import hashlib
import json
from pathlib import Path

from tintprobe.codex_native import color
from tintprobe.context import ROOT, load_palette


def fixtures(output,source):
    source=Path(source)
    report=json.loads(source.with_name('report.json').read_text())
    theme=hashlib.sha256((port_path('codex_theme')).read_bytes()).hexdigest()
    if report.get('status')!='pass' or report.get('theme_sha256')!=theme:
        raise ValueError('Codex replay is not a passing capture of the current exported theme')
    palette=load_palette()
    foreground=palette['foregrounds']['text'];background=palette['backgrounds']['base']
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    records=[]
    for shot in json.loads(source.read_text()):
        name='codex-'+shot['file']+'-'+str(shot['width'])
        cells={(c['row'],c['col']):c for c in shot['cells']}
        height=max(r for r,c in cells)+1
        if shot['width']>120 or height>36:raise ValueError('Native replay exceeds the fixture viewport; pagination is not implemented')
        snapshot=[];payload=''
        for row in range(height):
            for col in range(120):
                c=cells.get((row,col),{'text':' ','fg':'Reset','bg':'Reset','modifiers':'NONE'})
                modifiers=set(c['modifiers'].split(' | '))
                unsupported=modifiers-{'NONE','BOLD','DIM','ITALIC','UNDERLINED','REVERSED'}
                if unsupported:raise ValueError('Unsupported native modifiers: '+str(unsupported))
                fg=color(c['fg'],palette,foreground);bg=color(c['bg'],palette,background)
                if 'REVERSED' in modifiers:fg,bg=bg,fg
                rgb=lambda h:';'.join(str(int(h[i:i+2],16)) for i in (1,3,5))
                codes=['0','38;2;'+rgb(fg),'48;2;'+rgb(bg)]
                for modifier,code in [('BOLD','1'),('DIM','2'),('ITALIC','3'),('UNDERLINED','4')]:
                    if modifier in modifiers:codes.append(code)
                payload+='\x1b['+';'.join(codes)+'m'+c['text']
                snapshot.append({'row':row+2,'column':col,'text':c['text'],'fg':fg,'bg':bg,
                                 'bold':'BOLD' in modifiers,'underline':'UNDERLINED' in modifiers,'dim':'DIM' in modifiers})
            payload+='\x1b[0m\n'
        path=output/(name+'.ansi');path.write_text(payload)
        oracle=output/(name+'.cells.json')
        oracle.write_text(json.dumps({'scene':name,'cells':snapshot,'rows':height+2,'columns':120,
                                     'cursor':[-1,-1],'source':'Recorded native Codex renderer cells; RGB/SGR presentation in Ghostty',
                                     'source_sha256':source_hash,'source_revision':report['source_revision']}))
        records.append({'id':name,'kind':'native-codex-replay','status':'prepared','ansi':path.name,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'cells_sha256':hashlib.sha256(oracle.read_bytes()).hexdigest(),
                        'source_sha256':source_hash,'theme_sha256':theme,
                        'scope':'Native renderer cell replay displayed in Ghostty, not live app-server or model interaction'})
    return records
