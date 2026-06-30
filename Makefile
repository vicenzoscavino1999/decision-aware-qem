reproduce: reproduce-full verify

run:
	python reproducibility/run_all.py

verify:
	python reproducibility/verify.py --reference reproducibility/reference/

verify-confirmatory:
	python scripts/verify_confirmatory.py

verify-extension:
	python scripts/verify_extension.py

reproduce-all:
	python scripts/reproduce_all.py

archive-confirmatory:
	python scripts/archive_confirmatory_outputs.py

figures:
	python scripts/generate_all_figures.py

test:
	pytest tests/ -v

check: test verify

check-env:
	python reproducibility/run_all.py --check-env-only

reproduce-fast:
	python reproducibility/run_all.py --mode fast --level 1
	python reproducibility/verify.py --reference reproducibility/reference_level1/

reproduce-level1:
	python reproducibility/run_all.py --level 1
	python reproducibility/verify.py --reference reproducibility/reference_level1/

reproduce-pilot:
	python reproducibility/run_all.py --stage pilot
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-confirmatory:
	python reproducibility/run_all.py --stage confirmatory
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-full:
	python reproducibility/run_all.py --mode full --levels 1,2
	python reproducibility/verify.py --reference reproducibility/reference/

analysis-from-hardware:
	python reproducibility/run_all.py --level 3 --from-archived-counts
	python reproducibility/verify.py --reference reproducibility/reference/

determinism-check:
	python reproducibility/run_all.py --mode fast --level 1 --output results/determinism-run-1
	python reproducibility/run_all.py --mode fast --level 1 --output results/determinism-run-2
	python reproducibility/verify.py --reference results/determinism-run-1 --generated results/determinism-run-2 --exact-numeric
