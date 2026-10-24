"""Regression cases for hardware characterization, counts and resumption."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from qiskit.quantum_info import DensityMatrix
from experiments.hardware_sigma import run_main as h
from scripts import analysis_from_hardware as a

@pytest.fixture(autouse=True)
def archived_feasibility_record(monkeypatch):
    # The integrated layout stores experimental inputs separately from code.
    source=Path(__file__).resolve().parents[2]/'evidence/hardware/inputs/experiments/hardware_sigma/feasibility_result.json'
    assert source.is_file()
    monkeypatch.setattr(h,'FEASIBILITY_RECORD',source)

def design():
    x=np.zeros((203,14))
    lengths=(1,2,3,4,6,8,12)
    for i in range(203):
        g=i//29;x[i,g]=1;x[i,g+7]=2*lengths[(i%29)%7]
    return x

def test_gate_predicts_heldout_without_training_on_it():
    x=design();y=x@np.r_[np.full(7,.02),np.full(7,.004)]
    train,test=h.split_characterization(x)
    y[test]+=.2
    fitted_on_all=h.learn_sparse_pl_model(x,y)
    expected_model=h.learn_sparse_pl_model(x[train],y[train])
    expected=np.linalg.norm(x[test]@expected_model['params']-y[test])/np.linalg.norm(y[test])
    got=h.gate_c1_metrics(x,y,fitted_on_all)
    assert got['heldout_relative_generalization_error']==pytest.approx(expected,abs=1e-14)
    assert not set(got['fit_indices'])&set(got['heldout_indices'])
    assert not got['passed']

def test_constrained_negative_slope_refits_intercept():
    x=design();y=x@np.r_[np.full(7,.3),np.full(7,-.005)]
    fit=h.learn_sparse_pl_model(x,y)
    assert np.max(fit['rates'])<1e-9
    for g in range(7):
        assert fit['intercepts'][g]==pytest.approx(y[x[:,g]==1].mean(),abs=1e-9)
    clipped=np.r_[np.full(7,.3),np.zeros(7)]
    assert np.linalg.norm(x@fit['params']-y)<np.linalg.norm(x@clipped-y)

@pytest.mark.parametrize('qubits',[1,2])
def test_log_rate_channel_has_exponential_eigenvalue(qubits):
    r=.6;rates=np.zeros(7);rates[0 if qubits==1 else 4]=r
    model=h.sparse_pl_noise_model_from_rates(rates)
    error=model._local_quantum_errors['x' if qubits==1 else 'cz'][(0,) if qubits==1 else (0,1)]
    rho=DensityMatrix.from_label('0'*qubits).evolve(error.to_quantumchannel()).data
    d=2**qubits
    signal=(d*float(rho[0,0].real)-1)/(d-1)
    assert signal==pytest.approx(np.exp(-r),abs=1e-14)

@pytest.mark.parametrize('counts',[{'0000':-1,'0001':11},{'0000':1.5},{'0000':True},{'0020':10},{'000':10},{'0000':0}])
def test_invalid_counts_rejected(counts):
    with pytest.raises(ValueError):h.validate_counts(counts)

def test_wrong_shot_total_rejected():
    with pytest.raises(ValueError,match='shot total'):
        h.validate_counts({'0000':4095},expected_shots=4096)

def test_checkpoint_recomputes_gaps_and_rejects_changed_tasks_or_counts(tmp_path):
    tasks=h.build_epoch_tasks(0,1);counts=h.DeterministicProbabilitySampler().run(tasks,epoch=0)
    maps=h.method_maps(h.effective_scale_tuple());L=h.contrast_matrix(4,ref=0)
    vectors=h.gap_vectors_for_epoch(tasks,counts,maps,L)
    path=tmp_path/'epoch.json'
    h.save_epoch_checkpoint(path,vectors,epoch=0,tasks=tasks,counts_list=counts)
    payload=json.loads(path.read_text());payload['gap_vectors']={m:[[99,99,99]] for m in h.METHODS}
    path.write_text(json.dumps(payload))
    got=h.load_epoch_checkpoint(path,tasks=tasks,maps=maps,L=L)
    for m in h.METHODS:np.testing.assert_allclose(got[m],vectors[m])
    changed=[replace(tasks[0],shots=1),*tasks[1:]]
    with pytest.raises(ValueError,match='task identity'):
        h.load_epoch_checkpoint(path,tasks=changed,maps=maps,L=L)
    first=payload['raw_counts'][0];keys=list(first);first[keys[0]]-=1;first[keys[1]]+=1
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='checksum'):
        h.load_epoch_checkpoint(path,tasks=tasks,maps=maps,L=L)

def test_duplicate_primitive_task_rejected():
    tasks=h.build_epoch_tasks(0,1);counts=h.DeterministicProbabilitySampler().run(tasks,epoch=0)
    with pytest.raises(ValueError,match='Duplicate'):
        h.gap_vectors_for_epoch(tasks+[tasks[0]],counts+[counts[0]],h.method_maps(h.effective_scale_tuple()),h.contrast_matrix(4,ref=0))

@pytest.mark.parametrize('kw',[{'shots':512},{'r_final':1},{'epochs':0},{'bootstrap_repetitions':0}])
def test_incompatible_run_config_stops_before_sampling(tmp_path,kw):
    sampler=h.DeterministicProbabilitySampler()
    with pytest.raises(ValueError):
        h.run_pipeline(config=h.RunConfig(output_dir=tmp_path,**kw),sampler=sampler)
    assert sampler.submitted_batches==0

def test_archive_context_restores_state_after_error(tmp_path):
    original=(h.active_physical_qubits(),h.FEASIBILITY_RECORD,a.ARCHIVE_ROOT)
    with pytest.raises(RuntimeError):
        with a.archive_context(tmp_path):raise RuntimeError('stop')
    assert (h.active_physical_qubits(),h.FEASIBILITY_RECORD,a.ARCHIVE_ROOT)==original

def test_archive_loader_checks_job_and_shots(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'ARCHIVE_ROOT',tmp_path);(tmp_path/'raw_counts').mkdir()
    path=tmp_path/'raw_counts/example.json'
    path.write_text(json.dumps({'job_id':'wrong','raw_counts':[{'0000':4096}]}))
    with pytest.raises(ValueError,match='job identity'):a.load_raw_counts('example')
    task=h.build_epoch_tasks(0,1)[0]
    path.write_text(json.dumps({'job_id':'example','raw_counts':[{'0000':4095}],
                               'tasks':[h._task_metadata(task)]}))
    with pytest.raises(ValueError,match='shot total'):a.load_raw_counts('example',tasks=[task])

def test_covariance_does_not_invent_zero_uncertainty_from_one_sample():
    with pytest.raises(ValueError,match='at least two'):
        h.covariance_from_gap_vectors([np.ones(3)])

def test_primitive_helper_does_not_overwrite_other_methods():
    tasks=h.build_epoch_tasks(0,1)
    with pytest.raises(ValueError,match='single method'):
        h.primitive_vector_from_counts(tasks,[])

@pytest.mark.parametrize('missing',[False,True])
def test_feasibility_preserves_counts_and_rejects_missing_results(tmp_path,monkeypatch,missing):
    from experiments.hardware_sigma import run_feasibility as f
    import qiskit_ibm_runtime as runtime
    backend=SimpleNamespace(name='test-device',num_qubits=4,target=None,operation_names=[])
    score=SimpleNamespace(path=(0,1,2,3),score=.01,mean_readout_error=.01,
        mean_two_qubit_error=.01,readout_errors=(.01,)*4,edge_errors=(.01,)*3)
    monkeypatch.setattr(f,'_connect_service',lambda **kw:object())
    monkeypatch.setattr(f,'_usage_summary',lambda s:{})
    monkeypatch.setattr(f,'select_backend_blind',lambda *args:(backend,score,[]))
    monkeypatch.setattr(f,'_single_reference_transpile',lambda *args:h.QuantumCircuit(4))
    circuits=[{'label':str(i),'candidate_idx':i//2,'scale':1 if i%2==0 else 3} for i in range(8)]
    monkeypatch.setattr(f,'_build_feasibility_circuits',lambda:circuits)
    monkeypatch.setattr(f,'_transpile',lambda *args:[h.QuantumCircuit(4)]*8)
    monkeypatch.setattr(f,'_extract_pub_counts',lambda p:p)
    monkeypatch.setattr(f,'_job_metadata',lambda j:{'job_id':'test'})
    monkeypatch.setattr(f,'_calibration_snapshot_id',lambda b:'test')
    monkeypatch.setattr(f,'coupling_edges',lambda b:{(0,1),(1,2),(2,3)})
    monkeypatch.setattr(f,'OUTPUT_JSON',tmp_path/'feasibility.json')
    counts=[{'0000':2048,'0001':2048}]*(7 if missing else 8)
    job=SimpleNamespace(job_id=lambda:'test',result=lambda:counts)
    monkeypatch.setattr(runtime,'SamplerV2',lambda **kw:SimpleNamespace(run=lambda *a,**k:job))
    if missing:
        with pytest.raises(ValueError,match='shorter'):
            f.run_feasibility(backend_name='test',region='test',instance=None)
        assert not (tmp_path/'feasibility.json').exists()
    else:
        result=f.run_feasibility(backend_name='test',region='test',instance=None)
        assert result['raw_counts']==counts
        assert json.loads((tmp_path/'feasibility.json').read_text())['raw_counts']==counts

def test_partial_run_is_not_a_pass(tmp_path,monkeypatch):
    # Force a favorable point estimate: incomplete data still cannot pass.
    monkeypatch.setattr(h,'endpoint_projected_ranking',lambda **kw:{'primary_pass':True,'pairs':[]})
    result=h.run_pipeline(config=h.RunConfig(output_dir=tmp_path,epochs=2,reps_per_epoch=1,bootstrap_repetitions=5),
        sampler=h.DeterministicProbabilitySampler(),true_rates=np.full(7,.004),stop_after_epoch=0)
    assert result['status']=='incomplete_checkpointed'
    assert result['result_label']=='incomplete_not_evaluated'
    assert not result['primary_projected_ranking']['primary_pass']
    assert result['config']['R_final']==2
