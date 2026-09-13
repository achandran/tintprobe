from tintprobe.context import ROOT as TEST_ROOT, evaluation_path, project_resource, EVALUATION, port_path
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tintprobe.codex_flows import STAGES,validate_records
class FlowEvidence(unittest.TestCase):
    def records(self):return [{'file':s,'width':w,'cells':[{'text':' '.join(parts)}]} for s,parts in STAGES.items() for w in (60,100)]
    def test_all_stages_present(self):validate_records(self.records())
    def test_missing_stage_rejected(self):
        with self.assertRaises(ValueError):validate_records(self.records()[:-1])
    def test_blank_approval_rejected(self):
        records=self.records()
        for r in records:
            if r['file']=='approval':r['cells']=[]
        with self.assertRaises(ValueError):validate_records(records)
