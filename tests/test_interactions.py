from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
"""Failure-sensitive checks for contextual role and native capture oracles."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.evaluate_interactions import fzf_roles,fzf_oracle,pair,group_pairs
class Interactions(unittest.TestCase):
    def test_foreground_and_background_roles_are_not_interchangeable(self):
        r=fzf_roles('--color=light,bg:#FAFAF8,fg:#000000,bg+:#B8595C,fg+:#000000,prompt:#B8595C')
        self.assertTrue(r['fg+']['pass']);self.assertFalse(r['prompt']['pass'])
    def test_no_rounding_at_gate(self):
        self.assertFalse(pair('#000000','#8B3037')['pass'])
    def test_missing_selection_cannot_pass(self):
        s={'state':'initial','cells':[],'attrs':{},'defaults':{'fg':0,'bg':0xffffff}}
        self.assertTrue(fzf_oracle(s,{'fg+':pair('#000000','#B8595C')}))
    def test_wrong_selected_item_cannot_pass(self):
        s={'state':'initial','cells':[{'row':0,'col':0,'text':'3992','attr':1}], 'attrs':{1:{'foreground':0,'background':0xb8595c}},'defaults':{'fg':0,'bg':0xffffff}}
        self.assertTrue(fzf_oracle(s,{'fg+':pair('#000000','#B8595C')}))
        s['cells'][0]['text']='3993';s['cells'][0]['col']=2;s['cells'].append({'row':0,'col':0,'text':'▌','attr':1});self.assertEqual(fzf_oracle(s,{'fg+':pair('#000000','#B8595C')}),[])
    def test_popup_details_use_popup_background(self):
        g={'Normal':{'fg':0,'bg':0xffffff},'PmenuSel':{'fg':0xffffff,'bg':0},'PmenuKindSel':{'fg':0x333333}}
        self.assertFalse(group_pairs(g)['PmenuKindSel']['pass'])
    def test_undefined_group_is_not_a_contrast_pass(self):
        self.assertEqual(group_pairs({'Normal':{'fg':0,'bg':0xffffff},'Pmenu':{}})['Pmenu']['status'],'undefined')
    def test_capture_timeout_kills_worker_group(self):
        import subprocess
        from unittest.mock import patch,MagicMock
        from tintprobe.evaluate_interactions import isolated_capture
        process=MagicMock(pid=12345)
        process.communicate.side_effect=[subprocess.TimeoutExpired('worker',15),('','')]
        with patch('tintprobe.evaluate_interactions.subprocess.Popen',return_value=process), patch('tintprobe.evaluate_interactions.os.killpg') as kill:
            with self.assertRaises(TimeoutError):isolated_capture({},100,'diagnostics')
            kill.assert_called_once()


def test_history_oracle_uses_real_exact_matching():
    import shutil, subprocess, os
    import pytest
    from tintprobe.evaluate_interactions import FZF_EXACT_QUERY,ROOT
    fzf=shutil.which('fzf')
    if not fzf:pytest.skip('fzf executable unavailable')
    source=(evaluation_path('fixtures/fzf/history.txt')).read_text()
    output=subprocess.check_output([fzf,'--no-sort','--filter='+FZF_EXACT_QUERY[1:]],input=source,text=True,
        env={**os.environ,'FZF_DEFAULT_OPTS':'','FZF_DEFAULT_OPTS_FILE':''})
    assert output.splitlines()[0].startswith('3989 ')



def test_only_inactive_fzf_gutter_is_exempt():
    from tintprobe.evaluate_interactions import assess
    from copy import deepcopy
    shot={'case':'fzf','width':100,'state':'initial','defaults':{'fg':0,'bg':0xfafaf8},
          'attrs':{1:{'foreground':0xfafaf8,'background':0xfafaf8}},
          'cells':[{'row':3,'col':0,'text':'▌','attr':1}]}
    assert assess(shot)['inactive_gutter_cells']==1
    assert not assess(shot)['failures']
    for change in ({'col':2},{'text':'='},{'row':0}):
        damaged=deepcopy(shot);damaged['cells'][0].update(change)
        assert assess(damaged)['failures']
    shot['case']='diagnostics'
    assert assess(shot)['failures']


def test_active_pointer_cannot_be_hidden_or_removed():
    from tintprobe.evaluate_interactions import assess
    shot={'case':'fzf','width':100,'state':'initial','defaults':{'fg':0,'bg':0xfafaf8},
          'attrs':{1:{'foreground':0,'background':0xb8595c},2:{'foreground':0xb8595c,'background':0xb8595c}},
          'cells':[{'row':2,'col':2,'text':'3993','attr':1},{'row':2,'col':0,'text':'▌','attr':2}]}
    roles={'fg+':pair('#000000','#B8595C')}
    assert assess(shot)['failures']
    assert fzf_oracle(shot,roles)
    shot['cells'].pop()
    assert fzf_oracle(shot,roles)
    shot['cells'].append({'row':2,'col':0,'text':'▌','attr':1})
    assert not fzf_oracle(shot,roles)
