# Project profiles

A `tintprobe.json` in the project root supplies optional theme-specific inputs.
The standalone `compare` command only needs a theme manifest; ports and role
palettes are required only by the commands that use them.

```json
{
  "schema_version": 1,
  "default_theme": "my-theme",
  "default_adapter": {
    "id": "my-theme",
    "paths": ["."],
    "setup": "vim.cmd.colorscheme('my-theme')"
  },
  "palettes": {"variants": {"my-theme": "palette/resolved.json"}},
  "ports": {
    "ghostty": "extras/ghostty/theme.conf",
    "codex_theme": "extras/codex/theme.tmTheme",
    "codex_config": "extras/codex/config.toml"
  },
  "workflow_dir": "tests/workflows"
}
```

Role palettes declare `foregrounds`, `backgrounds`, `ansi`, `highlight`, and `diff`
as needed by the selected check. Values are sRGB hex strings. A `colors` name map
and `palettes.shared` JSON are supported as input conveniences; project-specific
naming rules and approval constraints are deliberately not enforced by Tintprobe.

A manifest entry can declare `codex_theme` to use a native exported TextMate theme;
otherwise the Codex comparison adapter generates an explicitly labeled conversion
from Neovim highlights. `zsh_theme` opts a theme into its shell/fzf fixture.
The profile's `ports.prompt` optionally supplies a shell prompt specimen.

`evaluation_path` resolves a project override before falling back to packaged
data. Themes, rubrics, aesthetic profiles, and render profiles can be overridden.
Shared source fixtures, source hashes, and Rust adapters ship in the package.
Dependencies and output always live in the caller's workspace, never in the
installed Python package. Existing saved images remain valid only when their
recorded theme and rendering assumptions match.

`workflow NAME` loads a trusted Python adapter from the declared workflow directory.
The extended suite recognizes `evaluate_pickers`, `evaluate_python_tools`,
`evaluate_git_review`, and `evaluate_installed_workflows` adapters when explicitly
requested. Their pass/fail policy belongs to the project, not the general benchmark.
Unconfigured workflow requests are reported as blocked, not silently passed.

Profile selection is per process. Set `--project-root` on the CLI before loading
any engine modules, or set `TINTPROBE_PROJECT_ROOT` before importing the Python API.

`contracts.ordinary_weight_diffs: true` enforces ordinary weight and no underline
in the native Ghostty diff check. It is opt-in; themes may otherwise use their
original emphasis styles. Adapters may specify `background: "dark"` for dark themes.
