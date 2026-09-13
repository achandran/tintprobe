from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.aesthetic_score import evaluate
from tintprobe.context import load_palette

class AestheticScore(unittest.TestCase):
    entry={'aesthetic_profile':'formex-reef-gmt-white-steel'}
    def setUp(self):
        self.palette=load_palette()
        self.cells=[{'text':'x','fg':'Reset','bg':'Reset','modifiers':''} for _ in range(200)]
        self.cells[0]['fg']='Rgb(163, 55, 62)'
    def score(self,p=None,cells=None):
        return evaluate(self.entry,p or self.palette,[{'file':'request','width':100,'cells':cells if cells is not None else self.cells}])
    def test_opt_in(self):self.assertEqual(evaluate({}, {}, [])['status'],'not_applicable')
    def test_unknown(self):self.assertEqual(evaluate({'aesthetic_profile':'../bad'}, {}, [])['status'],'unavailable')
    def test_missing_usage_no_total(self):self.assertIsNone(evaluate(self.entry,self.palette,[])['score'])
    def test_missing_roles_no_total(self):self.assertIsNone(evaluate(self.entry,{},[])['score'])
    def test_mutations(self):
        for family,key,value,component in [('backgrounds','base','#FFFFAF','dial'),('backgrounds','mantle','#99BBEE','steel'),('foregrounds','text','#AAAAAA','markings'),('accents','coral','#4466CC','red')]:
            with self.subTest(component=component):
                p=copy.deepcopy(self.palette);p[family][key]=value
                self.assertLess(self.score(p)['components'][component]['score'],self.score()['components'][component]['score'])
    def test_flat_steel(self):
        p=copy.deepcopy(self.palette);p['backgrounds']['mantle']=p['backgrounds']['crust']=p['backgrounds']['base']
        self.assertLess(self.score(p)['components']['steel']['score'],self.score()['components']['steel']['score'])
    def test_absent_and_excess_red(self):
        for fg in ('Reset','Rgb(163, 55, 62)'):
            cells=[dict(c,fg=fg) for c in self.cells]
            self.assertLess(self.score(cells=cells)['components']['red']['score'],self.score()['components']['red']['score'])
    def test_diff_colors_independent(self):
        p=copy.deepcopy(self.palette);p['diff']['changeEmphasis']='#FF00FF'
        self.assertEqual(self.score(p),self.score())
