VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
WORKERS ?= 4
RUN_ENV := PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1 MPLBACKEND=Agg MPLCONFIGDIR=tmp/matplotlib

.DEFAULT_GOAL := help
.PHONY: help setup test fetch-data fetch-results fetch verify-artifacts verify-provenance verify-inputs verify smoke paper-figures analyze reproduce kernel notebook final-train evaluate solve-unresolved confirmatory

help:
	@echo "setup             Install the pinned Python environment in .venv"
	@echo "paper-figures     Rebuild fig01.pdf, fig02.pdf, fig03.pdf from compact tables"
	@echo "fetch             Restore checksum-verified benchmark and raw-result bundles"
	@echo "test              Run the unit and provenance tests"
	@echo "verify            Verify frozen sources, data, runs, models, and evaluations"
	@echo "reproduce         Verify inputs and rebuild statistics and paper figures"
	@echo "notebook          Rebuild and execute the explanatory notebook"
	@echo "final-train       Train/resume the frozen final experiment (expensive)"

setup:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m pytest -q

fetch-data:
	$(PYTHON) scripts/artifacts.py fetch data

fetch-results:
	$(PYTHON) scripts/artifacts.py fetch results

fetch: fetch-data fetch-results

verify-artifacts:
	$(PYTHON) scripts/artifacts.py verify all

verify-provenance:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -c 'from src.protocol import verify_history; print("\n".join(verify_history()))'

verify:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli verify

verify-inputs:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) scripts/verify_analysis_inputs.py

smoke:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli smoke

paper-figures:
	$(RUN_ENV) $(PYTHON) paper/build_figures.py

# Require all evaluations before analysis; missing transfer inputs must fail.
analyze: verify-inputs
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.analysis
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.figures

reproduce: analyze
	$(MAKE) paper-figures

kernel:
	mkdir -p tmp/jupyter-config tmp/ipython jupyter
	IPYTHONDIR=tmp/ipython JUPYTER_CONFIG_DIR=tmp/jupyter-config $(PYTHON) -m ipykernel install --prefix jupyter --name iscmi2026-v2 --display-name "Python (.venv — ISCMI 2026 V2)"

notebook: kernel
	$(RUN_ENV) IPYTHONDIR=tmp/ipython JUPYTER_CONFIG_DIR=tmp/jupyter-config JUPYTER_PATH=jupyter/share/jupyter PYTHONPATH=. $(PYTHON) -m src.build_notebook --execute

final-train:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli train-final --workers $(WORKERS)

evaluate:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli evaluate

solve-unresolved:
	$(RUN_ENV) PYTHONPATH=. $(PYTHON) -m src.cli solve-unresolved --workers $(WORKERS)

confirmatory:
	$(MAKE) final-train
	$(MAKE) evaluate
	$(MAKE) solve-unresolved
