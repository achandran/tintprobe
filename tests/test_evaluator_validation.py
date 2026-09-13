from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.validate_evaluator import verdict
class Validation(unittest.TestCase):
    def test_negative_control_requires_specific_gate(self):
        self.assertFalse(verdict({'failures':[{'gate':'text_contrast'}]},'critical_inline_background'))
    def test_negative_control_cannot_pass_silently(self):
        self.assertFalse(verdict({'failures':[]},'text_contrast'))
    def test_positive_control_rejects_any_failure(self):
        self.assertFalse(verdict({'failures':[{'gate':'required_edit_missing'}]},None))
    def test_controls_accept_expected_results(self):
        self.assertTrue(verdict({'failures':[]},None))
        self.assertTrue(verdict({'failures':[{'gate':'text_contrast'}]},'text_contrast'))
