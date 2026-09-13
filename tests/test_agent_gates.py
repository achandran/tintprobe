from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.agent_gates import assess
class AgentGates(unittest.TestCase):
    def palette(self):return {'foregrounds':{'text':'#000000'},'backgrounds':{'base':'#FFFFFF'},'ansi':{str(i):'#000000' for i in range(16)}}
    def record(self):return {'file':'test-stage','width':60,'cells':[{'row':0,'col':0,'text':'x','fg':'Reset','bg':'Reset','modifiers':'NONE'}]}
    def test_clear_text_passes(self):self.assertEqual(assess([self.record()],self.palette())['status'],'pass')
    def test_bad_contrast_reports_coordinate(self):
        r=self.record();r['cells'][0]['fg']='Rgb(250, 250, 250)'
        result=assess([r],self.palette());self.assertEqual(result['status'],'fail')
        self.assertEqual(result['stages'][0]['failures'][0]['col'],0)
    def test_missing_cells_cannot_pass(self):
        self.assertEqual(assess([],self.palette())['status'],'fail')
        r=self.record();r['cells']=[]
        self.assertEqual(assess([r],self.palette())['status'],'fail')
    def test_dim_is_explicitly_unverified(self):
        r=self.record();r['cells'][0]['modifiers']='DIM'
        self.assertEqual(assess([r],self.palette())['stages'][0]['dim_cells_unverified'],1)
    def test_missing_required_approval_content_fails(self):
        r=self.record();r['file']='approval'
        result=assess([r],self.palette())
        self.assertEqual(result['status'],'fail')
        self.assertTrue(any(x['status']=='missing' for x in result['stages'][0]['required_content']))
