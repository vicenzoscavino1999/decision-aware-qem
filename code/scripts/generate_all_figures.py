"""Compatibility entry point for the corrected empirical figure sources."""
from pathlib import Path
import argparse
from plot_integrated_figures import render

if __name__=='__main__':
    package=Path(__file__).resolve().parents[2]
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    render(package,a.output_dir.resolve())
