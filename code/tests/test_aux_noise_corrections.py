from copy import deepcopy
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Statevector
from qiskit_aer import AerSimulator

from daqem.structured_noise import single_qubit_ad_pd_error, two_qubit_ad_pd_error, structured_noise_model, _scaled_rate
from daqem.pec import heterogeneous_depolarizing_noise_model
from daqem.auxiliary_noise import full_probability_vector, simulate_primitives, evaluation_shot_counts
import experiments.a3_pullback_frontier as a3
import experiments.r1_full_run as r1
import experiments.r1_derisk_run as rd
import experiments.het_pec_derisk_run as het
from daqem.risk import gri_risk
from scipy.stats import norm


@pytest.mark.parametrize('ad,pd',[(0.,0.),(.006,.004),(.18,.12),(1.,1.),(1.,0.),(0.,1.)])
def test_ad_pd_matches_bloch_population_and_coherence(ad,pd):
    rho=np.array([[.3,.2+.1j],[.2-.1j,.7]])
    expected=rho.copy()
    expected[0,0]=rho[0,0]+ad*rho[1,1]
    expected[1,1]=(1-ad)*rho[1,1]
    expected[0,1]=rho[0,1]*np.sqrt((1-ad)*(1-pd))
    expected[1,0]=expected[0,1].conjugate()
    actual=DensityMatrix(rho).evolve(single_qubit_ad_pd_error(gamma_ad=ad,gamma_pd=pd)).data
    np.testing.assert_allclose(actual,expected,atol=2e-15,rtol=0)


def test_two_qubit_channel_matches_independent_kraus_calculation():
    ad,pd=.18,.12
    amplitude=[np.diag([1.,np.sqrt(1-ad)]),np.array([[0,np.sqrt(ad)],[0,0]])]
    phase=[np.diag([1.,np.sqrt(1-pd)]),np.diag([0.,np.sqrt(pd)])]
    kraus=[b@a for a in amplitude for b in phase]
    state=np.array([1.,1j,-.4,.3]);state=state/np.linalg.norm(state)
    rho=np.outer(state,state.conjugate())
    expected=sum(np.kron(a,b)@rho@np.kron(a,b).conjugate().T for a in kraus for b in kraus)
    actual=DensityMatrix(rho).evolve(two_qubit_ad_pd_error(gamma_ad=ad,gamma_pd=pd)).data
    np.testing.assert_allclose(actual,expected,atol=3e-15,rtol=0)


@pytest.mark.parametrize('kind',['structured','heterogeneous'])
def test_symmetric_noise_covers_both_rzz_orientations(kind):
    if kind=='structured':
        model=structured_noise_model(num_qubits=2,graph_edges=[(0,1)],gamma_ad=.2,gamma_pd=.1,scale=1.,
            one_qubit_gates=['rx'],two_qubit_gates=['rzz'])
    else:
        model=heterogeneous_depolarizing_noise_model(p1_by_qubit={0:0.,1:0.},p2_by_edge={(0,1):.2},
            one_qubit_gates=['rx'],two_qubit_gates=['rzz'])
    simulator=AerSimulator(method='density_matrix',noise_model=model,max_parallel_threads=1)
    circuits=[]
    for edge in ((0,1),(1,0)):
        qc=QuantumCircuit(2);qc.x(0);qc.rzz(.3,*edge);qc.save_probabilities();circuits.append(qc)
    result=simulator.run(circuits).result()
    left=np.asarray(result.data(0)['probabilities']);right=np.asarray(result.data(1)['probabilities'])
    np.testing.assert_allclose(left,right,atol=2e-15,rtol=0)
    assert left[0]>.01  # A missing error would leave all probability on state 01.


@pytest.mark.parametrize('value,scale,clip',[(-.01,1.,(0.,.95)),(.01,-1.,(0.,.95)),(np.nan,1.,(0.,.95)),(.01,1.,(.95,0.))])
def test_invalid_scaled_channel_is_rejected(value,scale,clip):
    with pytest.raises(ValueError):_scaled_rate(value,scale,clip)


def test_conflicting_oriented_rates_are_rejected():
    with pytest.raises(ValueError,match='conflicting'):
        heterogeneous_depolarizing_noise_model(p1_by_qubit={0:.01,1:.01},p2_by_edge={(0,1):.1,(1,0):.2},
            one_qubit_gates=['rx'],two_qubit_gates=['rzz'])


def small_config():
    config=deepcopy(r1.load_config())
    config['instance_ids']=['R1_TEST']
    config['primary_cell'].update(num_qubits=2,degree=1,depth=1,candidate_count=2,search_count=2,budget_grid=[3,6],replicates=2)
    return config


def test_explicit_simulator_rejects_a_different_graph():
    config=small_config();gate=r1._gate0_config(config)
    with pytest.raises(ValueError,match='labels'):
        simulate_primitives(instance_id='x',graph=nx.Graph([(1,2)]),gate0_config=gate,noise_model_factory=lambda i,s:None)


