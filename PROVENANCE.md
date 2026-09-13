# Extraction provenance

Tintprobe was extracted from [Ithilien](https://github.com/achandran/ithilien)
at commit `b52f53f28763449c20c2a8a2df434b0138829bb2`. The first Tintprobe commit retains the parent
repository history; renamed files can be followed through that history. See
`migration.json` for the list of extracted engine modules and retained project
workflow adapters.

Color mathematics, native capture, source fixtures, image checks, and reporting
moved here. Ithilien keeps authoring rules, exact palette identity tests, export
generators, and tests for its own plugin behavior. Frozen reference data under
`tests/fixtures/reference` only supports evaluator regression tests.

The APCA implementation identifies its W3/SAPC origin in `tintprobe/colors.py`.
Codex-derived fixture licensing is retained at
`tintprobe/data/fixtures/codex/LICENSE`. Pinned upstream sources are fetched
separately and retain their own licenses. This extraction does not relicense
third-party material or imply that measured themes endorse the tool.
