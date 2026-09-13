"""Command entry points. Desktop capture is always explicit."""
import argparse
import os
from pathlib import Path
import runpy
import sys

COMMANDS = {
    'compare': 'compare_themes', 'suite': 'evaluate_suite',
    'prepare': 'evaluation_dependencies', 'ghostty': 'evaluate_ghostty',
    'images': 'analyze_ghostty_images', 'codex-ui': 'codex_ui',
    'validate': 'validate_evaluator', 'interactions': 'evaluate_interactions',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    parser.add_argument('command', choices=[*COMMANDS, 'workflow'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    args = parser.parse_args()
    rest = args.arguments
    os.environ['TINTPROBE_PROJECT_ROOT'] = str(args.project_root.resolve())
    from tintprobe.context import enable_workflows, script_path
    enable_workflows()
    if args.command == 'workflow':
        if not rest:
            parser.error('workflow requires an adapter name')
        name, rest = rest[0], rest[1:]
        if not name.replace('_', '').isalnum():
            parser.error('invalid workflow name')
        sys.argv = [name, *rest]
        runpy.run_path(str(script_path(name + '.py')), run_name='__main__')
    else:
        module = COMMANDS[args.command]
        sys.argv = [module, *rest]
        runpy.run_module('tintprobe.' + module, run_name='__main__')
