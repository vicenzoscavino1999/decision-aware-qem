"""Fresh split-sample FakeKolkata correction. Local simulation only, resumable."""
from pathlib import Path
from contextlib import contextmanager
import sys,os,json,argparse,hashlib,time,inspect,importlib.metadata,shutil
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
if __name__ == '__main__':
    os.environ.setdefault('OMP_NUM_THREADS','4')
import numpy as np
import pandas as pd
from experiments.derisk_fakebackend import run as old
from experiments.derisk_fakebackend import rem as rem_module
from revision_v19.e1_reanalysis import fit_coefficients,risk_score,gaps
from daqem.rng import make_rng
from daqem.decisions import zne_failures
from daqem.cache import sha256,fingerprint,atomic_json,atomic_npz,load_json,valid_probability,valid_analysis
from qiskit_ibm_runtime.fake_provider import FakeKolkataV2
from qiskit_aer.noise import NoiseModel
from qiskit.transpiler import Target
from types import SimpleNamespace
METHODS=('Raw','Raw+REM','Accuracy-ZNE','Decision-ZNE')
NAMESPACE='v20-independent-fakekolkata-20261022'
def fresh_rng(**kwargs):
    kwargs['stream']=NAMESPACE+'|'+kwargs.get('stream','')
    return make_rng(**kwargs)

@contextmanager
def _sampling_context():
    """Apply this experiment's streams only during its sequential sampling call."""
    previous_rng = old.make_rng
    previous_calibration_rng = rem_module.make_rng
    try:
        old.make_rng = fresh_rng
        rem_module.make_rng = fresh_rng
        yield
    finally:
        old.make_rng = previous_rng
        rem_module.make_rng = previous_calibration_rng


@contextmanager
def _simulation_context():
    """Keep this runner's Aer thread limit local to its simulation call."""
    previous_threads = old.AER_MAX_PARALLEL_THREADS
    try:
        old.AER_MAX_PARALLEL_THREADS = 4
        yield
    finally:
        old.AER_MAX_PARALLEL_THREADS = previous_threads


def _validate_protocol():
    """Reject missing or incompatible metadata before any expensive work or writes."""
    protocol_path = ROOT.parent / 'protocol.json'
    if not protocol_path.is_file():
        raise FileNotFoundError(f'Required protocol file is missing: {protocol_path}')
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    if not isinstance(protocol, dict) or not isinstance(protocol.get('fakekolkata'), dict):
        raise ValueError('protocol.json must contain a fakekolkata configuration object')
    expected = {'budget': 512, 'fit_reps': 10, 'selection_reps': 10,
                'test_reps': 20, 'menu': list(METHODS), 'seed_namespace': NAMESPACE}
    actual = protocol['fakekolkata']
    different = [key for key, value in expected.items() if actual.get(key) != value]
    if different:
        raise ValueError(f'protocol.json disagrees with this fixed experiment: {different}')
    return protocol

def bounded_backend(backend,noise):
    # This is an explicitly NEW robustness design, not the historical mapping.
    physical=[16,22,25,19,20,24,23,14,26,13]
    mapping={q:i for i,q in enumerate(physical)}
    target=Target(num_qubits=10)
    for name in backend.target.operation_names:
        instruction=backend.target.operation_from_name(name)
        properties={tuple(mapping[q] for q in qubits):value
            for qubits,value in backend.target[name].items()
            if qubits is not None and all(q in mapping for q in qubits)}
        if properties:target.add_instruction(instruction,properties,name=name)
    reduced=old._scaled_reduced_noise_model(noise,mapping,scale=1.)
    for q,i in mapping.items():
        reduced.add_readout_error(noise._local_readout_errors[(q,)], [i])
    return SimpleNamespace(target=target),reduced,physical

