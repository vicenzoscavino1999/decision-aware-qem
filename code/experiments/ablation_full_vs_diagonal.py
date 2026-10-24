"""Reanalyze the existing Gate 0 covariance ablation without new shots."""
import argparse
from pathlib import Path
from experiments.gate0_pilot_full_vs_diagonal import run_analysis

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profile',default='full')
    args=parser.parse_args()
    frame=run_analysis(args.output,args.profile)
    print(f"Reanalyzed {len(frame)} method/budget rows from saved samples")
