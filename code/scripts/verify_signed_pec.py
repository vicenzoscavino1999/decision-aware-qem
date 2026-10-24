"""Verify v45 PEC claims against sealed evidence; no experiments or paper edits."""
from pathlib import Path
import argparse
_parser=argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--output',type=Path,required=True)
_args=_parser.parse_args()
import csv
import hashlib
import io
import json
import zipfile
import numpy as np

P = Path(__file__).resolve().parents[2]
tex = (P/'manuscript/main.tex').read_text(encoding='utf-8')
checks = {}

def present(name, phrase):
    assert phrase in tex, (name, phrase)
    checks[name] = phrase

def digest(data):
    return hashlib.sha256(data).hexdigest()

provenance = json.loads((P/'provenance/editorial_changes.json').read_text(encoding='utf-8'))
for name, expected in provenance['evidence_archives_sha256'].items():
    assert digest((P/'evidence'/name).read_bytes()) == expected

with zipfile.ZipFile(P/'evidence/pec_decisiones_v2.zip') as z:
    base='pec_decisiones_v2/'
    def read(name): return json.loads(z.read(base+name))
    manifest=read('manifest_sha256.json')
    for name, expected in manifest.items():
        assert digest(z.read(base+name)) == expected, name
    result=read('results.json'); cfg=read('protocol.json'); prior=read('verification_post.json')
    assert prior['status']=='PASS' and prior['checks']['decisions_replayed']==49152
    rows=list(csv.DictReader(io.StringIO(z.read(base+'cell_results.csv').decode('utf-8'))))
    assert len(rows)==96
    for budget in cfg['budgets_per_candidate']:
        values=[]
        for method,key in [('Raw','Raw'),('Signed-PEC','PEC')]:
            selected=[r for r in rows if r['method']==method and int(r['budget'])==budget]
            assert len(selected)==16
            for metric in ['mse_expected','mse_empirical','failure_empirical','failure_discrete','risk_gaussian']:
                assert np.isclose(np.mean([float(r[metric]) for r in selected]),result['aggregate'][str(budget)][key][metric],atol=1e-14,rtol=0)
            assert all(int(r['total_shots_per_decision'])==9*budget for r in selected)
        a=result['aggregate'][str(budget)]
        phrase=f'{budget} & {a["Raw"]["mse_expected"]:.6f} & {a["PEC"]["mse_expected"]:.6f} & {100*a["Raw"]["failure_empirical"]:.2f} & {100*a["PEC"]["failure_empirical"]:.2f}'
        present(f'table_{budget}',phrase)
    a=result['aggregate'][str(cfg['primary_budget'])]
    present('primary_budget',f'primary budget $B={cfg["primary_budget"]}$')
    present('empirical_mse',f'empirical MSE falls from ${a["Raw"]["mse_empirical"]:.5f}$ to ${a["PEC"]["mse_empirical"]:.5f}$')
    reduction=100*(1-a['PEC']['mse_empirical']/a['Raw']['mse_empirical'])
    present('mse_reduction',f'a ${reduction:.0f}\\%$ reduction')
    diff=a['differences_pec_minus_raw']['failure_empirical']
    present('failure_difference',f'${100*diff:.2f}$ percentage points')
    lo,hi=a['differences_90ci']['failure_empirical']
    present('failure_interval',f'$[{100*lo:.2f},{100*hi:.2f}]$')
    lo,hi=a['differences_90ci']['mse_empirical']
    present('mse_interval',f'$[{lo:.5f},{hi:.5f}]$')
    diff=a['differences_pec_minus_raw']['mse_empirical']
    present('mse_difference',f'${diff:.5f}$')
    lo,hi=result['aggregate']['768']['differences_90ci']['mse_empirical']
    assert lo<0<hi
    present('sensitivity_uncertainty','At $B=768$, the MSE-difference interval includes zero')
    for key,label in [('Raw','Raw'),('Signed-PEC','PEC')]:
        error=result['gaussian_adequacy'][key]['max_abs_error']
        assert error*100<0.35
        present('gaussian_error_'+label,f'${error:.5f}$ for {label}')
    assert cfg['landscapes']==8 and cfg['qubits']==6 and cfg['depth']==2 and cfg['candidates']==9
    assert cfg['repetitions']==512 and cfg['primary_budget']==3072
    assert cfg['bootstrap']['replicates']==10000 and cfg['bootstrap']['confidence']==.90
    present('repetitions','512 independent repetitions')
    present('bootstrap','10,000 paired bootstrap resamples of the eight landscapes')
    assert cfg['landscapes']*len(cfg['noise'])*cfg['repetitions']==8192
    present('sample_count','8,192 decisions per method and budget')
    # Check the new law and variance equations directly against the archived distributions.
    error_mean=error_variance=error_joint=0.
    gamma_squared=set()
    for name in manifest:
        if not name.startswith('laws/') or not name.endswith('.npz'): continue
        with np.load(io.BytesIO(z.read(base+name))) as law:
            gamma=float(law['gamma']); m=law['ideal_cut'].shape[1]-1
            gamma_squared.add(round(gamma**2,4))
            h=m/2-law['cuts']
            joint=law['joint_state']
            expected=np.stack([(law['absolute_state']+law['ideal_state']/gamma)/2,
                               (law['absolute_state']-law['ideal_state']/gamma)/2],axis=1)
            error_joint=max(error_joint,float(np.max(np.abs(joint-expected))))
            values=-m/2+gamma*np.stack([h,-h])
            mean=np.sum(joint*values[None,:,:],axis=(1,2))
            truth=law['ideal_state']@(-law['cuts'])
            var=np.sum(joint*(values[None,:,:]-mean[:,None,None])**2,axis=(1,2))
            formula=gamma**2*(law['absolute_state']@(h*h))-(law['ideal_state']@h)**2
            error_mean=max(error_mean,float(np.max(np.abs(mean-truth))))
            error_variance=max(error_variance,float(np.max(np.abs(var-formula))))
    assert max(error_mean,error_variance,error_joint)<1e-10
    assert gamma_squared=={3.6105,13.0750}
    present('overheads',r'$\Gamma^2=3.6105$ and $13.0750$')
    present('signed_law',r'\Prob(s,z)=\tfrac12\bigl(P_{\rm abs}(z)+sP_{\rm ideal}(z)/\Gamma\bigr)')
    present('actual_variance',r'\Gamma^2\E_{\rm abs}[h^2]-(\E_{\rm ideal}h)^2')
    present('known_channel','The channel is stipulated known.')
    present('marginal_simulation','The simulation samples this exact marginal over circuit branches.')
    present('centering','The known constant is added exactly')
    present('ties','ties count as failures')
    present('scope','rather than learned from finite calibration data')

report=dict(status='PASS',claim_checks=checks,archived_files_verified=len(manifest),
    aggregate_rows_verified=len(rows),signed_law_max_error=error_joint,
    signed_mean_max_error=error_mean,signed_variance_max_error=error_variance,
    previous_evidence_replay=prior['checks'],new_experiments_run=False,
    source_sha256=digest((P/'manuscript/main.tex').read_bytes()),
    pdf_sha256=digest((P/'decision_residual_fields_theory_v45.pdf').read_bytes()))
out=_args.output
if out.exists(): raise FileExistsError(out)
out.parent.mkdir(parents=True,exist_ok=True)
if out.exists(): raise FileExistsError(out)
out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'PASS: {len(checks)} claims, {len(manifest)} archived files, {len(rows)} result rows; signed moments agree.')
