# Evaluator validation

`uv run tintprobe validate --output evaluation/results/validation`

The combined suite runs this automatically as a required stage. It captures native Neovim cells after applying temporary highlight overrides inside the isolated editor. It never edits the palette, installed themes, or existing screenshots.

Two separate Python fixtures exercise a boundary operator insertion and a string replacement at 100 and 160 columns. They are excluded from the palette-tuning corpus. Their contents are hashed in the report. Once inspected and used for tuning they should no longer be described as unseen; add fresh cases periodically.

Four controls run for each fixture and width:

- Baseline must pass all gates.
- Making inline foreground equal to its background must trigger text contrast failure.
- Merging inline and changed-line backgrounds must trigger critical inline background failure.
- A contrasting purple inline background must pass, checking that the evaluator does not require amber.

Each negative must trigger its named failure in every fixture/width. An unrelated failure cannot satisfy the control. Native cell captures and the complete gate evidence are saved for inspection.

This validates sensitivity to these specific faults, not human task performance, complete score calibration, or long-session comfort. Numerical scores can saturate; hard failures remain authoritative. The holdout is small and should grow independently of palette optimization. Overlay oracle mutations are additionally covered by unit tests; this native validation currently targets plain diff rendering.
