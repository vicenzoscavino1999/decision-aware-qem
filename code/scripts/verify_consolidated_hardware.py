"""Independent count, covariance, channel and bootstrap checks of hardware."""
from pathlib import Path
from itertools import product
import csv,hashlib,json,os,sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE),str(CODE/'src')]
import numpy as np
from scipy.integrate import quad
from scipy.special import log_ndtr
from scipy.stats import norm
from qiskit.quantum_info import DensityMatrix,Statevector
from experiments.hardware_sigma import run_main as h
from scripts import analysis_from_hardware as a

def read(path):return json.loads(path.read_text())
def write(path,z):path.write_text(json.dumps(z,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def covariance(x):
    x=np.asarray(x);c=x-x.mean(axis=0);return c.T@c/(len(x)-1)
def main(P, report_dir):
    result=read(P/'results/hardware/hardware.json')
    reference=read(P/'evidence/hardware/inputs/results/hardware_sigma_attempt2/hsmc_result.json')
    old=read(P/'evidence/hardware/inputs/previous_reanalysis.json')
    coeff={'Raw':[1,0,0], 'Accuracy-ZNE':result['config']['accuracy_zne_coefficients'],
           'DA-ZNE':result['executed_coefficients']}
    rawroot=P/'evidence/hardware/inputs/reproducibility/hardware/raw_counts'
    def objective(bits):return -sum(bits[j]!=bits[j+1] for j in range(3))
    outcomes=np.array([objective(format(i,'04b')[::-1]) for i in range(16)],dtype=float)
    epochs=[];shot_total=0;row_count=0;gap_error=0.
    for epoch,job in enumerate(a.ATTEMPT2_EPOCH_JOBS):
        payload=read(rawroot/(job+'.json'));primitives={}
        for meta,counts in zip(payload['tasks'],payload['raw_counts'],strict=True):
            shots=sum(counts.values());assert shots==meta['shots']
            shot_total+=shots;row_count+=1
            value=sum(outcomes[int(bits,2)]*n for bits,n in counts.items())/shots
            key=(meta['method'],meta['replicate'],meta['candidate'])
            scale=int(meta['scale_nominal'])-1
            if key not in primitives:primitives[key]=np.zeros(3)
            primitives[key][scale]=value
        vectors={}
        for method in h.METHODS:
            vectors[method]=[]
            for rep in range(epoch*6,epoch*6+6):
                values=np.array([np.dot(coeff[method],primitives[(method,rep,c)]) for c in range(4)])
                vectors[method].append(values[1:]-values[0])
            gap_error=max(gap_error,float(np.max(np.abs(np.array(vectors[method])-payload['archived_gap_vectors'][method]))))
        epochs.append(vectors)
    hat={m:covariance([v for ep in epochs for v in ep[m]]) for m in h.METHODS}
    hat_error=max(float(np.max(abs(hat[m]-result['sigma_hat'][m]))) for m in h.METHODS)
    assert hat_error<1e-15 and gap_error<1e-14
    assert result['executed_coefficients']==reference['config']['decision_zne_coefficients']
    assert result['ledger']==reference['ledger'] and shot_total==result['ledger']['C_Sigmahat']

    # Independent explicit Pauli-twirl channel propagation, without Aer/noise helpers.
    I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex)
    Y=np.array([[0,-1j],[1j,0]],complex);Z=np.diag([1,-1]).astype(complex)
    paulis=(I,X,Y,Z)
    def embed(local,targets):
        matrices=[I]*4
        for q,op in zip(targets,local,strict=True):matrices[q]=op
        full=np.ones((1,1),complex)
        for op in matrices[::-1]:full=np.kron(full,op)
        return full
    twirls={qs:[embed(ps,qs) for ps in product(paulis,repeat=len(qs))]
            for qs in [(0,),(1,),(2,),(3,),(0,1),(1,2),(2,3)]}
    rates=np.array(result['characterization']['learned_rates'])
    physical_error=0.;ideal_error=0.;variances=[]
    saved=np.load(P/'results/hardware/prediction_probabilities.npz')['probabilities']
    with a.archive_context(P/'evidence/hardware/inputs'):
        landscape=h.microcell_landscape();mu=landscape.ideal_values[1:]-landscape.ideal_values[0]
        for c,base in enumerate(h.build_candidate_circuits()):
            for scale in (1.,2.,3.):
                isa,_=h.isa_for_candidate_scale(base,scale)
                qc=h.compact_isa_circuit(isa).remove_final_measurements(inplace=False)
                ideal=Statevector.from_instruction(qc).probabilities()
                ideal_error=max(ideal_error,abs(float(ideal@outcomes)-landscape.ideal_values[c]))
                rho=DensityMatrix.from_label('0000')
                for inst in qc.data:
                    qs=tuple(qc.find_bit(q).index for q in inst.qubits)
                    rho=rho.evolve(inst.operation,qargs=list(qs))
                    rate=None
                    if inst.operation.name in ('x','sx'):rate=rates[qs[0]]
                    if inst.operation.name=='cz':
                        qs=tuple(sorted(qs));rate=rates[4+((0,1),(1,2),(2,3)).index(qs)]
                    if rate is not None:
                        twirl=sum((op@rho.data@op.conj().T for op in twirls[qs]),np.zeros((16,16),complex))/len(twirls[qs])
                        rho=DensityMatrix(np.exp(-rate)*rho.data+(1-np.exp(-rate))*twirl)
                p=rho.probabilities();p/=p.sum()
                physical_error=max(physical_error,float(np.max(abs(p-saved[len(variances)]))))
                variances.append(float(p@(outcomes**2)-(p@outcomes)**2))
    assert physical_error<1e-13 and ideal_error<1e-13
    pred={};pullback_error=0.
    for method in h.METHODS:
        weights=np.asarray(coeff[method]);shots=4096 if method=='Raw' else 1365
        v=np.array(variances).reshape(4,3)@(weights**2)/shots
        sigma=np.diag(v[1:])+v[0]*np.ones((3,3));pred[method]=sigma
        pullback_error=max(pullback_error,float(np.max(abs(sigma-result['sigma_pred'][method]))))
    assert pullback_error<1e-15

    # Orthant probabilities from a deterministic one-dimensional reference integral.
    risks={}
    for method,sigma in pred.items():
        vr=sigma[0,1];sd=np.sqrt(np.diag(sigma)-vr)
        def integrand(z):return norm.pdf(z)*(-np.expm1(log_ndtr((mu-np.sqrt(vr)*z)/sd).sum()))
        risk,err=quad(integrand,-np.inf,np.inf,epsabs=1e-14,epsrel=1e-12,limit=300)
        discrepancy=abs(risk-result['corrected_endpoint']['risks'][method])
        # Production CDF requests absolute tolerance 1e-7. The independent check
        # enforces 1e-9 and also verifies every pair threshold below.
        assert discrepancy<1e-9
        risks[method]={'quadrature':risk,'reported':result['corrected_endpoint']['risks'][method],
                       'absolute_difference':discrepancy,'quadrature_error':err}

    # Rebuild all epoch-cluster covariance draws with a separate covariance routine.
    payload='260616|HSMC001|hardware_sigma|4096|0|hardware_sigma_epoch_bootstrap'
    seed=int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8],'big')
    rng=np.random.Generator(np.random.PCG64DXSM(seed))
    selected=rng.integers(0,10,size=(10000,10))
    boot={}
    for method in h.METHODS:
        x=np.array([ep[method] for ep in epochs])[selected].reshape(10000,60,3)
        centered=x-x.mean(axis=1,keepdims=True)
        boot[method]=np.einsum('nri,nrj->nij',centered,centered)/59
    grad={m:h.gri_sigma_gradient(mu,np.array(result['sigma_pred'][m])) for m in h.METHODS}
    projected_checks=[]
    for pair in result['corrected_endpoint']['pairs']:
        m,n=pair['pair']
        prediction_m=np.array(result['sigma_pred'][m]);prediction_n=np.array(result['sigma_pred'][n])
        delta=abs(np.trace(grad[m]@(prediction_m-hat[m]))-np.trace(grad[n]@(prediction_n-hat[n])))
        z=np.abs(np.einsum('ij,nji->n',grad[m],prediction_m-boot[m])-np.einsum('ij,nji->n',grad[n],prediction_n-boot[n]))
        ucb=float(np.quantile(z,.95))
        assert abs(delta-pair['delta_rank'])<1e-14 and abs(ucb-pair['ucb95'])<1e-14
        assert not pair['passed'] and ucb>pair['threshold']
        independent_threshold=.25*abs(risks[m]['quadrature']-risks[n]['quadrature'])
        assert ucb>independent_threshold
        projected_checks.append({'pair':pair['pair'],'independent_projected_error':delta,'independent_ucb95':ucb})

    accounting=[]
    for path in sorted(rawroot.glob('*.json')):
        z=read(path);raw=z.get('raw_counts')
        if isinstance(raw,list):
            accounting.append({'job':z['job_id'],'shots':sum(sum(c.values()) for c in raw),'source':'raw_counts'})
        else:
            # Feasibility only retained summaries, not per-bitstring counts.
            feasibility=read(P/'evidence/hardware/inputs/experiments/hardware_sigma/feasibility_result.json')
            summaries=feasibility['feasibility']['counts_summary']
            accounting.append({'job':z['job_id'],'shots':sum(s['shots'] for s in summaries),'source':'summary_only'})
    write(report_dir/'hardware_shot_accounting.json',{'jobs':accounting,'archived_campaign_total_shots':sum(r['shots'] for r in accounting),
        'attempt2_main_shots':result['ledger']['C_total'],'scope':'Includes failed characterization and feasibility summaries; no missing raw feasibility counts reconstructed'})
    changes=[]
    for m in h.METHODS:
        before=old['secondary']['methods'][m]['relative_frobenius_error'];after=result['secondary']['methods'][m]['relative_frobenius_error']
        changes.append({'metric':'relative_frobenius_error','method_or_pair':m,'before':before,'after':after,'difference':after-before})
    for pair in result['corrected_endpoint']['pairs']:
        previous=next(p for p in old['corrected_endpoint']['pairs'] if set(p['pair'])==set(pair['pair']))
        for metric in ('delta_rank','ucb95','threshold'):
            changes.append({'metric':metric,'method_or_pair':' / '.join(pair['pair']),
                            'before':previous[metric],'after':pair[metric],'difference':pair[metric]-previous[metric]})
    with (report_dir/'hardware_numerical_changes.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(changes[0]));writer.writeheader();writer.writerows(changes)
    report={'counts_records_checked':row_count,'gap_vectors_checked':180,'gap_max_abs_error':gap_error,
        'measured_covariance_max_abs_error':hat_error,'executed_coefficients_preserved':True,
        'independent_Pauli_twirl_probability_vectors':12,'probability_max_abs_error':physical_error,
        'ideal_folded_objective_max_abs_error':ideal_error,'covariance_pullback_max_abs_error':pullback_error,
        'deterministic_risk_integrals':risks,'independent_bootstrap_draws':10000,'projected_checks':projected_checks,
        'gradient_scope':'Analytic production gradients already regression-tested; independent contraction/bootstrap and risk integral here',
        'main_shots':shot_total+203*4096,'label_unchanged':result['label']==old['label'],
        'feasibility_raw_counts_available':False,'new_hardware_jobs':0}
    write(report_dir/'independent_hardware.json',report)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--report-dir',type=Path,required=True);args=p.parse_args();args.report_dir.mkdir(parents=True,exist_ok=True);main(args.package.resolve(),args.report_dir)
