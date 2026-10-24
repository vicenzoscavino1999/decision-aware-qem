"""Render the five empirical manuscript figures from the corrected sources."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
CODE=Path(__file__).resolve().parents[1]


def render(package,output):
    output.mkdir(parents=True,exist_ok=True);records=[]
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def register(name,sources,series=None):
        records.append(dict(figure=name,sha256=sha(output/name),sources={p.relative_to(package).as_posix():sha(p) for p in sources},series=series))
    proof=package/'evidence/cdr_pec/results/proof_of_mechanism/result.json'
    table=pd.DataFrame(json.loads(proof.read_text())['aggregate']['table'])
    series=table[table.method.isin(['Raw','CDR','PEC'])].sort_values(['method','budget'])
    series.to_csv(output/'F1_series.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(8.8,3.4),sharex=True)
    for method,marker,label in [('Raw','o','Raw'),('CDR','s','CDR affine control'),('PEC','^','PEC effective-shot proxy')]:
        sub=series[series.method==method]
        axes[0].plot(sub.budget,sub.MSE_mean,marker=marker,label=label)
        axes[1].plot(sub.budget,sub.GRI_mean,marker=marker,label=label)
    for ax,title,ylabel in zip(axes,['Estimator accuracy','Gaussian decision risk'],['Empirical MSE','GRI']):
        ax.set(title=title,xlabel='Evaluation budget per candidate',ylabel=ylabel);ax.set_xscale('log',base=2);ax.minorticks_off();ax.grid(alpha=.25)
        ax.set_xticks([768,1536,3072,6144],labels=[768,1536,3072,6144])
    axes[1].legend(frameon=False,fontsize=8);fig.tight_layout();fig.savefig(output/'F1_accuracy_decision_separation.png',dpi=160,bbox_inches='tight');plt.close(fig)
    register('F1_accuracy_decision_separation.png',[proof],'F1_series.csv')
    source=package/'evidence/learned_ablation/results/pilot/gate0_full_vs_diagonal.csv'
    table=pd.read_csv(source);table.to_csv(output/'F6_series.csv',index=False)
    fig,ax=plt.subplots(figsize=(5,4.5))
    for changed,label,marker,color in [(False,'Selector unchanged','o','#4C78A8'),(True,'Selector changed','x','#E45756')]:
        group=table[table.selector_changed==changed]
        if len(group):ax.scatter(group.gri_diagonal,group.gri_full,label=label,marker=marker,color=color,alpha=.8)
    ax.plot([0,1],[0,1],'k--',lw=1,label='Full = diagonal');ax.set(xlim=(0,1),ylim=(0,1),xlabel='GRI diagonal',ylabel='GRI full',title='Covariance diagnostic: 24 cells, 72 method rows')
    ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(output/'F6_gate0_full_vs_diagonal.png',dpi=160);plt.close(fig)
    register('F6_gate0_full_vs_diagonal.png',[source],'F6_series.csv')
    for script,source,name in [('plot_corrected_e1.py','results/e1/summary.csv','F7_e1_reanalysis.png'),
                               ('plot_corrected_e2.py','results/e2/e2_full_ledger.csv','F8_dynamic_full_cost.png')]:
        subprocess.run([sys.executable,str(CODE/script),'--input',str(package/source),'--output',str(output/name)],check=True)
        register(name,[package/source])
    source=package/'results/confirmatory/e3_independent_mean_and_failure.csv';frontier=package/'results/confirmatory/e3_pullback_frontier.csv'
    subprocess.run([sys.executable,str(CODE/'plot_corrected_e3.py'),'--input',str(source),'--frontier',str(frontier),
                    '--output',str(output/'F9_e3_comparisons.png'),'--series-output',str(output/'F9_e3_series.csv')],check=True)
    register('F9_e3_comparisons.png',[source,frontier],'F9_e3_series.csv')
    (output/'figure_sources.json').write_text(json.dumps(records,indent=2)+'\n')
    return records


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=CODE.parent);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    render(a.package.resolve(),a.output_dir.resolve())
