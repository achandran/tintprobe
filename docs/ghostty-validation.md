# Ghostty validation

This stage is under development. It never counts prepared ANSI output or a
calibration-only screenshot as full native acceptance.

Use `uv run tintprobe compare` while working on this computer. Use
`uv run tintprobe images --output PATH` to recheck saved screenshots with no
desktop interaction. Foreground capture requires an idle desktop: concurrent
typing, clicking, or switching Spaces can invalidate focus, selection, and
cursor evidence. A separate test Mac is the strongest option for unattended
native coverage. Headless or saved-image passes do not replace that final layer.

`uv run tintprobe suite` prepares real Git status, Git diff, single-character Git word
diff, ripgrep, the optional project-configured zsh prompt, and pytest output in a disposable repository. Pytest deliberately
runs one passing and one failing Python test. A separate labeled probe covers
ANSI 0–15 and dim text. The palette remains frozen. No installed configuration,
user repository, shell history, or application data is changed.

## Native capture worker

On a macOS host where native UI automation is authorized and Screen Recording
is already available, run:

```sh
uv run tintprobe ghostty --capture
# Or include it in the combined suite:
uv run tintprobe suite --ghostty-capture
```

The worker compiles a small Swift helper, checks capture permission without
requesting it, and launches one isolated Ghostty window with a unique title for the entire run.
The window receives a generated config, Berkeley Mono Medium at 16 points, and
sRGB. A resident worker runs scenes sequentially, resets the terminal between
scenes, and acknowledges each scene's readiness and exit. Only the uniquely
titled window is captured; there is no whole-desktop capture. Each fixture has
a bounded lifetime. Cleanup explicitly closes that exact window through
Accessibility and verifies it disappeared, including after capture failures.
`session-window.json` and `session-cleanup.json` record ownership and cleanup.
The worker never quits the user's other Ghostty windows.

Screenshots are decoded into sRGB and checked for six ANSI calibration swatches
(with a two-channel-value tolerance and at least 100 matching pixels per color).
This catches blank captures and gross palette mismatches. It does **not** prove
text content completeness, font selection, glyph contrast, cursor rendering,
selection, or readability. Actual screenshots are linked in the gallery when
captured. The report remains `incomplete`, with a nonzero acceptance exit,
until those additional gates exist. Partial failures remain visible.

Native execution requires authorization in the environment running it. Preparing
fixtures and testing the evaluator's logic require no native app access.

## Remaining acceptance work

- Verify full command output is visible, including wrapped paths, errors, and
  punctuation; add additional terminal command fixtures.
- Verify font and geometry, then measure glyph foreground/background samples.
- Extend cursor coverage to inactive windows and real shell mode hooks, then
  verify the implemented cursor and mouse selection cases on the target host.
- Display the existing native Neovim and Codex fixtures through Ghostty and
  compare their pixels with their recorded cells.
- Check stable repeated captures and reject stale, clipped, or occluded frames.

No comfort or Claude Code validation is claimed by this stage.

## Running from a regular checkout

Use `uv run tintprobe ghostty --capture` to test only Ghostty. Selected native cases require their configured theme and application dependencies.
A project palette and Ghostty port must be configured; see [profiles](profiles.md).
`uv run tintprobe ghostty` prepares fixtures without launching UI.
Both currently exit nonzero because native acceptance is incomplete, even if
all available calibration checks pass. Inspect `evaluation/results/ghostty/report.json`
for the precise status. The full `uv run tintprobe suite` still requires its documented
pinned dependencies; this target does not install them.

Startup diagnostics distinguish an unstarted launcher, a failed child process,
and a ready fixture whose window cannot be located. Each scene retains a
`*.child.log` and `*.started` marker. The launcher uses Ghostty's explicit
`initial-command=shell:...` form, quotes every path, disables shell integration
for the fixture, and keeps the byte emitter free of third-party imports.

## Command text checks

Native runs now also produce `quality.html` and `quality.json`. To analyze
existing screenshots without launching or capturing any app:

```sh
uv run tintprobe images
```

The analyzer locates the six calibration bars to infer the terminal grid, parses
the recorded ANSI output, and checks every expected nonspace ASCII cell for
clipping, the expected foreground color, and dark stroke contrast against the
cell's modal background (minimum 4.5:1). Pixels are converted using their ICC
profile into sRGB. This is a solid-stroke rendering proxy, not a psychophysical
readability or comfort score. Antialiased edge pixels are not required to meet
the solid-text contrast threshold. Tiny punctuation is tested explicitly.

An independent Apple Vision OCR pass compares each expected line at its rendered
vertical position. Only whitespace is normalized: missing `=`, punctuation,
case changes and missing lines do not pass. OCR disagreement or engine failure
is `unverified`, not proof that the palette is defective. Font identity, exact
indentation, and character-shape fidelity are not certified by these checks.

