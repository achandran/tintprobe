# Development

```sh
uv sync --locked
uv run pytest
uv build
```

Tests include synthetic measurements, deliberately damaged captures, dependency
pinning, subprocess cleanup, and project-independence checks. The reference palette
under `tests/fixtures/reference` is frozen input data for regressions; the package
never uses it as a runtime default and does not ship test data in wheels.

For native regression coverage, run `tintprobe compare` against at least two themes.
Check both execution status and per-theme findings; a successful capture is not a
claim that every theme passes the configured rubric. Preserve evidence of failures.

UI replay and native terminal capture are separate capability layers. Native
Ghostty capture is never run by pytest or by the default comparison command.
Heavy Rust builds, source checkouts, and captured images are ignored caches.

The public CLI and role/config schema start at version 0.1.0. Consumers should pin
an exact Git revision while the adapter interface is stabilizing. Publish changes
only after both Tintprobe tests and a consuming project's policy tests pass.
