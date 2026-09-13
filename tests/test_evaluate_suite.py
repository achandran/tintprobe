from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.evaluate_suite import execution_failed
class SuiteStatus(unittest.TestCase):
    def test_quality_failure_is_not_execution_failure(self):
        r={'stages':{'neovim':{'status':'pass'}},'themes':[{'codex_diff':{'captures':60,'status':'fail'}}]}
        self.assertFalse(execution_failed(r))
    def test_missing_native_capture_is_execution_failure(self):
        r={'stages':{'neovim':{'status':'pass'}},'themes':[{'codex_diff':{'status':'fail'}}]}
        self.assertTrue(execution_failed(r))
    def test_failed_neovim_stage_cannot_be_masked(self):
        self.assertTrue(execution_failed({'stages':{'neovim':{'status':'fail'}},'themes':[]}))

    def test_blocked_workflow_is_not_pass(self):
        from tintprobe.evaluate_suite import workflow_status
        self.assertEqual(workflow_status({'pass':False,'results':[{'pass':False,'status':'blocked'}]}),'blocked')
        self.assertEqual(workflow_status({'pass':False,'results':[{'pass':False,'status':'blocked'},{'pass':False,'status':'fail'}]}),'fail')

    def test_missing_dependency_is_recorded(self):
        from tintprobe.evaluate_suite import run_workflow
        r={'stages':{},'themes':[]}
        def missing():raise FileNotFoundError('dependency absent')
        run_workflow(r,'native',missing)
        self.assertEqual(r['stages']['native']['status'],'blocked')
        self.assertTrue(execution_failed(r))

    def test_empty_workflow_cannot_pass(self):
        from tintprobe.evaluate_suite import workflow_status
        self.assertEqual(workflow_status({'pass':True,'results':[]}),'fail')

    def test_gallery_lists_native_profiles(self):
        import tempfile
        from tintprobe.evaluate_suite import write_index
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'pickers').mkdir();(out/'pickers/gallery.html').write_text('fixture')
            write_index(out,{'themes':[],'stages':{'pickers':{'status':'pass','gallery':'pickers/gallery.html'},'codex':{'status':'blocked','reason':'cargo absent'}}})
            page=(out/'index.html').read_text()
            self.assertIn('pickers/gallery.html',page)
            self.assertIn('cargo absent',page)

    def test_quality_gate_failure_rejects_successful_capture(self):
        import json,tempfile
        from tintprobe.evaluate_suite import finalize
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            for name in ('neovim','python'):
                (out/name).mkdir();(out/name/'scorecard.json').write_text(json.dumps({'results':[{'gates':{'failures':['contrast'] if name=='neovim' else []}}]}))
            r={'stages':{'neovim':{'status':'pass'},'python':{'status':'pass'},'interactions':{'status':'pass'}},'interactions':{'quality_pass':True},'themes':[{'codex_diff':{'captures':1,'status':'pass'},'agent_gates':{'status':'pass'}}]}
            self.assertTrue(finalize(r,out,True))
            self.assertEqual(r['required_execution_status'],'complete')
            self.assertEqual(r['acceptance_status'],'fail')
            self.assertEqual(r['stages']['neovim']['quality_status'],'fail')

    def test_permission_failure_is_blocked_not_silently_passed(self):
        from tintprobe.evaluate_suite import interaction_status
        error='fzf did not render a live result list: operation not permitted'
        r={'results':[{'errors':[error]}]}
        self.assertEqual(interaction_status(r),'blocked')
        r['results'].append({'errors':['Unexpected rendering error']})
        self.assertEqual(interaction_status(r),'fail')

    def test_missing_theme_dependency_is_actionable(self):
        import tempfile
        from tintprobe.compare_themes import check_adapter
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, 'Missing theme dependency'):
                check_adapter({'paths':[str(Path(tmp)/'absent')], 'pins':{}})

    def test_missing_dependencies_do_not_prevent_ghostty_report(self):
        import json,tempfile
        from unittest.mock import patch
        import tintprobe.evaluate_suite as evaluate_suite
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'themes.json';out=root/'out'
            manifest.write_text(json.dumps([{'id':'fixture','paths':[str(root/'absent')]}]))
            argv=['suite','--manifest',str(manifest),'--output',str(out),'--codex-source',str(root/'codex'),
                  '--python-source',str(root/'python'),'--nvim','nvim','--ghostty']
            ghostty={'status':'blocked','reason':'capture unavailable','coverage':{'native_pixels':'blocked'}}
            with patch.object(sys,'argv',argv), patch('tintprobe.evaluate_suite.shutil.which',return_value=None), \
                 patch('tintprobe.evaluate_interactions.run',side_effect=FileNotFoundError('missing dependency')), \
                 patch('tintprobe.validate_evaluator.run',side_effect=FileNotFoundError('missing dependency')), \
                 patch('tintprobe.evaluate_ghostty.prepare',return_value=ghostty):
                self.assertEqual(evaluate_suite.main(),1)
            report=json.loads((out/'report.json').read_text())
            self.assertEqual(report['stages']['neovim']['status'],'blocked')
            self.assertEqual(report['stages']['evaluator-validation']['status'],'blocked')
            self.assertEqual(report['stages']['ghostty']['status'],'blocked')
            self.assertTrue((out/'index.html').exists())


def test_blocked_renderers_do_not_claim_quality_failure(tmp_path):
    from tintprobe.evaluate_suite import finalize
    report={'stages':{name:{'status':'blocked'} for name in ('neovim','python','interactions')},'themes':[]}
    assert finalize(report,tmp_path,True)
    assert all(s['quality_status']=='unverified' for s in report['stages'].values())
    assert report['acceptance_status']=='fail'


def test_unverified_stock_ui_contrast_blocks_strict_acceptance(tmp_path):
    import json
    from tintprobe.evaluate_suite import finalize
    for name in ('neovim', 'python'):
        (tmp_path/name).mkdir()
        (tmp_path/name/'scorecard.json').write_text(json.dumps({'results': []}))
    report = {'stages': {name: {'status': 'pass'} for name in ('neovim', 'python', 'interactions')},
              'themes': [], 'interactions': {'quality_pass': True}}
    report['stages']['codex-ui'] = {'status': 'pass', 'captures': 48, 'quality_status': 'unverified'}
    assert finalize(report, tmp_path, True)
    assert report['required_execution_status'] == 'complete'
    assert report['acceptance_status'] == 'fail'
