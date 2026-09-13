# Stock Codex UI validation

A project may provide a Codex configuration profile through `ports.codex_config` that sets
`tui.animations = false`, the supported motion preference documented in the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Merge this setting into your Codex config manually, preserving other settings,
and restart Codex. The evaluator reads the repository profile directly; it does
not edit your installed configuration.

This removes the stock status shimmer and effort-change composer particles. The
project palette and exported theme files are unchanged. Stock Codex's TextMate
theme controls syntax highlighting, not separate transcript metadata colors or
the composer border. The composer and past user messages retain their shared
stock surface. These limitations are recorded in the UI evaluation report.

Run the targeted evaluation with the pinned Codex source and Rust runtime used
by the main suite:

```sh
uv run tintprobe codex-ui --source evaluation/deps/codex
```

It also requires `just` and `cargo-nextest`, following the pinned source's test
instructions. `uv run tintprobe suite` includes the same UI stage. The runner temporarily
adds test instrumentation and configures the test helper from the configured `ports.codex_config`;
it restores both upstream test files even on failure. Production renderer files
are never patched. Do not evaluate concurrently against the same checkout.

The replay records 48 native Ratatui frames: low, max, and ultra effort at 60 and
100 columns, with eight frames spanning at least two seconds per case. It
exercises genuine effort transitions, then checks:

- Complete frame geometry and exact working/placeholder text.
- A 4.5:1 nominal text-contrast floor in every frame.
- Steady status and composer cells throughout each reduced-motion sequence.
- Exact empty-composer contents, including padding rows and trailing blanks;
  particles and uneven background fills cannot pass.

Terminal `DIM` remains **unverified**, not a contrast pass based on undimmed RGB.
The stock placeholder uses it, so a clean reduced-motion replay currently exits
nonzero with `status: unverified`. Strict combined acceptance is blocked by this
unverified quality result even though replay execution completes. A future native
Ghostty pixel replay is needed to certify that text. These cell exports are not
screenshots, font validation, or evidence of long-session comfort. They do not
prove a running session has reloaded the config or that a higher-priority config
layer has not overridden it.

Results are in `evaluation/results/codex-ui/report.json`, `codex-ui-cells.json`,
`native.log`, and `codex-gallery.html`. Reports retain source revision and
profile, adapter, analyzer, and cell hashes. Nominal contrast is explicitly named
to distinguish it from rendered stroke contrast.

For a native negative control that enables animations only in the isolated test:

```sh
uv run tintprobe codex-ui --source evaluation/deps/codex --animated-control \
  --output evaluation/results/codex-ui-animated-control
```

On September 12, 2026 this control failed at a minimum nominal text contrast of
3.943:1 and exposed composer artifacts. The installed profile remained disabled.
Synthetic mutation tests also reject a single bad phase, missing frames/text,
uneven fills, and changing colors even when each color remains readable.
