from pathlib import Path
import argparse
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser()
p.add_argument('--input',type=Path,default=root/'results/e2_full_ledger.csv')
p.add_argument('--output',type=Path,default=root/'manuscript/figures/F8_dynamic_full_cost.pdf')
args=p.parse_args()
ledger=pd.read_csv(args.input)
fig,ax=plt.subplots(figsize=(7.4,4.3))
for selector,label,color in [('DA','GRI selector','#0072B2'),('MSE','MSE selector','#D55E00')]:
    sub=ledger[ledger.selector==selector].groupby('budget')[['total_shots_per_trajectory','success_rate']].mean()
    ax.plot(sub.total_shots_per_trajectory/1e6,sub.success_rate,'o-',label=label,color=color)
ax.axhline(.8,color='black',ls='--',lw=1,label='Target 0.80')
ax.set(xlabel='Mean full shots per trajectory (millions)',ylabel='Mean success probability',ylim=(.35,.84))
ax.grid(alpha=.2);ax.legend(frameon=False);fig.tight_layout()
output=args.output;output.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(output)
print(output)
