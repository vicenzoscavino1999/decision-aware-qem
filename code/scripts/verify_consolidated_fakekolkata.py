"""Independent numerical checks of the completed cached FakeKolkata analysis.

Does not import the production sampling, decision, REM, optimization or summary
functions. Does not simulate quantum circuits. Fractions, explicit Kronecker
matrices, scalar quadratic intersections and integer bootstrap totals provide
alternative calculations.
"""
from pathlib import Path
from fractions import Fraction
import csv
import hashlib
import json
import os
import time
from scripts.compare_release import equivalent,CDF_ATOL
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np

PACKAGE = None
ARCHIVE = None
RESULTS = None
REPORT_DIR = None
NAMES = [f'C{i:03}' for i in range(1,49)]
METHODS = ('Raw','Raw+REM','Accuracy-ZNE','Decision-ZNE')
POLICIES = (*METHODS,'MSE-selector','GRI-selector')
NAMESPACE = 'v20-independent-fakekolkata-20261022'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def seed_rng(name, method, rep, stream):
    payload = f'260616|{name}|{method}|512|{rep}|{NAMESPACE}|{stream}'
    seed = int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], 'big')
    return np.random.Generator(np.random.PCG64DXSM(seed))

def kron_channel(matrices):
    channel = np.ones((1,1))
    for matrix in reversed(matrices):
        channel = np.kron(channel, matrix)
    return channel

def independent_rem(cell, name, rep, candidate):
    rid = 25*rep+candidate
    counts = seed_rng(name,'Raw+REM',rid,'rem_eval_counts').multinomial(
        410, cell['noisy_observed_probs'][0,candidate])
    rng = seed_rng(name,'Raw+REM',rid,'rem_calibration')
    estimated = np.empty((10,2,2))
    for prepared in (0,1):
        for q in range(10):
            p = cell['readout_matrices'][q,:,prepared]
            estimated[q,:,prepared] = rng.multinomial(51,p/p.sum())/51
    estimated = np.maximum(estimated,1e-12)
    estimated /= estimated.sum(axis=1,keepdims=True)
    inverses=[]
    for m in estimated:
        determinant = m[0,0]*m[1,1]-m[0,1]*m[1,0]
        assert abs(determinant)>1e-8
        inverses.append(np.array([[m[1,1],-m[0,1]],[-m[1,0],m[0,0]]])/determinant)
    unprojected = kron_channel(inverses) @ (counts/410)
    lo, hi = float(unprojected.min()-1), float(unprojected.max())
    for _ in range(80):
        mid = (lo+hi)/2
        if np.maximum(unprojected-mid,0).sum()>1:
            lo=mid
        else:
            hi=mid
    projected=np.maximum(unprojected-(lo+hi)/2,0)
    projected/=projected.sum()
    return float(projected @ cell['values_by_state'])

def minimax_by_scalar_intersections(primitive, ideal, optimum, coefficients):
    keep=[j for j in range(25) if j!=optimum]
    g=primitive[:10][:,:,keep]-primitive[:10][:,:,[optimum]]
    centered=g-g.mean(axis=0)
    q=np.einsum('rsj,rtj->jst',centered,centered)/9
    ref=ideal[keep]-ideal[optimum]
    q/=ref[:,None,None]**2
    c0=np.array([2.,-1.,0.]);direction=np.array([1.,-2.,1.])
    a=np.einsum('s,jst,t->j',direction,q,direction)
    b=2*np.einsum('s,jst,t->j',c0,q,direction)
    c=np.einsum('s,jst,t->j',c0,q,c0)
    candidates=[-bb/(2*aa) for aa,bb in zip(a,b) if aa>0]
    for j in range(24):
        for k in range(j):
            polynomial=np.array([a[j]-a[k],b[j]-b[k],c[j]-c[k]])
            for root in np.roots(np.trim_zeros(polynomial,'f')):
                if abs(root.imag)<1e-9:
                    candidates.append(float(root.real))
    def objective(t):
        return float(np.max((a*t+b)*t+c))
    optimum_t=min(candidates,key=objective)
    reference=objective(optimum_t)
    found=objective(float(coefficients[2]))
    excess=(found-reference)/max(1.,abs(reference))
    assert -1e-9 <= excess <= 1e-7, (found,reference,coefficients)
    return float(excess)

