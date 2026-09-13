from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import copy,json,sys,unittest
from pathlib import Path
ROOT=TEST_ROOT;sys.path.insert(0,str(ROOT/'scripts'))
from tintprobe.evaluation_gates import evaluate_gates

class GateMutations(unittest.TestCase):
    def setUp(self):
        self.r=json.loads((evaluation_path('rubric.json')).read_text())
        self.r['inline_oracles']={'sample':[{'side':'before','line':1,'byte':2,'text':'x'}]}
        self.s={'case':'sample','width':100,'state':'diff','defaults':{'fg':0,'bg':0xffffff},'attrs':{1:{'foreground':0,'background':0xeeeeee},2:{'foreground':0,'background':0xaaaaaa}},'cells':[{'row':0,'col':0,'attr':1,'text':'a'},{'row':0,'col':1,'attr':2,'text':'x'}],'regions':[{'row':0,'col':0,'side':'before','source_line':1,'source_byte':1,'text':'a','group':'DiffChange'},{'row':0,'col':1,'side':'before','source_line':1,'source_byte':2,'text':'x','group':'DiffText'}]}
    def gates(self,shots):return {f['gate'] for f in evaluate_gates(shots,self.r)['failures']}
    def test_healthy_fixture_passes(self):self.assertFalse(self.gates([self.s]))
    def test_single_invisible_character_fails_without_averaging(self):
        self.s['attrs'][2]['foreground']=0xaaaaaa
        self.assertIn('text_contrast',self.gates([self.s]))
    def test_removed_emphasis_fails(self):
        self.s['regions'][1]['group']='DiffChange'
        self.assertIn('inline_emphasis_missing',self.gates([self.s]))
    def test_merged_backgrounds_fail(self):
        self.s['attrs'][2]['background']=0xeeeeee
        self.assertIn('critical_inline_background',self.gates([self.s]))
    def test_invisible_overlay_fails(self):
        overlay=copy.deepcopy(self.s);overlay['state']='search'
        self.assertIn('overlay_not_visible',self.gates([self.s,overlay]))
    def test_visible_overlay_passes(self):
        overlay=copy.deepcopy(self.s);overlay['state']='search';overlay['attrs'][1]['background']=0xbbccdd
        self.assertNotIn('overlay_not_visible',self.gates([self.s,overlay]))
    def test_distinct_hue_change_is_not_automatically_a_failure(self):
        self.s['attrs'][2]['background']=0x99aacc
        self.assertFalse(self.gates([self.s]))
    def test_gutter_does_not_influence_readability(self):
        self.s['cells'].append({'row':2,'col':0,'attr':2,'text':'|'})
        self.assertFalse(self.gates([self.s]))
    def test_typography_gets_review_instead_of_background_only_verdict(self):
        self.s['attrs'][2]['background']=0xeeeeee
        self.s['highlights']={'DiffText':{'bold':True},'DiffChange':{}}
        self.assertIn('inline_cue_review',self.gates([self.s]))
        self.assertNotIn('critical_inline_background',self.gates([self.s]))
    def test_bold_space_is_not_visible_emphasis(self):
        from tintprobe.evaluation_gates import alternative_inline_cues
        self.s['highlights']={'DiffText':{'bold':True},'DiffChange':{}}
        self.assertEqual(alternative_inline_cues(self.s,{'text':' '}),[])