The attribute probe deliberately contains white ANSI text on the light canvas;
those incompatible pairs are exposed as findings, not hidden or changed during
evaluation. The six real command cases are reported separately. Full native
acceptance remains incomplete because native Neovim/Codex workflows and font identity remain unverified. An OCR error never silently falls back to a passing pixel-only verdict.

Tests include blank/clipped calibration, erased glyphs, low-contrast cells,
tiny punctuation, altered comparison operators, omitted lines, and unsupported
ANSI control sequences. Captured PNG and ANSI hashes are recorded in the text
report. Existing fixtures must match the capture's stored ANSI hash and the
current theme must match its stored theme hash before analysis proceeds.

OCR now runs on isolated full-width terminal rows rather than a whole-window
image. Each crop is padded and scaled 2× to avoid adjacent-line merges. Saved
`ocr-rows/` images make recognition input reviewable. The engine receives row
numbers and PNG paths only—not expected text or custom-word hints. Comparison
still uses its top candidate and preserves every non-whitespace character;
`<`, `<=`, and the look-alike `‹=` are distinct. Pixel checks continue to use the
original unscaled screenshot. Engine failure remains unverified.


### Independent punctuation recognition

New captures include a separate ASCII reference sheet, rendered by Ghostty under
the same configuration in normal, bold, italic, and underline combinations. This
uses another scene in the same reusable fixture window. On OCR-mismatched rows, the analyzer classifies every
cell against the full reference alphabet; it never chooses a template using the
expected command character. Full 120-column rows must agree, including unexpected
suffixes. Shape distance must be at most 0.08 with a 0.04 lead over the next glyph;
ambiguous shapes remain unverified. Independent pixel/contrast checks still gate
acceptance. Reference PNG, payload, geometry, and classifier hashes are recorded.
Old captures without this sheet retain their OCR results; rerun native capture
to use the additional recognizer. The first native reference run passed all six real command fixtures and recovered
their OCR omissions. An offline mutation of that native diff passed unchanged and
was rejected after erasing the equals sign in `<=`. The white-on-white ANSI probe
still fails as intended. Synthetic mutation tests additionally cover replaced
operators and unexpected suffixes. Ligatures or differing rasterization may
remain unverified.

### Native steady block cursor

New captures also include `cursor-block`: the terminal receives a steady-block
cursor escape sequence and positions its actual cursor over the `=` in
`return attempt <= 3`. The emitter does not paint a replacement cursor. Its cell
must have the configured cursor fill and foreground, meet the 4.5:1 rendered
stroke contrast floor, and independently resolve to `=` against the native ASCII
reference sheet. Normal command text checks still apply to the rest of the row.
Missing fill, an outline cursor, erased or replaced glyphs cannot pass this gate.
The JSON report records cursor evidence separately from command text evidence.

Run `uv run tintprobe ghostty --capture` to capture this case. Previous captures do not
establish coverage for newly added interactions.

### Cursor modes and real mouse selection

The native stage also requests steady bar and underline cursors, hidden cursors,
and blinking block/bar/underline cursors. Bar and underline checks enforce the
cursor's location, extent, and palette color, plus readable underlying glyphs.
Only exact cursor-colored strip pixels are removed for glyph/OCR recognition;
original pixels still undergo the independent cursor and text checks. A sequence
of 16 timed frames must contain at least two on frames, two off frames, and two
transitions before blinking passes. A static or unrecognizable cursor cannot pass.
A separate same-window sequence exercises bar → block → underline → hidden → block,
with an acknowledgment after each native escape sequence and a screenshot per
state. These are terminal protocol tests, not claims that every extras/shell/plugin's
vi-mode hooks are configured correctly.

Mouse tests drag through a substring containing `<=` and across two lines. One
fixture includes blue ANSI text to verify that selection overrides its foreground.
The analyzer checks selected spaces and unselected neighbors as well as text:
missing selection, selection beyond the expected range, wrong fill, white text,
and damaged operators do not pass. Coordinates come from the captured terminal
grid and are converted to window-relative fractions for Retina displays. The
selection is native mouse input, not an ANSI-painted background or clipboard paste.

Native Ghostty may place a one-pixel bar immediately left of the inferred cell
boundary. Shape and hidden-phase checks include that single boundary pixel;
OCR cleanup uses the same boundary. A bar farther away, an erased bar, and an
erased covered glyph remain rejected. This allowance changes neither the
palette nor the contrast or independent glyph-classification thresholds.

In addition to Screen Recording, the helper needs **Accessibility** permission
for window focus and mouse input. It checks permission without prompting. A
missing permission produces a blocked run with the native error retained. Grant
permission to the helper identified by macOS, then rerun from your terminal.
The worker raises its own uniquely titled fixture window; it refuses input if
identity, focus, or ownership at the target coordinates changes. It never sends
input to your ordinary Ghostty windows. Keep this desktop session free of other
mouse/keyboard activity while the native interaction cases run. No clipboard or
shell-history access is involved.