def analyze(cell):
    with _sampling_context():
        raw,primitive,rem=old._primitive_samples(cell,(512,))
    raw=raw[:,:,0];primitive=primitive[:,:,:,0];rem=rem[:,:,0]
    coeff,status=fit_coefficients(primitive[:10],cell.ideal_values,cell.x_star)
    values={'Raw':raw,'Raw+REM':rem,**{m:np.einsum('s,rsc->rc',c,primitive) for m,c in coeff.items()}}
    scores={m:{'mse':float(np.mean((v[10:20]-cell.ideal_values)**2)),
               'gri':risk_score(v[10:20],cell.x_star,20261022)} for m,v in values.items()}
    choices={'MSE-selector':min(METHODS,key=lambda m:(scores[m]['mse'],m)),
             'GRI-selector':min(METHODS,key=lambda m:(scores[m]['gri'],m))}
    outcomes={m:np.any(gaps(v[20:],cell.x_star)<=0,axis=1).astype(int) for m,v in values.items()}
    outcomes['Accuracy-ZNE']=zne_failures(primitive[20:],cell.x_star,512//3).astype(int)
    outcomes['Decision-ZNE']=zne_failures(primitive[20:],cell.x_star,512//3,coefficients=coeff['Decision-ZNE']).astype(int)
    for policy,method in choices.items():outcomes[policy]=outcomes[method]
    # Menu acquisition reuses the same 3-scale ZNE record for both ZNE arms.
    ledger={}
    for policy in outcomes:
        method=choices.get(policy,policy)
        fit=10*3*(512//3)*25 if policy.endswith('selector') or policy=='Decision-ZNE' else 0
        selection=10*(512+512+3*(512//3))*25 if policy.endswith('selector') else 0
        evaluation=20*(3*(512//3) if 'ZNE' in method else 512)*25
        ledger[policy]={'fit':fit,'selection':selection,'evaluation':evaluation,
                        'total':fit+selection+evaluation,'amortized_per_decision':(fit+selection+evaluation)/20}
    return {'instance':cell.instance_id,'scores':scores,'choices':choices,'solver_status':status,
        'coefficients':{k:v.tolist() for k,v in coeff.items()},'ledger':ledger,
        'failures':{k:v.tolist() for k,v in outcomes.items()}},(raw,primitive,rem)

def probability_identity(name,backend,noise,physical):
    sources=['experiments/derisk_fakebackend/run.py','experiments/derisk_fakebackend/rem.py',
             'src/daqem/candidates.py','src/daqem/qaoa.py','src/daqem/rng.py']
    # Target display order and Aer-generated UUIDs vary across processes. Hash
    # the complete numeric calibration in a canonical order, not those labels.
    operations=[]
    for operation_name in sorted(backend.target.operation_names):
        operation=backend.target.operation_from_name(operation_name)
        properties=[{'qubits':list(q) if q is not None else None,
                     'duration':v.duration if v is not None else None,
                     'error':v.error if v is not None else None}
                    for q,v in backend.target[operation_name].items()]
        properties.sort(key=lambda x:json.dumps(x['qubits']))
        operations.append({'name':operation_name,'qubits':operation.num_qubits,
            'clbits':operation.num_clbits,'params':list(map(str,operation.params)),
            'properties':properties})
    errors=[{k:v for k,v in error.items() if k!='id'}
            for error in noise.to_dict(serializable=True)['errors']]
    errors.sort(key=lambda x:json.dumps(x,sort_keys=True,separators=(',',':')))
    return {'schema':2,'instance':name,'physical_block':physical,
        'source_hashes':{p:sha256(ROOT/p) for p in sources},
        'bounded_backend_source':hashlib.sha256(inspect.getsource(bounded_backend).encode()).hexdigest(),
        'identity_source':hashlib.sha256(inspect.getsource(probability_identity).encode()).hexdigest(),
        'backend_target':fingerprint({'num_qubits':backend.target.num_qubits,'operations':operations}),
        'noise_model':fingerprint({'errors':errors}),
        'versions':{p:importlib.metadata.version(p) for p in ['numpy','scipy','networkx','qiskit','qiskit-aer','qiskit-ibm-runtime']},
        'scales':list(map(float,old.ZNE_LAMBDAS)),'candidates':old.CANDIDATE_COUNT,
        'depth':old.DEPTH,'transpiler_seed':old.SEED_TRANSPILE}


def analysis_identity(name,probability_hash):
    sources=['run_fakekolkata_v21.py','revision_v19/e1_reanalysis.py','src/daqem/decisions.py',
             'src/daqem/risk.py','src/daqem/qem_methods.py','src/daqem/cache.py',
             'experiments/derisk_fakebackend/run.py','experiments/derisk_fakebackend/rem.py','src/daqem/rng.py','src/daqem/budget.py']
    return {'schema':1,'instance':name,'probability_sha256':probability_hash,'namespace':NAMESPACE,
        'source_hashes':{p:sha256(ROOT/p) for p in sources},'protocol_sha256':sha256(ROOT.parent/'protocol.json'),
        'versions':{p:importlib.metadata.version(p) for p in ['numpy','scipy','cvxpy','clarabel','scikit-learn']},
        'budget':512,'fit':10,'select':10,'test':20,'menu':list(METHODS)}


def load_cell(cache,name):
    with np.load(cache,allow_pickle=False) as f:
        cell=old.CellData(instance_id=name,graph_edges=tuple(map(tuple,f['graph_edges'])),
            x_star=int(f['x_star']),ideal_values=f['ideal_values'],values_by_state=f['values_by_state'],
            noisy_observed_probs=f['noisy_observed_probs'],raw_gate_probs=f['raw_gate_probs'],
            readout_matrices=f['readout_matrices'],mappings=json.loads(str(f['mappings'])))
    for p in [cell.noisy_observed_probs,cell.raw_gate_probs]:
        if p.shape!=(3,25,1024) or not np.isfinite(p).all() or p.min()<0 or not np.allclose(p.sum(-1),1.,atol=1e-12,rtol=0):
            raise ValueError(f'Invalid probability array for {name}')
    return cell


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT.parent/'results/fakekolkata')
    parser.add_argument('--instances',nargs='+',default=[f'C{i:03}' for i in range(1,49)])
    parser.add_argument('--bounded-10-qubits',action='store_true',help='New fixed-physical-block design; changes historical routing')
    parser.add_argument('--regenerate-probabilities',action='store_true',help='Recompute probabilities, samples and analysis even when checkpoints exist')
    parser.add_argument('--probability-inputs',type=Path,help='Optional source of validated probability caches and sidecars')
    args=parser.parse_args()
    allowed={f'C{i:03}' for i in range(1,49)}
    if len(args.instances)!=len(set(args.instances)) or not set(args.instances)<=allowed:
        parser.error('Use unique instance IDs C001 through C048')
    _validate_protocol()
    args.output.mkdir(parents=True,exist_ok=True)
    backend=FakeKolkataV2();noise=NoiseModel.from_backend(backend)
    physical=None
    if args.bounded_10_qubits:backend,noise,physical=bounded_backend(backend,noise)
    started=time.time()
    records=[]
    for name in args.instances:
        checkpoint=args.output/f'{name}_analysis.json';cache=args.output/f'{name}_probabilities.npz'
        samples=args.output/f'{name}_samples.npz'
        p_identity=probability_identity(name,backend,noise,physical)
        valid=not args.regenerate_probabilities and valid_probability(cache,p_identity)
        if not valid and not args.regenerate_probabilities and args.probability_inputs:
            supplied=args.probability_inputs/cache.name
            if valid_probability(supplied,p_identity):
                if supplied.resolve()!=cache.resolve():
                    shutil.copy2(supplied,cache);shutil.copy2(supplied.with_suffix('.json'),cache.with_suffix('.json'))
                valid=True
        if not valid:
            with _simulation_context():
                cell=old._probability_array_for_cell(name,backend,noise)
            if physical is not None:cell.mappings['device_physical_qubits']=physical
            atomic_npz(cache,graph_edges=cell.graph_edges,x_star=cell.x_star,
                ideal_values=cell.ideal_values,values_by_state=cell.values_by_state,
                noisy_observed_probs=cell.noisy_observed_probs,raw_gate_probs=cell.raw_gate_probs,
                readout_matrices=cell.readout_matrices,mappings=json.dumps(cell.mappings))
            atomic_json(cache.with_suffix('.json'),{'identity':p_identity,'sha256':sha256(cache),'origin':'density_matrix_simulation'})
        identity=analysis_identity(name,sha256(cache))
        identity['probability_model_fingerprint']=fingerprint(p_identity)
        record=load_json(checkpoint)
        if not args.regenerate_probabilities and valid_analysis(record,identity,samples):
            records.append(record);print(f'{name}: verified checkpoint reused',flush=True);continue
        cell=load_cell(cache,name)
        record,arrays=analyze(cell)
        atomic_npz(samples,raw=arrays[0],primitive=arrays[1],rem=arrays[2])
        record.update(cache_identity=identity,samples_sha256=sha256(samples))
        atomic_json(checkpoint,record);records.append(record)
        print(f'{name}: independent evaluation completed; elapsed={time.time()-started:.1f}s',flush=True)
    rows=[{'instance':r['instance'],'policy':p,'replicate':i+20,'failure':v}
          for r in records for p,a in r['failures'].items() for i,v in enumerate(a)]
    df=pd.DataFrame(rows);df.to_csv(args.output/'outcomes.csv',index=False)
    rates=df.groupby(['instance','policy']).failure.mean().unstack('policy')
    draws=np.random.default_rng(20261022).integers(0,len(rates),(10000,len(rates)))
    m=rates['MSE-selector'].to_numpy();d=rates['GRI-selector'].to_numpy()
    boot_m=m[draws].mean(1);boot_d=d[draws].mean(1)
    raw_rate=rates['Raw'].to_numpy();raw_difference=d-raw_rate
    relative_boot=np.divide(boot_m-boot_d,boot_m,out=np.full_like(boot_m,np.nan),where=boot_m!=0)
    relative_ci=np.quantile(relative_boot,[.025,.975]).tolist() if np.isfinite(relative_boot).all() else None
    summary={'instances':len(records),'instance_ids':[r['instance'] for r in records],'test_decisions':20*len(records),'scope':'retrospective landscapes, independent fit/select/test sampling, four-arm menu',
        'routing_design':'fixed 10-qubit calibrated block; new experiment' if physical is not None else 'historical unrestricted routing',
        'physical_block':physical,
        'failure_rates':rates.mean().to_dict(),'relative_reduction':float((m.mean()-d.mean())/m.mean()) if m.mean()!=0 else None,
        'relative_reduction_cluster_ci':relative_ci,'bootstrap_zero_reference_replicates':int((boot_m==0).sum()),
        'paired_difference':float((d-m).mean()),'paired_difference_cluster_ci':np.quantile(boot_d-boot_m,[.025,.975]).tolist(),
        'paired_difference_GRI_minus_Raw':float(raw_difference.mean()),
        'paired_difference_GRI_minus_Raw_cluster_ci':np.quantile(raw_difference[draws].mean(1),[.025,.975]).tolist(),
        'namespace':NAMESPACE,'target_ideal_labels':'oracle inputs; ideal computation cost not included',
        'not_equal_end_to_end_cost':'compare fixed arms using ledger; selector evaluation budgets only are matched'}
    atomic_json(args.output/'summary.json',summary);print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
