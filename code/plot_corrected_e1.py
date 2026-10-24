"""Plot the revised E1 table and its paired instance-bootstrap intervals."""
from pathlib import Path
import argparse
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, default=ROOT/'results/e1/summary.csv')
parser.add_argument('--output', type=Path, default=ROOT/'manuscript/figures/F7_e1_reanalysis.pdf')
args = parser.parse_args()
df = pd.read_csv(args.input)
policies = ['Raw', 'Accuracy-ZNE', 'Decision-ZNE', 'MSE-selector', 'GRI-selector']
labels = ['Always Raw', 'Accuracy-ZNE', 'Decision-ZNE', 'MSE selector', 'GRI selector']
colors = ['#255A78', '#7E929F', '#A1AEB6', '#A95545', '#207A66']
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'pdf.fonttype': 42, 'ps.fonttype': 42})
fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.8), sharey=True)
for ax, comparison, title in zip(axes, ['evaluation', 'end_to_end'],
        ['Equal evaluation shots', 'Equal full cost, including learning'], strict=True):
    sub = df[(df.base_t == 512) & (df.comparison == comparison) &
             (df.kind == 'failure_rate')].set_index('policy')
    for y, policy in enumerate(policies):
        row = sub.loc[policy]
        ax.errorbar(100*row.estimate, y,
            xerr=[[100*(row.estimate-row.ci_low)], [100*(row.ci_high-row.estimate)]],
            fmt='o', color=colors[y], capsize=3, markersize=6, lw=1.7)
        ax.annotate(f'{100*row.estimate:.2f}%', (100*row.estimate, y), xytext=(0, 9),
            textcoords='offset points', ha='center', fontsize=9, color=colors[y])
    ax.set_title(title, fontsize=11, pad=12)
    ax.set_xlabel('Test failure (%) - lower is better')
    ax.set_xlim(10, 62)
    ax.set_yticks(range(len(policies)), labels)
    ax.grid(axis='x', alpha=.2)
axes[0].invert_yaxis()
fig.suptitle('Retrospective E1 comparison | 48 instances | 10 fit / 10 select / 20 test', fontsize=12, y=1.01)
fig.tight_layout()
args.output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.output, bbox_inches='tight')
plt.close(fig)
