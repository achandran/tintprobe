from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import ast,json,unittest
from pathlib import Path
ROOT=TEST_ROOT
class PythonRuntime(unittest.TestCase):
    def test_pinned_server_and_parser(self):
        from importlib.metadata import version
        spec=json.loads((evaluation_path('python-runtime.json')).read_text())
        self.assertEqual(version('basedpyright'),spec['language_server_version'])
        self.assertRegex(spec['tree_sitter_revision'],r'^[a-f0-9]{40}$')
    def test_fixtures_have_intentional_diagnostic(self):
        for c in json.loads((evaluation_path('python-cases.json')).read_text()):
            for side in ('before','after'):
                text=(EVALUATION / c[side]).read_text();ast.parse(text)
                self.assertIn('invalid_count: int = "not an integer"',text)
    def test_semantic_response_without_applied_marks_fails(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from tintprobe.evaluation_checks import syntax_ready
        b={'parser':True,'semantic_tokens':3,'semantic_extmarks':0,'diagnostics':1}
        self.assertFalse(syntax_ready({'python_runtime':{'buffers':[b,b]}}))
        b['semantic_extmarks']=3
        self.assertTrue(syntax_ready({'python_runtime':{'buffers':[b,b]}}))
