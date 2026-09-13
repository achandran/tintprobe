# Frozen-palette interaction evaluation

The palette remains frozen. These checks identify problems without adjusting colors or thresholds to obtain a pass.

Run the interaction audit independently:

```sh
uv run tintprobe interactions --output evaluation/results/interactions
```

The combined `tintprobe suite` also runs it automatically. `--strict-gates` makes measured interaction contrast failures fail the combined suite. Missing captures fail execution even without strict gates.

## Evidence

- Contextual foreground/background checks use the generated Dawn shell export, including selected text, selected matches, prompt, spinner, pointer, and header. A color passing as a background does not establish that it passes as a foreground.
- Native Neovim diagnostic and completion scenes run at 100 and 160 columns for every pinned theme. All four diagnostic severities and completion menu content must actually appear.
- Native fzf receives synthetic history through a PTY hosted by Neovim. Initial selection, moving selection, and changing the query run at both widths. Selected item identity and foreground/background attributes are checked. The fixture includes Unicode, multiline entries, and a long path; these are corpus coverage, not proof that every item was selected and inspected.
- Highlight contracts include diagnostics, completion details, inlay hints, active signature parameters, selection, cursor, and matching brackets. Undefined groups are reported explicitly. These contracts do not claim complete plugin workflow coverage.

Every text contrast gate uses the unrounded WCAG ratio and a 4.5 minimum. Diagnostic colors colliding with ordinary text are observations, not automatic failures. Group contracts are supplementary; rendered scenes and generated fzf role pairs determine interaction quality gates.

## Controlled comparison

The existing manifest pins Kanso Pearl, Gruvbox Material Light Soft with **original** foregrounds, and the Modus Operandi Neovim port alongside Ithilien Dawn. The same fixture, widths, and application renderer are used. The gallery requests Berkeley Mono Medium at 16 pt. Cell captures do not establish native font rasterization.

Only Dawn currently has a declared native fzf configuration. Peer themes explicitly report missing fzf coverage; do not rank them as better because they have fewer tested roles. Codex ports are explicit adapters, not upstream author implementations. Modus results apply to the pinned Neovim port, not the original Emacs theme.

Native Ghostty pixels, Claude Code, and long-session comfort remain unverified. A passing interaction audit is not a world-class certification. Native fzf failures or timeouts remain visible as unavailable evidence; the suite never substitutes a fabricated rendering.

## Python workflows and overlapping states

The diff comparison now includes `selection-search` and `selection-search-diagnostic` alongside separate overlays. These retain linewise selection while search remains enabled; the latter adds an error diagnostic at the active line. The source-cell oracle verifies full line selection and search outside it. Cursor coordinates are captured, but terminal cursor glyph appearance remains unverified.

The interaction gallery adds diagnostic floats, documentation, active signature parameter, references in the quickfix window, and inline type hints. These are deterministic native-renderer fixtures, not requests to a live language server. They complement the separate Python Tree-sitter/basedpyright integration stage. Completion plugin-specific documentation behavior is not covered.

Use `--skip-fzf` on either the interaction script or combined suite to leave fzf out explicitly. Skipping it does not validate fzf. No palette or generated theme changes are made by these fixtures.
