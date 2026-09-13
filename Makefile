.DEFAULT_GOAL := help
UV ?= uv
.PHONY: help test build compare
help:
	@printf '%s\n' 'Tintprobe: make test | make build | make compare' 'Native desktop capture is opt-in through tintprobe ghostty --capture.'
test:
	$(UV) run --locked pytest
build:
	$(UV) build
compare:
	$(UV) run --locked tintprobe compare
