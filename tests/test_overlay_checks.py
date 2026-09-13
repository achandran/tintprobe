from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.overlay_checks import overlay_failures

class OverlayChecks(unittest.TestCase):
    def setUp(self):
        self.s={'case':'x','width':100,'state':'selection-char','overlay':{'anchor':[1,1],'finish':[1,2],'anchor_vcol':1,'finish_vcol':2},'cells':[{'row':0,'col':0,'attr':1},{'row':0,'col':1,'attr':0},{'row':0,'col':2,'attr':0}], 'attr_info':{1:[{'hi_name':'Visual'}]},'regions':[{'row':0,'col':i,'source_line':1,'source_byte':i+1,'side':'after','vcol':[i+1,i+1]} for i in range(3)]}
    def test_expected_selection_passes(self):self.assertFalse(overlay_failures(self.s))
    def test_partial_selection_detected(self):
        self.s['cells'][0]['attr']=0
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'overlay_missing_cell')
    def test_selection_spill_detected(self):
        self.s['cells'][2]['attr']=1
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'overlay_extra_cell')
    def test_other_pane_selection_detected(self):
        self.s['regions'][0]['side']='before'
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'overlay_extra_cell')
    def test_search_missing_and_extra(self):
        self.s['state']='search';self.s['attr_info']={1:[{'hi_name':'Search'}]}
        self.s['regions'][0]['search_match']=True
        self.assertFalse(overlay_failures(self.s))
        self.s['cells'][2]['attr']=1
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'overlay_extra_cell')
    def test_tabs_use_virtual_columns(self):
        self.s['state']='selection-block';self.s['overlay']['finish']=[2,2];self.s['overlay']['finish_vcol']=8
        self.s['regions']=self.s['regions'][:1];self.s['regions'][0]['vcol']=[1,8]
        self.assertFalse(overlay_failures(self.s))
    def test_combined_line_selection_keeps_full_line(self):
        self.s['state']='selection-search';self.s['overlay']['search_pattern']='needle'
        self.s['cells'][2]['attr']=1
        self.assertFalse(overlay_failures(self.s))
    def test_combined_search_outside_selection_required(self):
        self.s['state']='selection-search';self.s['overlay']['search_pattern']='needle'
        self.s['cells'][2]['attr']=1
        self.s['regions'][0]['side']='before'
        self.s['regions'][0]['search_match']=True
        self.s['cells'][0]['attr']=0
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'combined_search_missing')
    def test_combined_diagnostics_must_be_present(self):
        self.s['state']='selection-search-diagnostic'
        self.s['overlay']['search_pattern']='needle'
        self.s['cells'][2]['attr']=1
        self.assertEqual(overlay_failures(self.s)[0]['gate'],'combined_diagnostic_missing')
