"""Check the compact v45 E1 note against the sealed repartitioning study."""
from pathlib import Path
import hashlib
import io
import json
import zipfile
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parents[1]
tex=(P/'manuscript/main.tex').read_text(encoding='utf-8')
checks={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def present(name,phrase):
    assert phrase in tex,(name,phrase)
    checks[name]=phrase

archive=P/'evidence/e1_particiones_v1.zip'
assert sha(archive)=='79bc7cd31f67d012c8702ac618b318b97ae652ed8609c6fdaaae16230d37021b'
with zipfile.ZipFile(archive) as z:
    base='e1_particiones_v1/'
    def read(name):return json.loads(z.read(base+name))
    manifest=read('manifest_sha256.json')
    for name,h in manifest.items():assert hashlib.sha256(z.read(base+name)).hexdigest()==h,name
    result=read('results.json');cfg=read('protocol.json');splits=read('splits.json')
    verification=read('verification.json');assert verification['status']=='PASS'
    assert verification['alternative_decisions']==384000
    assert read('close_score_verification.json')['status']=='PASS'
    assert len(splits)==48 and cfg['alternative_splits']==20 and cfg['budgets']==[512,1024]
    for instance,items in splits.items():
        tallies={k:np.zeros(40,dtype=int) for k in ['fit','select','test']}
        for split,parts in items.items():
            if split=='S000':continue
            assert [len(parts[k]) for k in tallies]==[10,10,20]
            assert sorted(sum((parts[k] for k in tallies),[]))==list(range(40))
            for k in tallies:tallies[k][parts[k]]+=1
        for k,n in [('fit',5),('select',5),('test',10)]:assert np.all(tallies[k]==n)
    present('partition_design','20 balanced $10/10/20$ partitions of the same 48 instances')
    present('balanced_counts','five times in fitting, five in selection and ten in testing')
    present('retrospective','after the original E1 outcomes were known')
    present('original_kept','The original split remains the primary analysis and is excluded from the alternative-partition average.')
    present('unchanged_costs','original methods, ideal references, shot blocks and costs')
    present('dependent_ranges','ranges across dependent partitions, not confidence intervals')
    for t in [512,1024]:
        for ref,sign in [('Raw',1),('MSE-selector',-1)]:
            d=next(v for v in result['split_sensitivity'] if v['base_t']==t and v['comparison']=='end_to_end' and v['reference']==ref)
            assert d['positive' if sign==1 else 'negative']==20 and d['original_primary_direction_stable']
            if t==512:
                phrase=f'${100*d["minimum"]:.2f}$ to ${100*d["maximum"]:.2f}$'
                present('full_cost_range_'+ref,phrase)
    present('directions_both_budgets','preserves both full-cost directions in every partition at both budgets')
    avg=pd.read_csv(io.BytesIO(z.read(base+'average_summary.csv')))
    rows=pd.read_csv(io.BytesIO(z.read(base+'instance_average_rates.csv')))
    for ref in ['Raw','MSE-selector']:
        a=avg[(avg.base_t==512)&(avg.comparison=='end_to_end')&(avg.kind=='paired_difference')&(avg.reference==ref)].iloc[0]
        present('averaged_difference_'+ref,f'${a.estimate:.4f}$')
        present('averaged_interval_'+ref,f'$[{a.ci_low:.4f},{a.ci_high:.4f}]$')
        m=rows[(rows.base_t==512)&(rows.comparison=='end_to_end')].pivot(index='instance',columns='policy',values='failure')
        assert np.isclose((m['GRI-selector']-m[ref]).mean(),a.estimate,atol=1e-14)
    a=avg[(avg.base_t==512)&(avg.comparison=='evaluation')&(avg.kind=='paired_difference')&(avg.reference=='Raw')].iloc[0]
    present('evaluation_difference',f'${a.estimate:.4f}$')
    present('evaluation_interval',f'$[{a.ci_low:.4f},{a.ci_high:.4f}]$')
    for t in [512,1024]:
        a=avg[(avg.base_t==t)&(avg.comparison=='evaluation')&(avg.kind=='paired_difference')&(avg.reference=='Raw')].iloc[0]
        assert a.ci_low<0<a.ci_high
    assert cfg['bootstrap_replicates']==10000
    present('cluster_method','rates are first averaged over partitions within each instance, followed by 10,000 paired bootstrap resamples of the 48 complete instance clusters')
    present('inference_scope','without adding independent observations or testing transfer to new landscapes')

report=dict(status='PASS',claim_checks=checks,archived_files_verified=len(manifest),
    balanced_split_assignments_rechecked=True,both_primary_directions_hold_in_all_20_partitions_at_both_budgets=True,
    averages_checked_against_instance_records=True,new_experiments_run=False,
    source_sha256=sha(P/'manuscript/main.tex'),pdf_sha256=sha(P/'decision_residual_fields_theory_v45.pdf'))
out=P/'validation/e1_sensitivity_consistency.json';assert not out.exists()
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'PASS: {len(checks)} new claims, {len(manifest)} sealed evidence files, balanced partitions and averaged contrasts.')
