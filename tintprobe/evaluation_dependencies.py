from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Pinned, checkout-local evaluation sources. Never reset existing checkouts."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from tintprobe.context import ROOT, CONFIG


def validate(deps):
    missing = [d['path'] for d in deps.values() if not (ROOT / d['path']).is_dir()]
    if missing:
        raise FileNotFoundError('Missing evaluation dependencies: ' + ', '.join(sorted(set(missing))) +
                                '. Run make setup-evaluation once (network required).')
    for d in deps.values():
        path = ROOT / d['path']
        actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True, timeout=30).strip()
        if actual != d['revision']:
            raise ValueError(f"Pinned revision mismatch at {path}: {actual}; expected {d['revision']}. Existing checkout left untouched.")
        if subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True, timeout=30).strip():
            raise ValueError(f'Dependency has local changes: {path}; existing checkout left untouched.')


def fetch_one(d):
    path = ROOT / d['path']
    if path.exists():
        validate({'existing': d})
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # A failed download never leaves a half-created dependency at its final path.
    with tempfile.TemporaryDirectory(prefix='.fetch-', dir=path.parent) as tmp:
        checkout = Path(tmp) / 'repo'
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        subprocess.run(['git', '-C', str(checkout), 'remote', 'add', 'origin', d['url']], check=True)
        subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth=1', 'origin', d['revision']], check=True, timeout=180)
        subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
        validate({'download': dict(d, path=str(checkout))})
        checkout.rename(path)


def plugin_dependencies(manifest, fetch=False):
    deps = json.loads((project_resource(manifest)).read_text())
    if fetch:
        for d in deps.values():
            fetch_one(d)
    validate(deps)
    return deps


def dependencies(themes=None, build_only=False):
    result = {}
    entries = json.loads((evaluation_path('themes.json')).read_text())
    known = {e['id'] for e in entries}
    if themes and set(themes) - known:
        raise ValueError('Unknown themes: ' + ', '.join(sorted(set(themes) - known)))
    def add(d):
        previous = result.get(d['path'])
        if previous and previous['revision'] != d['revision']:
            raise ValueError('Conflicting dependency pins: ' + d['path'])
        result[d['path']] = d
    for entry in entries:
        if themes and entry['id'] not in themes:
            continue
        for path, revision in entry.get('pins', {}).items():
            add({'path': path, 'revision': revision, 'url': entry['sources'][path]})
    if not build_only:
        for name in ('pickers', 'python-tools', 'git-review'):
            manifest = evaluation_path(f'{name}-dependencies.json')
            if not manifest.exists(): continue
            for d in json.loads(manifest.read_text()).values():
                add(d)
        py = json.loads((evaluation_path('python-runtime.json')).read_text())
        codex = json.loads((evaluation_path('sources.json')).read_text())['codex']
        add({'path': CONFIG.get('evaluation_dir', 'evaluation') + '/deps/tree-sitter-python', 'url': py['tree_sitter_source'], 'revision': py['tree_sitter_revision']})
        add({'path': CONFIG.get('evaluation_dir', 'evaluation') + '/deps/codex', 'url': codex['repository'], 'revision': codex['revision']})
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch', action='store_true', help='Download missing pinned sources; never modify an existing checkout')
    p.add_argument('--build-only', action='store_true')
    p.add_argument('--themes', nargs='+', default=None)
    a = p.parse_args()
    deps = dependencies(a.themes, a.build_only)
    if a.fetch:
        for d in deps.values():
            print('Prepare ' + d['path'], flush=True)
            fetch_one(d)
    validate(deps)
    print(f'{len(deps)} pinned sources verified. System prerequisites: Neovim, Git, fzf, Rust/Cargo; macOS Swift and Screen Recording for Ghostty.')
