from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Recheck saved command screenshots without native screen access."""
import argparse
import json
from pathlib import Path
from tintprobe.capture_ghostty import build_helper
from tintprobe.ghostty_quality import analyze

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    report=analyze(output,build_helper(output))
    from tintprobe.ghostty_coverage import synchronize
    synchronize(output, json.loads((output/'report.json').read_text()), report)
    print('Text-check status: '+report['status'])
    print('Report: '+str(output/'quality.html'))
    raise SystemExit(0 if report['status']=='pass' else 1)
