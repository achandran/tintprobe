from tintprobe.context import evaluation_path, script_path, project_resource, EVALUATION, port_path, default_adapter, DEFAULT_THEME
"""Keep native acquisition, measured quality, and outstanding coverage distinct."""
import hashlib
import json


def synchronize(output, report, quality):
    report['command_quality'] = quality
    report['quality_sha256'] = hashlib.sha256((output/'quality.json').read_bytes()).hexdigest()
    measured = {row['id']: row for row in quality.get('results', [])}
    coverage = report.setdefault('coverage', {})
    for role in ('cursor', 'selection'):
        expected = [r['id'] for r in report['results'] if role in r]
        passed = sum(measured.get(name, {}).get('status') == 'pass' for name in expected)
        coverage[role] = f'{passed}/{len(expected)} native cases passed; see command_quality'
    commands = [r['id'] for r in report['results'] if not r.get('kind') and r['id'] != 'attributes']
    passed = sum(measured.get(name, {}).get('status') == 'pass' for name in commands)
    coverage['terminal_commands'] = f'{passed}/{len(commands)} real command cases passed'
    coverage['ansi_and_dim'] = measured.get('attributes', {}).get('status', 'unverified')
    editors = [r['id'] for r in report['results'] if r.get('kind') == 'native-neovim']
    passed = sum(measured.get(name, {}).get('status') == 'pass' for name in editors)
    coverage['neovim'] = f'{passed}/{len(editors)} live Neovim-in-Ghostty scenes passed'
    shells = [r['id'] for r in report['results'] if r.get('kind') == 'native-shell']
    passed = sum(measured.get(name, {}).get('status') == 'pass' for name in shells)
    coverage['shell_keymaps'] = f'{passed}/{len(shells)} real zsh ZLE cases passed (fixture-local hooks)'
    replays = [r['id'] for r in report['results'] if r.get('kind') == 'native-codex-replay']
    passed = sum(measured.get(name, {}).get('status') == 'pass' for name in replays)
    coverage['codex_replay'] = f'{passed}/{len(replays)} native-renderer replay frames passed in Ghostty; not live model sessions'
    coverage['codex'] = 'Live session unverified; native-renderer replay pixels are reported separately'
    report['remaining_native_coverage'] = [
        'User-installed shell hooks and custom plugin configurations',
        'Full native plugin/LSP and live agent workflow matrix',
        'Font identity and fallback glyphs',
        'Claude Code native rendering',
    ]
    if measured.get('cursor-inactive-block',{}).get('status')!='pass':
        report['remaining_native_coverage'].insert(0,'Inactive-window cursor appearance (requires same-Space capture availability)')
    report['pass'] = False
    if not report.get('capture_error'):
        report['status'] = 'incomplete'
        report['reason'] = 'Measured cases are in command_quality; remaining_native_coverage prevents full native acceptance.'
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