def exact_failures(samples,optimum,coefficients):
    raw=np.rint(samples['raw'][20:]*512).astype(np.int64)
    prim=np.rint(samples['primitive'][20:]*170).astype(np.int64)
    assert np.max(abs(samples['raw']*512-np.rint(samples['raw']*512)))<1e-8
    assert np.max(abs(samples['primitive']*170-np.rint(samples['primitive']*170)))<1e-8
    keep=[j for j in range(25) if j!=optimum]
    answer={'Raw':np.any(raw[:,keep]<=raw[:,[optimum]],axis=1).astype(int).tolist(),
            'Raw+REM':np.any(samples['rem'][20:,keep]<=samples['rem'][20:,[optimum]],axis=1).astype(int).tolist()}
    t=Fraction(float(coefficients['Decision-ZNE'][2]))
    weights={'Accuracy-ZNE':(Fraction(4,3),Fraction(1,3),Fraction(-2,3)),
             'Decision-ZNE':(2+t,-1-2*t,t)}
    for method,w in weights.items():
        failures=[]
        for rep in prim:
            values=[sum((Fraction(int(rep[s,j]),170)*w[s] for s in range(3)),Fraction(0)) for j in range(25)]
            failures.append(int(any(values[j]<=values[optimum] for j in keep)))
        answer[method]=failures
    return answer

