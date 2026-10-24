"""Canonical offline entry point. Raw simulation regeneration is a separate mode."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['PYTHONPATH']=os.pathsep.join((str(ROOT/'code/src'),str(ROOT/'code')))
sys.path[:0]=[str(ROOT/'code/src'),str(ROOT/'code')]
from scripts.release_pipeline import main
if __name__=='__main__':
    raise SystemExit(main(ROOT))
