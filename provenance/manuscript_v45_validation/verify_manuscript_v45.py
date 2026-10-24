"""Check key reported quantities and plotted data against the bundled results.

Adapted for v45: read its source and PDF, compare empirical claims and unchanged figures
against the separate v4 reproduction package. This is a consistency check, not a new
mathematical or statistical validation. No scientific analysis is rerun.
"""
from pathlib import Path
import argparse,hashlib,json,re
import pandas as pd
import pymupdf

MANUSCRIPT_ROOT=Path(__file__).resolve().parents[1]
# --package is the unchanged v4 reproduction package supplying scientific evidence.
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(package):
    tex=(MANUSCRIPT_ROOT/'manuscript/main.tex').read_text(encoding='utf-8')
    checks={}
    def read(rel):return json.loads((package/rel).read_text(encoding='utf-8'))
    def present(name,phrase):
        if phrase not in tex:raise ValueError(f'Manuscript mismatch: {name}: {phrase}')
        checks[name]=phrase
    pom=read('evidence/cdr_pec/results/proof_of_mechanism/result.json')
    lo,hi=pom['cdr_slope_range'];present('cdr_slopes',f'a\\in[{lo:.3f},{hi:.3f}]')
    present('pec_model',r'n_{\rm eff}=\lfloor B/\gamma^2\rfloor')
    present('pec_covariance',r'\Sigma_{\rm ideal}/n_{\rm eff}')
    e1=pd.read_csv(package/'results/e1/summary.csv')
    methods=['Raw','Accuracy-ZNE','Decision-ZNE','MSE-selector','GRI-selector']
    for budget in (512,1024):
        for comp,title in [('evaluation','Evaluation only'),('end_to_end','Full cost')]:
            rows=e1[(e1.base_t==budget)&(e1.comparison==comp)&(e1.kind=='failure_rate')].set_index('policy')
            phrase=f'{budget} & {title} & '+' & '.join(f'{rows.loc[m,"estimate"]:.4f}' for m in methods)
            present(f'e1_table_{budget}_{comp}',phrase)
    e3=read('results/confirmatory/e3_summary.json')
    present('e3_active',f'all {e3["active_pairs"]} selected active pairs; {e3["directionally_sensitive_pass"]} satisfy the original directional criterion and {e3["fail"]} do not')
    counts=e3['covariance_score_vs_all40_failure']
    present('e3_all40',f'{counts["match"]} strict matches, {counts["reversal"]} reversals and {counts["ties"]} ties')
    counts=e3['method_mean_train_vs_independent_test']
    present('e3_train_test',f'{counts["match"]} strict matches, {counts["reversal"]} reversals and {counts["ties"]} ties')
    e2=read('results/e2/e2_summary.json')
    present('e2_da_max',f'${e2["pooled_max_success"]["DA"]:.4f}$')
    present('e2_mse_max',f'${e2["pooled_max_success"]["MSE"]:.4f}$')
    present('e2_crossings',f'${e2["median_full_cost_ratio_MSE_over_DA"]:.2f}$ on the {e2["both_cross_instances"]} instances')
    present('e2_ties','exact estimator ties retain the first candidate within a batch and the earlier incumbent across rounds')
    fk=read('results/fakekolkata_fixed10/summary.json')
    present('fake_mse_gri',f'${fk["failure_rates"]["MSE-selector"]:.4f}$ for MSE selection and ${fk["failure_rates"]["GRI-selector"]:.4f}$ for GRI selection')
    present('fake_raw',f'Always-Raw has failure ${fk["failure_rates"]["Raw"]:.4f}$')
    low,high=fk['relative_reduction_cluster_ci'];present('fake_relative_ci',f'[{low:.4f},{high:.4f}]')
    low,high=fk['paired_difference_GRI_minus_Raw_cluster_ci'];present('fake_raw_ci',f'[{low:.4f},{high:.4f}]')
    h=read('results/hardware/hardware.json');g=h['gate_c1']
    present('hardware_heldout',f'held-out error ${g["heldout_relative_generalization_error"]:.3f}$')
    present('hardware_fit_split',f'{len(g["fit_indices"])} characterization records')
    present('hardware_test_split',f'{len(g["heldout_indices"])} reserved records')
    present('hardware_full_fit',f'all {h["characterization"]["circuit_count"]} records')
    for pair in h['corrected_endpoint']['pairs']:
        expected=' & '.join([f'${pair["delta_rank"]:.7f}$',f'${pair["ucb95"]:.7f}$',f'${pair["threshold"]:.8f}$'])
        present('hardware_pair_'+'_'.join(pair['pair']),expected)
    initial=read('evidence/hardware/results/characterization_comparison.json')['attempt1']['corrected']['heldout_relative_generalization_error']
    present('hardware_initial',f'held-out generalization error ${initial:.2f}$')
    for method,stats in h['secondary_frobenius']['methods'].items():
        present('frobenius_'+method,f'${stats["relative_frobenius_error"]:.3f}$ for {method}')
    ablation=pd.read_csv(package/'evidence/learned_ablation/results/pilot/gate0_full_vs_diagonal.csv')
    assert len(ablation)==72 and not ablation.selector_changed.any()
    present('ablation_cells','all 24 instance--budget cells, represented by 72 method rows')
    figures=read('manuscript/figures/figure_sources.json')
    assert len(figures)==5
    for fig in figures:
        assert sha(package/'manuscript/figures'/fig['figure'])==fig['sha256']
        assert sha(MANUSCRIPT_ROOT/'manuscript/figures'/fig['figure'])==fig['sha256']
        for rel,digest in fig['sources'].items():assert sha(package/rel)==digest
    for name in ['F1_series.csv','F6_series.csv','F9_e3_series.csv']:
        assert (package/'manuscript/figures'/name).read_bytes()==(package/'figures'/name).read_bytes()
    pdf=MANUSCRIPT_ROOT/'decision_residual_fields_theory_v45.pdf'
    with pymupdf.open(pdf) as doc:
        pages=len(doc);text='\n'.join(p.get_text() for p in doc)
    assert 31 <= pages <= 34 and '??' not in text and '\ufffd' not in text
    assert not re.search(r'\baudit\b|Revision draft|Gate 0',text,re.I)
    return dict(status='complete',scope=__doc__,checks=checks,pdf_pages=pages,source_sha256=sha(MANUSCRIPT_ROOT/'manuscript/main.tex'),pdf_sha256=sha(pdf),figures_with_verified_source_hashes=len(figures),series_identical_to_corrected_results=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True,help='Unchanged v4 reproduction package with archived results and evidence');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Use a new report path')
    report=verify(a.package.resolve());a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Verified {len(report["checks"])} manuscript quantities/descriptions and 5 figures.')
