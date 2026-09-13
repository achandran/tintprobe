from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import hashlib
import json
from pathlib import Path
import unittest
ROOT=TEST_ROOT
class EvaluationCorpus(unittest.TestCase):
    def test_pinned_sources_are_intact(self):
        sources=json.loads((evaluation_path('sources.json')).read_text())
        for source in sources.values():
            self.assertRegex(source['revision'],r'^[0-9a-f]{40}$')
            for item in source['files']:
                self.assertEqual(hashlib.sha256((project_resource(item['path'])).read_bytes()).hexdigest(),item['sha256'])
    def test_cases_have_real_edits_and_local_paths(self):
        for case in json.loads((evaluation_path('cases.json')).read_text()):
            paths=[(EVALUATION / case[k]).resolve() for k in ('before','after')]
            for path in paths:self.assertTrue(path.is_relative_to(EVALUATION))
            self.assertNotEqual(paths[0].read_bytes(),paths[1].read_bytes())

class NativeStateChecks(unittest.TestCase):
    def test_missing_or_recolored_selection_fails(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from tintprobe.evaluation_checks import state_failures
        from tintprobe.context import load_palette
        palette=load_palette()
        shot={'case':'mutation','state':'selection','attrs':{},'defaults':{'fg':0,'bg':0xffffff},'cells':[{'text':'x','attr':0}]}
        self.assertTrue(state_failures(shot,palette))
        shot['attrs'][0]={'background':int(palette['highlight']['background'][1:],16)}
        self.assertFalse(state_failures(shot,palette))
        shot['cells'][0]['text']=' '
        self.assertFalse(state_failures(shot,palette))
        shot['attrs'][0]['background']=0xffffff
        self.assertTrue(state_failures(shot,palette))

class CodexColorResolution(unittest.TestCase):
    def test_native_color_depths(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from tintprobe.codex_native import color
        from tintprobe.context import load_palette
        p=load_palette()
        self.assertEqual(color('Rgb(0, 95, 255)',p,'#000000'),'#005FFF')
        self.assertEqual(color('Indexed(196)',p,'#000000'),'#FF0000')
        self.assertEqual(color('Indexed(232)',p,'#000000'),'#080808')
        self.assertEqual(color('Red',p,'#000000'),p['ansi']['red'])
        with self.assertRaises(ValueError):color('Unrecognized',p,'#000000')

class PythonCoverage(unittest.TestCase):
    def test_python_syntax_corpus_is_valid_and_varied(self):
        import ast
        cases=json.loads((evaluation_path('cases.json')).read_text())
        python_cases=[c for c in cases if c.get('require_syntax')]
        self.assertGreaterEqual(len(python_cases),3)
        kinds=set()
        for case in python_cases:
            for side in ('before','after'):
                tree=ast.parse((EVALUATION / case[side]).read_text())
                kinds.update(type(node).__name__ for node in ast.walk(tree))
        self.assertTrue({'AsyncFunctionDef','AsyncWith','Await','ClassDef','AnnAssign','JoinedStr','ListComp','DictComp','Match','Try','Raise','Lambda'} <= kinds)

    def test_disabled_python_syntax_is_detected(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from tintprobe.evaluation_checks import state_failures
        from tintprobe.context import load_palette
        shot={'case':'python','state':'diff','require_syntax':True,'syntax_groups':[]}
        self.assertTrue(state_failures(shot,load_palette()))
        shot['syntax_groups']=['pythonStatement','pythonString','pythonComment']
        self.assertFalse(state_failures(shot,load_palette()))

class ThemeComparison(unittest.TestCase):
    def test_contrast_uses_rendered_colors_not_ithilien_roles(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from tintprobe.compare_themes import assess
        shot={'case':'test','width':10,'state':'diff','defaults':{'fg':0,'bg':0xffffff},'attrs':{1:{'foreground':0xffffff,'background':0}},'cells':[{'text':'x','attr':1}], 'highlights':{g:{'bg':0xffffff} for g in ('DiffText','DiffChange','Search','Visual')}}
        self.assertEqual(assess(shot)['cells_below_4_5'],0)
        shot['attrs'][1]['foreground']=0x111111
        self.assertEqual(assess(shot)['cells_below_4_5'],1)

    def test_four_named_theme_adapters(self):
        entries=json.loads((evaluation_path('themes.json')).read_text())
        self.assertEqual(len({e['id'] for e in entries}),4)
        for entry in entries:
            self.assertTrue(entry['setup'])
            for pin in entry['pins'].values():self.assertRegex(pin,r'^[a-f0-9]{40}$')
