# Tintprobe

Reproducible color scheme evaluation for editors and terminals.

Tintprobe captures actual Neovim UI cells, measures foreground/background pairs
and diff cues, and produces linked evidence. Optional adapters cover Codex replay,
Ghostty pixel analysis, and project-specific plugin workflows. It does not declare
a universally best theme or infer long-session comfort from contrast scores.

## Install and compare

Requires Python 3.12+, Git, and Neovim for native editor capture.

```sh
git clone https://github.com/achandran/tintprobe.git
cd tintprobe
uv sync --locked
uv run tintprobe prepare --build-only --fetch --themes kanso-pearl modus-operandi
uv run tintprobe compare --themes kanso-pearl modus-operandi
```

Open `evaluation/results/comparison/gallery.html` and `scorecard.html`.
The first command downloads exact pinned theme revisions into an ignored cache;
subsequent captures do not fetch sources. The comparison is headless and does not
open a terminal window or use desktop input.

For your own theme, provide a JSON list with an ID, runtime paths, and Lua setup:

```json
[
  {
    "id": "my-theme",
    "paths": ["/absolute/path/to/my-theme"],
    "setup": "vim.cmd.colorscheme('my-theme')"
  }
]
```

```sh
uv run tintprobe compare --manifest /path/to/themes.json
```

Runtime paths are relative to `--project-root` (the current directory by default).
Optional `pins` map paths to exact Git revisions; `sources` map the same paths to
repository URLs. Setup Lua and project workflow adapters execute code: use trusted
manifests. No palette file or Ithilien installation is required for comparison.

## Measurements and expectations

Reports distinguish failed execution, failed checks, missing coverage, and
measurements requiring review. Defaults include text contrast and edited-span
checks. Projects can override `evaluation/rubric.json`; background-distance floors
are engineering heuristics, not accessibility standards. Weighted totals are off
by default. Aesthetic profiles are optional, project-supplied expectations.

- WCAG contrast, signed APCA, OKLab and CIEDE2000 distances, color-vision simulations.
- Native code, diff, selection, and search fixtures; original theme styles retained.
- Defect-injection checks that verify the evaluator can detect erased or merged edits.
- Pinned native Codex replay and optional terminal image analysis.
- JSON evidence and HTML galleries; native pixels and reconstructed cells are identified separately.

Run `uv run tintprobe --help` for commands. `compare` is the standalone editor
entry point. `suite` adds Python, Codex, and interaction stages and requires their
pinned tools. Ghostty desktop capture requires an explicit `--capture` (or
`--ghostty-capture` in the suite), an idle authorized macOS desktop, and permissions.
`images --output PATH` only reanalyzes saved frames; it cannot certify a new render.

See [project profiles](docs/profiles.md), [development](docs/development.md), and
[extraction provenance](PROVENANCE.md). Ithilien-specific palette policy, named
colors, and plugin assertions remain in the [Ithilien repository](https://github.com/achandran/ithilien).
