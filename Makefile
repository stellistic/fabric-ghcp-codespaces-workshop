UV ?= uv
PY = $(UV) run python
APPROVE_PLAN ?=
CONFIG ?= demo.local.yaml
NOTEBOOK ?= bronze
PARTICIPANT ?=
APPROVE_WORKSPACE ?=
TIMEOUT ?= 900
export APPROVE_PLAN CONFIG NOTEBOOK PARTICIPANT APPROVE_WORKSPACE TIMEOUT

.PHONY: setup config discover curate source.months offline data.build test lint build gates \
	dict.validate notebooks.build notebooks.check expected.build expected.check \
	report.fault report.check report.plan report.repair report.restore \
	fabric.preflight fabric.inventory fabric.publish fabric.run fabric.results

setup:
	$(UV) sync --frozen

config:
	$(PY) -m workshop.cli config

discover:
	$(PY) -m workshop.cli discover

curate:
	$(PY) -m workshop.cli curate

source.months:
	$(PY) -m workshop.cli source-months

offline: config dict.validate discover curate source.months

data.build:
	$(PY) -m tools.kit.build

dict.validate:
	$(PY) -m workshop.cli validate

notebooks.build:
	$(PY) -m tools.notebooks.build

notebooks.check:
	$(PY) -m tools.notebooks.build --check

expected.build:
	$(PY) -m tools.kit.expected_doc

expected.check:
	$(PY) -m tools.kit.expected_doc --check

report.fault:
	$(PY) -m workshop.cli report-fault

report.check:
	$(PY) -m workshop.cli report-check

report.plan:
	$(PY) -m workshop.cli report-plan

report.repair:
	$(PY) -m workshop.cli report-repair --approve-plan "$$APPROVE_PLAN"

report.restore:
	$(PY) -m workshop.cli report-restore --approve-plan "$$APPROVE_PLAN"

fabric.preflight:
	$(PY) -m workshop.live --config "$$CONFIG" preflight

fabric.inventory:
	$(PY) -m workshop.live --config "$$CONFIG" inventory

fabric.publish:
	$(PY) -m workshop.live --config "$$CONFIG" publish-notebook \
		--notebook "$$NOTEBOOK" --participant "$$PARTICIPANT" --approve-workspace "$$APPROVE_WORKSPACE"

fabric.run:
	$(PY) -m workshop.live --config "$$CONFIG" --timeout "$$TIMEOUT" run-notebook \
		--notebook "$$NOTEBOOK" --participant "$$PARTICIPANT" --approve-workspace "$$APPROVE_WORKSPACE"

fabric.results:
	$(PY) -m workshop.live --config "$$CONFIG" get-results \
		--notebook "$$NOTEBOOK" --participant "$$PARTICIPANT"

test:
	$(PY) -m pytest

lint:
	$(UV) run ruff check workshop tools tests
	bash -n .devcontainer/post-create.sh
	bash -n .devcontainer/fabric-terminal.sh

build: notebooks.check expected.check dict.validate

gates: lint test build
