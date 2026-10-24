PYTHON ?= python
OUTPUT ?= /tmp/daqem-reproduction
WORKERS ?= 8
.PHONY: reproduce-fast reproduce-analysis reproduce-all test docker
reproduce-fast:
	$(PYTHON) reproduce.py --mode fast --output $(OUTPUT)
reproduce-analysis:
	$(PYTHON) reproduce.py --mode analysis --workers $(WORKERS) --output $(OUTPUT)
reproduce-all:
	$(PYTHON) reproduce.py --mode all --workers $(WORKERS) --output $(OUTPUT)
test:
	$(PYTHON) code/scripts/run_regression_tests.py --output-dir $(OUTPUT)
docker:
	docker build --platform linux/amd64 -t daqem:1.2.0 .
