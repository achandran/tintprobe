"""Explicit project inputs and packaged evaluation resources.

A theme project may override corpus policy, provide a role palette, and register
trusted local workflow adapters. No installed theme or personal config is read
unless the selected command explicitly requests it.
"""
import json
import os
import sys
from pathlib import Path
from tintprobe.colors import Color, rgb, wcag, apca, oklch, delta_e, simulated_hex

ROOT = Path(os.environ.get('TINTPROBE_PROJECT_ROOT', os.getcwd())).resolve()
PACKAGE = Path(__file__).resolve().parent
EVALUATION = PACKAGE / 'data'
config_path = ROOT / 'tintprobe.json'
CONFIG = json.loads(config_path.read_text()) if config_path.exists() else {}
DEFAULT_THEME = CONFIG.get('default_theme', 'default')


def evaluation_output(relative):
    """Project-owned paths for outputs/caches, never packaged resources."""
    return ROOT / CONFIG.get('evaluation_dir', 'evaluation') / relative


def evaluation_path(relative):
    local = evaluation_output(relative)
    return local if local.exists() else EVALUATION / relative


def project_resource(relative):
    path = Path(relative)
    if path.parts and path.parts[0] == 'evaluation':
        return evaluation_path(Path(*path.parts[1:]))
    return ROOT / path


def script_path(name):
    for folder in (ROOT / CONFIG.get('workflow_dir', 'tests/workflows'), ROOT / 'scripts', PACKAGE):
        path = folder / name
        if path.exists():
            return path
    raise FileNotFoundError(f'No evaluator or project workflow named {name}')


def port_path(name):
    value = CONFIG.get('ports', {}).get(name)
    if not value:
        raise ValueError(f'This check requires ports.{name} in {config_path}')
    return ROOT / value


def default_adapter():
    entry = CONFIG.get('default_adapter')
    if not entry:
        raise ValueError('Provide a theme adapter; no colorscheme is selected implicitly')
    return dict(entry, paths=[ROOT / p for p in entry['paths']])


def load_palette(variant=None):
    """Read declared role data; authoring and aesthetic policy belong to the project."""
    spec = CONFIG.get('palettes', {})
    name = variant or DEFAULT_THEME
    path = spec.get('variants', {}).get(name)
    if not path:
        raise ValueError(f'No role palette declared for {name!r} in {config_path}')
    shared = json.loads((ROOT / spec['shared']).read_text()) if spec.get('shared') else {}
    result = {**shared, **json.loads((ROOT / path).read_text())}
    colors = result.pop('colors', {})
    result.pop('colorNotes', None)
    for key, value in list(result.items()):
        if isinstance(value, dict):
            result[key] = {role: colors.get(color, color) if isinstance(color, str) else color for role, color in value.items()}
    return result


def enable_workflows():
    folder = CONFIG.get('workflow_dir')
    if folder:
        sys.path.insert(0, str(ROOT / folder))


def workflow(name):
    import importlib
    if not CONFIG.get('workflow_dir'):
        raise FileNotFoundError('No project workflow directory configured')
    enable_workflows()
    try:
        return importlib.import_module(name).run
    except ModuleNotFoundError as exc:
        raise FileNotFoundError(f'Project workflow unavailable: {name}') from exc