def main():
    start=time.monotonic()
    rows=[]; totals=[]; samples_checked=0; rem_checked=0; labels_checked=0
    max_readout_error=0.;max_rem_error=0.;max_qp_excess=0.;max_mse_error=0.;cross_platform={'max_abs_difference':0.}
    for name in NAMES:
        record=read(RESULTS/f'{name}_analysis.json'); old=read(ARCHIVE/f'{name}_analysis.json')
        equivalent(record,old,name,cross_platform)
        with np.load(RESULTS/f'{name}_samples.npz',allow_pickle=False) as z:
            samples={k:z[k] for k in z.files}
        with np.load(ARCHIVE/f'{name}_samples.npz',allow_pickle=False) as z:
            for key,array in samples.items():
                np.testing.assert_array_equal(array,z[key]);samples_checked+=array.size
        with np.load(RESULTS/f'{name}_probabilities.npz',allow_pickle=False) as z:
            cell={k:z[k] for k in z.files}
        opt=int(cell['x_star']);ideal=cell['ideal_values'];coeff=record['coefficients']
        failure=exact_failures(samples,opt,coeff)
        for policy,method in record['choices'].items():
            failure[policy]=failure[method]
            criterion='mse' if policy=='MSE-selector' else 'gri'
            assert method==sorted(METHODS,key=lambda m:(record['scores'][m][criterion],m))[0]
        assert failure==record['failures'],name
        labels_checked+=sum(map(len,failure.values()))
        totals.append([sum(failure[p]) for p in POLICIES])
        methods={'Raw':samples['raw'],'Raw+REM':samples['rem']}
        for method in ('Accuracy-ZNE','Decision-ZNE'):
            methods[method]=sum(coeff[method][s]*samples['primitive'][:,s,:] for s in range(3))
            np.testing.assert_allclose([sum(coeff[method]),sum((s+1)*coeff[method][s] for s in range(3))], [1.,0.],atol=1e-14,rtol=0)
        for method,values in methods.items():
            mse=float(np.mean((values[10:20]-ideal)**2))
            delta=abs(mse-record['scores'][method]['mse']);max_mse_error=max(max_mse_error,delta)
            assert delta<1e-12
        excess=minimax_by_scalar_intersections(samples['primitive'],ideal,opt,coeff['Decision-ZNE'])
        max_qp_excess=max(max_qp_excess,excess)
        readout=kron_channel(cell['readout_matrices'])
        predicted=cell['raw_gate_probs'].reshape(-1,1024) @ readout.T
        error=float(np.max(abs(predicted.reshape(3,25,1024)-cell['noisy_observed_probs'])))
        max_readout_error=max(max_readout_error,error);assert error<1e-14
        for rep in (0,9,10,19,20,39):
            for candidate in sorted({0,opt,24}):
                expectation=independent_rem(cell,name,rep,candidate)
                delta=abs(expectation-float(samples['rem'][rep,candidate]))
                max_rem_error=max(max_rem_error,delta);rem_checked+=1
                assert delta<1e-10,(name,rep,candidate,delta)
        for policy in POLICIES:
            method=record['choices'].get(policy,policy)
            fit=25*10*(170+170+170) if policy in ('Decision-ZNE','MSE-selector','GRI-selector') else 0
            selection=25*10*(512+(410+51+51)+(170+170+170)) if policy.endswith('selector') else 0
            evaluation=25*20*(510 if method in ('Accuracy-ZNE','Decision-ZNE') else 512)
            assert record['ledger'][policy]=={'fit':fit,'selection':selection,'evaluation':evaluation,
                'total':fit+selection+evaluation,'amortized_per_decision':(fit+selection+evaluation)/20}
        rows.append({'instance':name,'samples_equal':True,'scientific_record_within_tolerances':True,
                     'failures_checked':120,'readout_max_error':error,'qp_scaled_objective_excess':excess,
                     'GRI_choice':record['choices']['GRI-selector'],'MSE_choice':record['choices']['MSE-selector']})
    summary=read(RESULTS/'summary.json');old_summary=read(ARCHIVE/'summary.json')
    assert summary==old_summary
    assert (RESULTS/'outcomes.csv').read_text()==(ARCHIVE/'outcomes.csv').read_text()
    counts=np.asarray(totals,dtype=np.int64)
    for j,policy in enumerate(POLICIES):
        np.testing.assert_allclose(summary['failure_rates'][policy],counts[:,j].sum()/960,atol=1e-15,rtol=0)
    draws=np.random.default_rng(20261022).integers(0,48,size=(10000,48))
    boot=counts[draws].sum(axis=1)
    m=boot[:,POLICIES.index('MSE-selector')];d=boot[:,POLICIES.index('GRI-selector')];r=boot[:,POLICIES.index('Raw')]
    independent_cis={'relative_reduction_cluster_ci':np.quantile((m-d)/m,[.025,.975]).tolist(),
        'paired_difference_cluster_ci':np.quantile((d-m)/960,[.025,.975]).tolist(),
        'paired_difference_GRI_minus_Raw_cluster_ci':np.quantile((d-r)/960,[.025,.975]).tolist()}
    for key,value in independent_cis.items():
        np.testing.assert_allclose(value,summary[key],atol=2e-15,rtol=0)
    report={'instances':48,'samples_compared_exactly':samples_checked,'failure_labels_checked':labels_checked,
            'analysis_records_within_tolerances_excluding_provenance':48,'selector_choices_equal':96,
            'cross_platform_cdf_atol':CDF_ATOL,'cross_platform_max_numeric_difference':cross_platform['max_abs_difference'],
            'outcomes_csv_text_identical':True,'outcomes_csv_byte_identical':(RESULTS/'outcomes.csv').read_bytes()==(ARCHIVE/'outcomes.csv').read_bytes(),'summary_equal':True,
            'readout_probability_vectors_checked':48*3*25,'readout_max_abs_error':max_readout_error,
            'independent_REM_expectations_checked':rem_checked,'REM_max_abs_error':max_rem_error,
            'independent_scalar_minimax_fits_checked':48,'minimax_max_scaled_objective_excess':max_qp_excess,
            'MSE_max_abs_error':max_mse_error,'ledger_rows_checked':48*6,
            'independent_bootstrap_resamples':10000,'independent_cluster_intervals':independent_cis,
            'new_physical_simulations':0,'elapsed_seconds':time.monotonic()-start,
            'scope':'Full cached-probability reanalysis; no independent regeneration of the physical density matrices.'}
    write(REPORT_DIR/'independent_fakekolkata.json',report)
    with (REPORT_DIR/'fakekolkata_instance_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--report-dir',type=Path,required=True);args=p.parse_args()
    PACKAGE=args.package.resolve();ARCHIVE=PACKAGE/'evidence/fakekolkata/results/fakekolkata_fixed10'
    RESULTS=PACKAGE/'results/fakekolkata_fixed10';REPORT_DIR=args.report_dir
    REPORT_DIR.mkdir(parents=True,exist_ok=True);main()