def test_auxiliary_wrappers_never_replace_a3_globals(monkeypatch):
    original_landscape=a3.landscape_for_instance;original_graph=a3.maxcut_graph_for_instance
    def primitive(**kwargs):
        assert a3.landscape_for_instance is original_landscape and a3.maxcut_graph_for_instance is original_graph
        raise RuntimeError('simulation interrupted')
    for module in (r1,rd,het):monkeypatch.setattr(module,'simulate_primitives',primitive)
    config=small_config();gate=r1._gate0_config(config);graph=nx.Graph([(0,1)])
    with pytest.raises(RuntimeError):r1._primitive_moments_on_graph(instance_id='x',graph=graph,config=config,gate0_config=gate,noise_model_factory=None)
    with pytest.raises(RuntimeError):het._primitive_moments_on_locked_graph(instance_id='x',graph=graph,gate0_config=gate,noise_model_factory=None)
    config['primary_cell']['graph_seed']=1;config['primary_cell']['instance_id']='x'
    with pytest.raises(RuntimeError):rd._primitive_moments_on_primary_graph(config=config,gate0_config=gate,noise_model_factory=None)
    assert a3.landscape_for_instance is original_landscape and a3.maxcut_graph_for_instance is original_graph


def test_probability_tail_is_retained_and_mass_loss_rejected():
    np.testing.assert_array_equal(full_probability_vector([1.-1e-10,1e-10],2),[1.-1e-10,1e-10])
    with pytest.raises(ValueError,match='mass was lost'):full_probability_vector([1.-1e-8,0.],2)


def test_r1_empirical_ties_are_failures_for_every_method(tmp_path):
    config=small_config();gate=r1._gate0_config(config)
    ideal=np.array([-1.,0.]);probs=np.zeros((3,2,4));probs[:,:,0]=1.
    data=dict(probabilities=probs,values_by_state=np.array([0.,-1.,-1.,0.]),ideal_values=ideal,x_star=0)
    item=dict(instance_id='R1_TEST',x_star=0,ideal_values=ideal,input_config=config,primitive_data=data,
        coefficients={'Raw':np.array([1.,0.,0.]),'Accuracy-ZNE':np.array([4,1,-2])/3,'Decision-ZNE':np.array([2.,-1.,0.])},
        budgets=[dict(budget=b,DA_selected_method='Raw',MSE_selected_method='Accuracy-ZNE',GRI={m:.5 for m in r1.METHODS}) for b in (3,6)])
    rows=r1.empirical_instance(instance_result=item,config=config,gate0_config=gate,sample_archive_dir=tmp_path)
    assert all(all(count==2 for count in row['failure_counts'].values()) for row in rows)
    with np.load(tmp_path/'R1_TEST_samples.npz') as record:assert record['primitive_sums'].shape==(4,3,2)
    item['input_config']={}
    with pytest.raises(ValueError,match='different configuration'):
        r1.empirical_instance(instance_result=item,config=config,gate0_config=gate)


def test_primitive_budget_is_not_reported_as_equal_total_cost():
    costs=evaluation_shot_counts(512,25)
    assert costs['per_candidate']=={'Raw':512,'Accuracy-ZNE':1536,'Decision-ZNE':1536}
    assert costs['all_candidates']['Raw']==12800
    assert costs['all_candidates']['Decision-ZNE']==38400


def test_undefined_relative_saving_is_not_imputed_as_zero():
    epsilon=[dict(instance_id=f'I{j}',epsilon_opt_ideal=j,difficulty_tercile=label) for j,label in enumerate(('hard','medium','easy'))]
    phase=[dict(instance_id=f'I{j}',budgets=[dict(budget=3,GRI={m:.5 for m in r1.METHODS})]) for j in range(3)]
    rows=[]
    for j,(raw,da,relative) in enumerate(((0,0,None),(2,1,.5),(4,3,.25))):
        rows.append(dict(instance_id=f'I{j}',budget=3,replicates=4,
            failure_counts={**{m:raw for m in r1.METHODS},'DA_selected':da,'MSE_selected':raw},
            absolute_reduction_DA_vs_Raw=(raw-da)/4,relative_reduction_DA_vs_Raw=relative))
    result=r1.aggregate_empirical(rows,phase,epsilon,[3])['continuous_epsilon_trend']['3']
    assert result['relative_trend_valid_instances']==2
    assert result['pearson_epsilon_vs_relative_reduction']==pytest.approx(-1.)
    for bad in (rows[:-1],rows+[rows[0]]):
        with pytest.raises(ValueError,match='missing or duplicate'):r1.aggregate_empirical(bad,phase,epsilon,[3])


@pytest.mark.parametrize('correlation',[0.,.25,.5,.9])
def test_rare_orthant_risk_respects_marginal_union_bounds(correlation):
    z=np.array([8.711759,9.63,11.])
    covariance=(1-correlation)*np.eye(3)+correlation*np.ones((3,3))
    risk=gri_risk(z,covariance)
    tails=norm.sf(z)
    assert tails.max()*(1-1e-10)<=risk<=tails.sum()*(1+1e-10)
    if correlation==0:
        assert risk==pytest.approx(-np.expm1(norm.logcdf(z).sum()),rel=1e-10,abs=0)


def test_rare_two_gap_risk_matches_positive_orthant_inclusion_exclusion():
    # Independent gaps have an exact product formula, even below machine epsilon.
    mu=np.array([8.,9.]);cov=np.diag([1.,1.])
    exact=norm.sf(8.)+norm.sf(9.)-norm.sf(8.)*norm.sf(9.)
    assert gri_risk(mu,cov)==pytest.approx(exact,rel=1e-10,abs=0)
