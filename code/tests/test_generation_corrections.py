from pathlib import Path
import json
import subprocess
import sys
import numpy as np
import pytest
from experiments import a3_pullback_frontier as a3
from daqem.learned_control import common_incumbent_gradient


def small_config():
    config=a3.load_config('smoke')
    config['gate0_config'].update(candidate_count=4,budget_grid=[8,16],B_max=16)
    config.update(min_active_gaps=1,max_active_gaps=1)
    return config


def fake_moments(**kwargs):
    means=np.tile(np.array([0.,.1,.12,.14]),(3,1));variance=np.ones_like(means)
    if kwargs.get('evidence_path') is not None:
        a3._write_deterministic_npz(kwargs['evidence_path'],means=means,variances=variance)
    return means,variance,means[0],np.asarray(0)


def test_generator_uses_full_gradient_even_with_one_gap_mask(tmp_path,monkeypatch):
    monkeypatch.setattr(a3,'_primitive_objective_moments',fake_moments)
    path=a3.build_frozen_prediction_for_cell(instance_id='P001',output_root=tmp_path,config=small_config())
    with np.load(path) as f:
        for mi in range(3):
            for bi in range(2):
                mask=f['active_masks'][mi,bi];grad=f['gradients'][mi,bi]
                assert mask.sum()==1
                assert np.any(np.abs(grad[~mask])>1e-5)
                np.testing.assert_allclose(grad,common_incumbent_gradient(f['mu'],f['sigma_pred'][mi,bi]),rtol=0,atol=0)
        assert not f['gradient_unstable'].any() and (f['gradient_steps']==0).all()
        metadata=json.loads(str(f['metadata_json']))
        assert metadata['prospective_preregistration'] is False
        assert metadata['primitive_evidence_hash']==a3._sha256(tmp_path/metadata['primitive_evidence_path'])
    original=path.read_bytes()
    with pytest.raises(FileExistsError):
        a3.build_frozen_prediction_for_cell(instance_id='P001',output_root=tmp_path,config=small_config())
    assert path.read_bytes()==original


def test_existing_prediction_stops_run_before_simulation(tmp_path,monkeypatch):
    config=small_config();monkeypatch.setattr(a3,'load_config',lambda _:config)
    path=tmp_path/a3.FROZEN_REL_DIR/'P001.npz';path.parent.mkdir(parents=True);path.write_bytes(b'archived')
    monkeypatch.setattr(a3,'build_frozen_prediction_for_cell',lambda **_:pytest.fail('must not simulate'))
    with pytest.raises(FileExistsError):a3.run(tmp_path)
    assert path.read_bytes()==b'archived'


def test_zero_variance_mean_mismatch_is_not_a_pass():
    frozen=dict(primitive_mean_unit=np.zeros((3,2)),cdev_true_diag_unit=np.zeros(6))
    raw=dict(primitive_objective_estimates=np.zeros((2,3,2,1)),budgets=np.array([8]))
    raw['primitive_objective_estimates'][:,0,0,0]=1.
    row=a3.mean_crosscheck_from_frozen_raw(instance_id='P001',frozen=frozen,raw=raw)
    assert row['max_z_score']==np.inf and row['means_ok'] is False
    raw['primitive_objective_estimates'][:]=0
    assert a3.mean_crosscheck_from_frozen_raw(instance_id='P001',frozen=frozen,raw=raw)['means_ok'] is True


def test_failed_hash_prevents_any_raw_read(tmp_path):
    path=tmp_path/'f.npz';a3._write_deterministic_npz(path,test=np.array([0]))
    with pytest.raises(ValueError,match='hash mismatch'):
        a3.analyze_cell_from_frozen_prediction(instance_id='P001',frozen_path=path,
            frozen_hash='bad',output_root=tmp_path,config=small_config())


@pytest.mark.parametrize('name',['control_affine','control_common_mode','control_mse_enough',
    'e4_power_sensitivity_audit','e5_claim_survival_table','focal_lower_bound','regime_frontier',
    'robustness_generality_matrix','hardware_ordering_analysis','hardware_sigma_microcell_analysis'])
def test_reserved_entrypoint_does_not_exit_successfully(name):
    script=Path(a3.__file__).parent/(name+'.py')
    result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
    assert result.returncode!=0 and 'placeholder' in result.stderr


def test_dense_Aer_snapshot_keeps_rare_probability(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import networkx as nx
    from qiskit import QuantumCircuit
    eps=1e-12
    # Isolate probability extraction from the compiler's approximate removal
    # of tiny rotations; the model is the distribution of compiled circuits.
    real_transpile=a3.transpile
    monkeypatch.setattr(a3,'transpile',lambda *args,**kw:real_transpile(*args,optimization_level=0,**kw))
    landscape=SimpleNamespace(angles=np.zeros((2,2)),ideal_values=np.array([0.,1.]),x_star=0)
    monkeypatch.setattr(a3,'landscape_for_instance',lambda *args,**kwargs:landscape)
    monkeypatch.setattr(a3,'maxcut_graph_for_instance',lambda *args,**kwargs:nx.Graph([(0,1)]))
    def circuit(*args,**kwargs):
        qc=QuantumCircuit(2);qc.ry(2*np.arcsin(np.sqrt(eps)),0);return qc
    monkeypatch.setattr(a3,'qaoa_maxcut_circuit',circuit)
    config=small_config()['gate0_config'];config.update(depth=1,qubits=2,graph_degree=1,candidate_count=2)
    path=tmp_path/'primitives.npz'
    means,variances,_,_=a3._primitive_objective_moments(instance_id='x',gate0_config=config,
        noise_model_factory=lambda i,s:None,evidence_path=path)
    np.testing.assert_allclose(means,-eps,atol=1e-22,rtol=0)
    np.testing.assert_allclose(variances,eps*(1-eps),atol=1e-22,rtol=0)
    with np.load(path) as data: assert np.all(data['probabilities'][:,:,1]>0)


def test_univariate_gradient_matches_normal_tail_derivative():
    from scipy.stats import norm
    for mean in (-.2,0.,.2):
        var=.3;step=1e-6
        derivative=(norm.sf(mean/np.sqrt(var+step))-norm.sf(mean/np.sqrt(var-step)))/(2*step)
        np.testing.assert_allclose(common_incumbent_gradient([mean],[[var]])[0,0],derivative,atol=1e-10,rtol=0)


def test_raw_metadata_budget_order_is_not_an_axis_contract():
    cfg=small_config()['gate0_config']
    raw=dict(metadata_json=np.array(json.dumps(dict(instance_id='P001',profile=cfg['profile'],
        candidate_count=4,budget_grid=[16,8]))),budgets=np.array([8,16]))
    a3._validate_raw(raw,'P001',cfg)
    raw['budgets']=np.array([8,32])
    with pytest.raises(ValueError):a3._validate_raw(raw,'P001',cfg)