The palette remains frozen. Tests mutate synthetic captures to ensure wrong
shapes, static blinking, missing/overextended selection, and altered text cannot
pass. A September 12, 2026 authorized native run, reanalyzed after the bar-boundary
repair, passed six command cases, eight cursor cases (including three timed blink
sequences and all five transition states), and both mouse selections. Selection
text measured 4.622:1 against the unchanged 4.5:1 floor. The white-on-white
attribute probe still failed as intended. Local evidence is in
`evaluation/results/ghostty-validation-20260912/quality.json` and `quality.html`;
`report.json` retains the original pre-repair analysis. Native-image mutation
controls in `bar-mutation-controls.json` reject erased/misplaced bars and an
erased equals sign. These results apply to this capture, not every installation.
Inactive-window
cursor appearance, shell-specific mode hooks, native Neovim/Codex sessions, and
long-session comfort remain outside this interaction set. The report lists
cursor and selection case counts separately from full native acceptance.


## Targeted capture and offline iteration

Prefer a short acquisition while developing checks:

```sh
uv run tintprobe ghostty --output evaluation/results/native-smoke \
  --capture --cases git-status cursor-block selection-single neovim-diff
```

The glyph reference is included automatically. `omitted_cases` explicitly lists
what was left out; a targeted run never establishes complete coverage. The
window closes before the more expensive offline analysis starts. Reuse saved
images with `uv run tintprobe images --output ...`; this does not open
Ghostty. Reanalysis updates `report.json` and its quality hash as well as
`quality.json`, so headline counts no longer describe an obsolete analysis.
A changed theme still requires fresh captures.

## Live Neovim scenes

`neovim-diff`, `neovim-search`, `neovim-selection`, `neovim-diagnostic`, and
`neovim-completion` launch a real Neovim TUI inside the reusable Ghostty window.
They require Neovim and the pinned Kanso checkout. Temporary state and an RPC
socket are isolated; installed configuration is not changed. The same running
Neovim records the final RGB redraw cells through an observational UI at the same
dimensions. Checks
compare cell backgrounds, foreground strokes, and independently recognized
glyphs against the screenshot. The fixed reference alphabet includes printable
ASCII and selected UI punctuation with confusable alternatives; other glyphs
remain unverified.
The cursor cell belongs to the separate native cursor suite.

The one-character diff must expose the edited equals sign on the emphasis
background, using ordinary weight without underline. These are selected live
workflows, not complete coverage of every plugin, language server, fallback
font, terminal size, or agent application. Individual results remain failed or
unverified until fresh native evidence satisfies their gates.


## Shell keymaps and inactive focus

`shell-vicmd` and `shell-viins` run real zsh ZLE in an isolated PTY and show its
output in the same Ghostty window. Fixture-local conventional keymap hooks set
block/bar cursors; the raw keymap and `main` alias binding are recorded. Editing
input navigates to the equals sign but never accepts or executes the buffer.
Closing the owned PTY terminates its shell. These cases test real ZLE behavior,
not arbitrary hooks in the user's installed dotfiles.

`cursor-inactive-block` restores the application that was active before the run,
without opening a second test window. It checks a hollow cursor and its intact
underlying glyph. On hosts that place these apps on different macOS Spaces,
the inactive window may be unavailable to screenshot capture. This is recorded
as blocked, and the other scenes continue. No other window is substituted.

## Native Codex replay in Ghostty

The full suite passes its newly produced native flow cells into the terminal
stage. A targeted run may supply an existing `--codex-cells PATH`; the sibling
report must pass and match the current exported theme hash. All flow stages at
both recorded widths are presented as RGB/SGR cells in Ghostty, preserving bold,
italic, underline, and DIM attributes. The source revision, cell hashes, and
presentation scope remain explicit. This is terminal-pixel validation of native
renderer replay, not a live model or app-server session. Oversized viewports and
unknown modifiers fail preparation instead of being silently clipped or dropped.

DIM deliberately changes the foreground, so its nominal RGB match is not a gate;
its actual measured stroke contrast still must reach 4.5:1. Ordinary cells retain
both exact-color and contrast checks. Diff emphasis backgrounds require ordinary
weight without added underline. User-visible dim text that fails the contrast
floor remains a finding; the evaluator does not alter faint opacity to pass.

## Evidence from the single-window runner

The September 12 live Neovim capture in
`evaluation/results/ghostty-native-workflows/` passed all five scenes after
independent reanalysis. The unchanged native diff passed, erasing its edited
`=` failed, and a bold-emphasis contract mutation failed. The two real zsh
keymaps passed in `evaluation/results/ghostty-shell-keymaps-verified/`.
Their `session-cleanup.json` files confirm the owned window was closed.
These are scoped results, not a claim of complete native coverage.
