VENV ?= ../.venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ARCHIVE := data/knapsack.zip
V1_ARCHIVE := ../iscmi2026/data/knapsack.zip
ARCHIVE_URL := https://codeload.github.com/JorikJooken/knapsackProblemInstances/zip/refs/heads/master
ARCHIVE_SHA256 := 68ef9b6be17fbc37f303a250aa79cacfcbe7167d5f0b83f8f96c60d666f0fb26
APPROVER ?=
RUN_ENV := PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1 MPLBACKEND=Agg MPLCONFIGDIR=tmp/matplotlib

.PHONY: setup kernel data verify-history prepare prepare-transfer test smoke development tune survivors lock-protocol final-train evaluate solve-unresolved confirmatory analyze notebook verify

setup: $(VENV)/.iscmi-v2-dependencies

kernel: setup
	mkdir -p tmp/jupyter-config tmp/ipython jupyter
	IPYTHONDIR=tmp/ipython JUPYTER_CONFIG_DIR=tmp/jupyter-config $(PYTHON) -m ipykernel install --prefix jupyter --name iscmi2026-v2 --display-name "Python (.venv — ISCMI 2026 V2)"

$(VENV)/bin/python:
	python3 -m venv $(VENV)

$(VENV)/.iscmi-v2-dependencies: requirements.txt $(VENV)/bin/python
	$(PIP) install -r requirements.txt
	touch $@

data: $(ARCHIVE)
	printf '%s  %s\n' $(ARCHIVE_SHA256) $(ARCHIVE) | shasum -a 256 -c -

$(ARCHIVE):
	mkdir -p data
	cp $(V1_ARCHIVE) $(ARCHIVE)

verify-history:
	shasum -a 256 -c protocol/history_manifest.sha256

prepare: setup data verify-history
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli prepare

prepare-transfer: setup
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli prepare-transfer

test: setup
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m pytest -q

smoke: setup data
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli smoke

development: prepare test smoke

tune: development
	mkdir -p tuning/work
	Rscript tuning/run_irace.R

survivors: setup data
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli survivors

lock-protocol: setup
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli lock --approver "$(APPROVER)"

final-train: setup data
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli train-final

evaluate: setup data
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli evaluate

solve-unresolved: setup data
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli solve-unresolved

confirmatory: final-train evaluate solve-unresolved

analyze: setup
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.analysis
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.figures

notebook: setup
	$(MAKE) kernel
	$(RUN_ENV) IPYTHONDIR=tmp/ipython JUPYTER_CONFIG_DIR=tmp/jupyter-config JUPYTER_PATH=jupyter/share/jupyter PYTHONPATH=. $(PYTHON) -m src.build_notebook --execute

verify: setup data verify-history
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli verify
