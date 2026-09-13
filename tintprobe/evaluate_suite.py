from tintprobe.context import workflow
from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""One command for supported theme comparisons and native Codex evaluations."""
import argparse,json,subprocess,sys,html
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import shutil
from tintprobe.context import ROOT
from tintprobe.codex_theme_adapters import prepare
from tintprobe.codex_native import run_native
from tintprobe.codex_flows import run as run_flows
from tintprobe.agent_gates import assess
from tintprobe.aesthetic_score import evaluate as evaluate_aesthetic


def execution_failed(report):
    return (any(s['status']!='pass' and s.get('reason')!='Not requested' for s in report['stages'].values())
            or any(t.get('status')=='unavailable_or_error' or not t.get('codex_diff',{}).get('captures') for t in report['themes']))


def interaction_status(result):
    errors=[error for row in result['results'] for error in row.get('errors',[])]
    if not errors:return 'pass'
    if all('fzf did not render a live result list: operation not permitted' in e for e in errors):return 'blocked'
    return 'fail'


def workflow_status(result):
    rows=result.get('results',[])
    failed=[r for r in rows if not r.get('pass')]
    if failed and all(r.get('status')=='blocked' for r in failed):return 'blocked'
    return 'pass' if result.get('pass') and rows else 'fail'


def run_workflow(report,name,callback):
    try:
        result=callback()
        report['stages'][name]={'status':workflow_status(result),'gallery':name+'/gallery.html',
            'passed':sum(bool(r.get('pass')) for r in result.get('results',[])),
            'total':len(result.get('results',[]))}
    except (FileNotFoundError,NotADirectoryError) as exc:
        report['stages'][name]={'status':'blocked','reason':str(exc)}
    except Exception as exc:
        report['stages'][name]={'status':'fail','reason':str(exc)}


def finalize(report,out,strict):
    execution_bad=execution_failed(report)
    quality_bad=False
    if strict:
        for stage in ('neovim','python'):
            path=out/stage/'scorecard.json'
            if report['stages'].get(stage,{}).get('status')=='blocked':
                report['stages'][stage]['quality_status']='unverified'
                quality_bad=True
                continue
            failed=not path.exists() or any(t['gates']['failures'] for t in json.loads(path.read_text())['results'])
            report['stages'].setdefault(stage,{'status':'untested'})['quality_status']='fail' if failed else 'pass'
            quality_bad |= failed
        interaction_bad=not report.get('interactions',{}).get('quality_pass',False)
        interaction_stage=report['stages'].setdefault('interactions',{'status':'untested'})
        interaction_stage['quality_status']='unverified' if interaction_stage['status']=='blocked' else ('fail' if interaction_bad else 'pass')
        quality_bad |= interaction_bad
        quality_bad |= any(t.get('codex_diff',{}).get('status')!='pass' or t.get('agent_gates',{}).get('status')!='pass' for t in report['themes'])
        if 'codex-ui' in report['stages']:
            quality_bad |= report['stages']['codex-ui'].get('quality_status') != 'pass'
    report['required_execution_status']='fail' if execution_bad else 'complete'
    report['acceptance_status']='fail' if execution_bad or quality_bad else 'pass'
    report['strict_gates']=strict
    return execution_bad or quality_bad


def write_index(out,report):
    rows=[];details=[]
    for t in report['themes']:
        name=html.escape(t['id'])
        aesthetic=t.get('aesthetic',{'status':'not evaluated','score':None})
        details.append('<details><summary>'+name+': Formex fidelity '+html.escape(str(aesthetic.get('score')) if aesthetic.get('score') is not None else aesthetic['status'])+'</summary><pre>'+html.escape(json.dumps(aesthetic,indent=2))+'</pre></details>')
        if 'adapter' not in t:rows.append(f'<tr><td>{name}</td><td colspan="3">{html.escape(t["reason"])}</td></tr>');continue
        rows.append(f'<tr><td>{name}</td><td>{html.escape(t["adapter"]["provenance"])}</td><td><a href="{t["diff_gallery"]}">{t["codex_diff"]["status"]}: diffs</a></td><td><a href="{t["flow_gallery"]}">{t["agent_gates"]["status"]}: flows</a></td></tr>')
        stage_rows=''.join(f'<tr><td>{html.escape(g["stage"])}</td><td>{g["width"]}</td><td>{g["minimum_contrast"]}</td><td>{len(g["failures"])}</td><td>{g["dim_cells_unverified"]}</td></tr>' for g in t['agent_gates']['stages'])
        details.append(f'<details><summary>{name}: agent-stage measurements</summary><p>Whole frame including accumulated history. Required-content fragment findings are in <a href="codex/{t["id"]}/agent-gates.json">agent-gates.json</a>.</p><table><tr><th>Stage</th><th>Width</th><th>Minimum contrast</th><th>Failed cells</th><th>Dim cells (unverified)</th></tr>{stage_rows}</table></details>')

    stage_table='<h2>Stage coverage</h2><table>'+''.join('<tr><td>'+html.escape(name)+'</td><td>'+html.escape(stage['status']+(' / quality '+stage['quality_status'] if stage.get('quality_status') else ''))+'</td><td>'+('<a href="'+html.escape(stage['gallery'],quote=True)+'">Gallery</a>' if stage.get('gallery') and (out/stage['gallery']).exists() else html.escape(stage.get('reason','')) )+'</td></tr>' for name,stage in report['stages'].items())+'</table>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Theme suite</title><style>body{font:16px/1.5 system-ui;padding:30px}td,th{padding:12px;border-bottom:1px solid #ccc}</style><h1>Combined evaluation</h1><p>Supported stages completed separately from quality gates. Full coverage remains incomplete: See stage coverage for measured Ghostty command, cursor, selection, and live Neovim cases. Claude Code and comfort remain unverified. Native event replay, not live model sessions.</p><p><a href="neovim/scorecard.html">Neovim gates</a> · <a href="python/scorecard.html">Python Tree-sitter/LSP gates</a> · <a href="interactions/gallery.html">fzf / diagnostics / completion</a> · <a href="evaluator-validation/index.html">Evaluator validation</a> · <a href="report.json">Full evidence</a></p><table><tr><th>Theme</th><th>Codex adapter provenance</th><th>Diff gates</th><th>Flow gates</th></tr>'+''.join(rows)+'</table>'+stage_table+'<p>Converted ports test our explicit mapping, not an upstream author’s Codex implementation.</p>'+''.join(details))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codex-source',type=Path,required=True);p.add_argument('--python-source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=evaluation_path('themes.json'));p.add_argument('--output',type=Path,default=ROOT/'evaluation/results/suite')
    p.add_argument('--ghostty',action='store_true',help='Prepare terminal command fixtures and track native Ghostty coverage')
    p.add_argument('--ghostty-capture',action='store_true',help='Run native macOS Ghostty capture; requires authorized UI access')
    p.add_argument('--fresh-run',action='store_true',help='Write to a unique run folder to avoid stale evidence')
    p.add_argument('--pickers',action='store_true',help='Gate native picker/completion workflows')
    p.add_argument('--python-tools',action='store_true',help='Gate actual pytest and debugpy plugin workflows')
    p.add_argument('--git-review',action='store_true',help='Gate pinned native Git plugin screens (fetch dependencies first)')
    p.add_argument('--installed-workflows',action='store_true',help='Also gate project-provided installed plugin workflows')
    p.add_argument('--skip-fzf',action='store_true');p.add_argument('--themes',nargs='+');p.add_argument('--strict-gates',action='store_true');p.add_argument('--nvim',default=shutil.which('nvim'))
    a=p.parse_args();out=a.output.resolve()
    if a.fresh_run:out=out/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=True)
    print('Evaluation output: '+str(out),flush=True)
    entries=json.loads(a.manifest.read_text())
    if a.themes:
        if set(a.themes)-{x['id'] for x in entries}:p.error('Unknown theme')
        entries=[x for x in entries if x['id'] in a.themes]
    report={'stages':{},'themes':[],'coverage':{'ghostty':'not evaluated: no native Ghostty capture stage','claude_code':'not evaluated','long_session_comfort':'not evaluated','full_target_coverage':'incomplete'}}
    def checkpoint():
        (out/'report.json').write_text(json.dumps(report,indent=2));write_index(out,report)
    for name,enabled in [('pickers',a.pickers),('python-tools',a.python_tools),('git-review',a.git_review),('installed-workflows',a.installed_workflows)]:
        report['stages'][name]={'status':'untested','reason':'Pending' if enabled else 'Not requested'}
    if not a.nvim:
        report['stages']['neovim']={'status':'blocked','reason':'Neovim executable not found'}
        report['required_execution_status']='fail';report['acceptance_status']='fail';checkpoint();return 1
    checkpoint()
    for name,extra in [('neovim',[]),('python',['--python-source',str(a.python_source.resolve())])]:
        print('Stage: '+name,flush=True)
        cmd=[sys.executable,str(script_path('compare_themes.py')),'--manifest',str(a.manifest.resolve()),'--output',str(out/name),'--nvim',a.nvim,'--themes',*[e['id'] for e in entries],*extra]
        missing=[str((ROOT/path).resolve()) for e in entries for path in e['paths'] if not (ROOT/path).is_dir()]
        if name=='python' and not a.python_source.is_dir():missing.append(str(a.python_source.resolve()))
        if missing:
            report['stages'][name]={'status':'blocked','reason':'Missing dependencies: '+', '.join(sorted(set(missing)))+'. Run make setup-evaluation.'}
            checkpoint();continue
        result=subprocess.run(cmd,cwd=ROOT)
        report['stages'][name]={'status':'pass' if result.returncode==0 else 'fail','gallery':name+'/gallery.html','scorecard':name+'/scorecard.html'}
        checkpoint()
    for entry in entries:
        name=entry['id'];print('Codex: '+name,flush=True);folder=out/'codex'/name
        try:
            if not shutil.which('cargo'):raise FileNotFoundError('Cargo is required: install the toolchain in codex-rs/rust-toolchain.toml, or set RUST_RUNTIME in evaluation/local.mk (see docs/development.md).')
            if not a.codex_source.is_dir():raise FileNotFoundError('Missing pinned Codex source; run make setup-evaluation.')
            theme,palette,meta=prepare(entry,folder/'adapter',a.nvim)
            diff=run_native(a.codex_source.resolve(),folder/'diff',theme,palette)
            flow=run_flows(a.codex_source.resolve(),folder/'flows',theme,palette)
            records=json.loads((folder/'flows/codex-cells.json').read_text());gates=assess(records,palette)
            (folder/'agent-gates.json').write_text(json.dumps(gates,indent=2))
            report['stages']['codex-'+name]={'status':'pass' if diff.get('captures') and flow.get('captures') else 'fail','quality_status':'pass' if diff['status']=='pass' and gates['status']=='pass' else 'fail'}
            report['themes'].append({'id':name,'aesthetic':evaluate_aesthetic(entry,palette,records),'adapter':meta,'codex_diff':diff,'codex_flows':flow,'agent_gates':gates,'flow_gallery':f'codex/{name}/flows/codex-gallery.html','diff_gallery':f'codex/{name}/diff/codex-gallery.html'})
        except FileNotFoundError as exc:
            report['stages']['codex-'+name]={'status':'blocked','reason':str(exc)}
            report['themes'].append({'id':name,'status':'unavailable_or_error','reason':str(exc)})
        except Exception as exc:
            report['stages']['codex-'+name]={'status':'fail','reason':str(exc)}
            report['themes'].append({'id':name,'status':'unavailable_or_error','reason':str(exc)})
        checkpoint()
    from tintprobe.evaluate_interactions import run as run_interactions
    try:
        from tintprobe.compare_themes import check_adapter
        for entry in entries:check_adapter(entry)
        interactions=run_interactions(entries,out/'interactions',a.nvim,include_fzf=not a.skip_fzf)
        report['interactions']={'gallery':'interactions/gallery.html','report':'interactions/report.json','quality_pass':all(r['quality_pass'] for r in interactions['results'])}
        report['stages']['interactions']={'status':interaction_status(interactions),'gallery':'interactions/gallery.html'}
    except Exception as exc:
        report['stages']['interactions']={'status':'blocked' if isinstance(exc,FileNotFoundError) else 'fail','reason':str(exc)}
    checkpoint()
    from tintprobe.validate_evaluator import run as validate_evaluator
    try:
        validation=validate_evaluator(out/'evaluator-validation')
        report['stages']['evaluator-validation']={'status':'pass' if validation['pass'] else 'fail','gallery':'evaluator-validation/index.html'}
    except Exception as exc:
        report['stages']['evaluator-validation']={'status':'blocked' if isinstance(exc,FileNotFoundError) else 'fail','reason':str(exc)}
    checkpoint()
    if a.pickers:
        run_workflow(report,'pickers',lambda:workflow('evaluate_pickers')(out/'pickers'));checkpoint()
    from tintprobe.codex_ui import run as run_codex_ui
    try:
        ui = run_codex_ui(a.codex_source, out/'codex-ui')
        report['stages']['codex-ui'] = {'status': 'pass' if ui['captures'] else 'fail',
                                      'quality_status': ui['status'], 'captures': ui['captures'],
                                      'gallery': 'codex-ui/codex-gallery.html',
                                      'remaining_gaps': ui['remaining_gaps']}
    except Exception as exc:
        report['stages']['codex-ui'] = {'status': 'blocked' if isinstance(exc, FileNotFoundError) else 'fail', 'reason': str(exc)}
    checkpoint()
    if a.python_tools:
        run_workflow(report,'python-tools',lambda:workflow('evaluate_python_tools')(out/'python-tools'));checkpoint()
    if a.git_review:
        run_workflow(report,'git-review',lambda:workflow('evaluate_git_review')(out/'git-review'));checkpoint()
    if a.installed_workflows:
        run_workflow(report,'installed-workflows',lambda:workflow('evaluate_installed_workflows')(out/'installed-workflows',Path.home()/'.config/nvim/init.lua',Path.home()/'.local/share/nvim/lazy/lazy.nvim'));checkpoint()
    if a.ghostty or a.ghostty_capture:
        from tintprobe.evaluate_ghostty import prepare as prepare_ghostty
        try:
            native_cells=out/'codex'/DEFAULT_THEME/'flows/codex-cells.json'
            ghostty=prepare_ghostty(out/'ghostty', a.ghostty_capture,codex_cells=native_cells if native_cells.exists() else None)
            report['stages']['ghostty']={'status':ghostty['status'],'reason':ghostty['reason'],'gallery':'ghostty/gallery.html'}
            report['coverage']['ghostty']=ghostty['coverage']
        except Exception as exc:
            report['stages']['ghostty']={'status':'fail','reason':str(exc)}
        checkpoint()
    failures=finalize(report,out,a.strict_gates)
    (out/'report.json').write_text(json.dumps(report,indent=2))
    write_index(out,report)
    print('Acceptance: '+report['acceptance_status']+'; report: '+str(out/'index.html'),flush=True)
    for name,stage in report['stages'].items():
        print(name+': '+stage['status']+(' / quality '+stage['quality_status'] if stage.get('quality_status') else ''),flush=True)
    return int(failures)

if __name__=='__main__':raise SystemExit(main())
