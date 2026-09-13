from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=TEST_ROOT
sys.path.insert(0,str(ROOT/'scripts'))
from tintprobe.score_themes import score

class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.rubric=json.loads((evaluation_path('rubric.json')).read_text())
        self.shot={'case':'test','width':100,'state':'diff','defaults':{'fg':0,'bg':0xffffff},'attrs':{1:{'foreground':0,'background':0xdddddd},2:{'foreground':0,'background':0xaaaaaa}},'cells':[{'row':0,'col':0,'text':'x','attr':1},{'row':0,'col':1,'text':'y','attr':2}], 'regions':[{'row':0,'col':0,'group':'DiffChange'},{'row':0,'col':1,'group':'DiffText'}]}
    def test_unreadable_text_lowers_score(self):
        original=score([self.shot],self.rubric)['diff']['score']
        self.shot['attrs'][2]['foreground']=0xaaaaaa
        self.assertLess(score([self.shot],self.rubric)['diff']['score'],original)
    def test_indistinguishable_inline_lowers_score(self):
        original=score([self.shot],self.rubric)['diff']['score']
        self.shot['attrs'][2]['background']=0xdddddd
        result=score([self.shot],self.rubric)
        self.assertLess(result['diff']['score'],original)
        self.assertEqual(result['diff']['components']['inline_distinction'],0)
    def test_missing_regions_never_pass(self):
        self.shot['regions']=[]
        self.assertIsNone(score([self.shot],self.rubric)['diff']['score'])
    def test_missing_oracle_cell_blocks_score(self):
        self.shot['case']='punctuation'
        result=score([self.shot],self.rubric)
        self.assertIsNone(result['diff']['score'])
        self.assertTrue(result['diff']['oracle_failures'])
    def test_unmeasured_axes_remain_null(self):
        result=score([self.shot],self.rubric)
        self.assertIsNone(result['agents']['score'])
        self.assertIsNone(result['long_session']['score'])
    def test_gutters_do_not_change_score(self):
        original=score([self.shot],self.rubric)['diff']['score']
        self.shot['cells'].append({'row':3,'col':0,'text':'|','attr':2})
        self.assertEqual(score([self.shot],self.rubric)['diff']['score'],original)
    def test_hue_difference_contributes_to_separation(self):
        from tintprobe.score_themes import distance
        self.assertGreater(distance(0xff0000,0x009400),20)
        self.assertEqual(distance(0xaabbcc,0xaabbcc),0)
