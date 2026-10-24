from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Pauli, SuperOp
from qiskit_aer.noise import depolarizing_error

from daqem.cdr import bracketing_clifford_endpoint_angles, fit_linear_cdr
from daqem.pec import (_append_ideal_pauli, _label_from_qiskit_instruction,
    inverse_depolarizing_quasiprobabilities, one_qubit_gamma_closed_form, pec_overhead_ledger_row)
from daqem.pec import pec_expectation_aer
from daqem.qaoa import maxcut_graph
from experiments import proof_of_mechanism_run as p


@pytest.mark.parametrize('n,rate', [(1,0.),(2,0.),(1,.01),(2,.03),(1,1.2),(2,1.03)])
def test_signed_pauli_inverse_cancels_actual_aer_superoperator(n, rate):
    channel = inverse_depolarizing_quasiprobabilities(rate,n)
    inverse = sum(q * SuperOp(Pauli(label)).data for label,q in channel.quasi_probabilities.items())
    actual = SuperOp(depolarizing_error(rate,n)).data
    np.testing.assert_allclose(inverse @ actual,np.eye(4**n),atol=2e-13,rtol=0)
    assert sum(channel.sampling_probabilities.values()) == pytest.approx(1.)
    if n==1:
        assert channel.gamma == pytest.approx(one_qubit_gamma_closed_form(rate))


@pytest.mark.parametrize('n',[1,2])
def test_complete_depolarization_has_no_inverse(n):
    with pytest.raises(ValueError,match='not invertible'):
        inverse_depolarizing_quasiprobabilities(1.,n)


@pytest.mark.parametrize('label',['IX','XI','YZ','ZY'])
def test_sampled_correction_uses_qiskit_qubit_order(label):
    circuit=QuantumCircuit(2)
    _append_ideal_pauli(circuit,label,(0,1))
    np.testing.assert_allclose(Operator(circuit).data,Pauli(label).to_matrix(),atol=1e-15)
    instructions=[{'name':label[1].lower(),'qubits':[0]}, {'name':label[0].lower(),'qubits':[1]}]
    assert _label_from_qiskit_instruction(instructions,2)==label


@pytest.mark.parametrize('noisy,exact', [([1,1],[2,3]),([np.nan,1],[2,3]),([1,2],[3,np.inf])])
def test_cdr_rejects_unidentifiable_or_nonfinite_fit(noisy,exact):
    with pytest.raises(ValueError):
        fit_linear_cdr(np.array(noisy),np.array(exact))


def test_cdr_does_not_claim_to_bracket_angles_outside_locked_grid():
    with pytest.raises(ValueError,match='outside'):
        bracketing_clifford_endpoint_angles(np.array([-4.,4.]))
    lower,upper=bracketing_clifford_endpoint_angles(np.array([.7,1.2]))
    assert np.all(lower <= [.7,1.2]) and np.all(upper >= [.7,1.2])


def test_pec_ledger_keeps_factor_separate_from_executed_shots():
    row=pec_overhead_ledger_row(gamma=3.,B_nominal=128)
    assert row['gamma_squared']==9. and row['C_total']==0.
    row=pec_overhead_ledger_row(gamma=3.,n_samples=20,shots_per_sample=64)
    assert row['C_total']==1280 and row['C_overhead']==0.


def test_effective_proxy_never_invents_a_sample():
    assert p.effective_pec_shots(768,72.56683490923633)==10
    with pytest.raises(ValueError,match='no effective samples'):
        p.effective_pec_shots(3,4.)


@pytest.mark.parametrize('budget',[4,0,3.5])
def test_matched_shot_protocol_rejects_truncation(budget):
    config=deepcopy(p.load_config())
    config['budget_grid']=[budget]
    with pytest.raises(ValueError):
        p.validate_config(config)


def sample_fixture(tied=True):
    config=deepcopy(p.load_config())
    config.update(budget_grid=[3],replicates=2)
    probs=np.ones((3,3))/3 if tied else np.eye(3)[[2,1,0]]
    if tied:
        probs[:]=[1,0,0]
    item=dict(instance_id='TEST',x_star=0 if tied else 2,
        landscape=SimpleNamespace(ideal_values=np.array([-2.,-1.,0.]) if tied else np.array([0.,-1.,-2.])),
        cdr_fit={'a':1.,'b':1e20},gamma_squared=1.,values_by_state=np.array([-2.,-1.,0.]),
        noisy_probs=np.repeat(probs[None],3,axis=0),ideal_probs=probs,
        coefficients={'Accuracy-ZNE':np.array([4,1,-2])/3,'Decision-ZNE':np.array([2.,-1.,0.])})
    return item,config


def test_all_exact_ties_fail_independent_of_first_index(tmp_path):
    item,config=sample_fixture()
    observations=p.empirical_observations([item],config,sample_archive_dir=tmp_path)
    assert all(row['decision_failure']==1 for row in observations)
    with np.load(tmp_path/'TEST_samples.npz') as data:
        assert data['zne_sums'].shape==(2,3,3)


def test_affine_control_preserves_ranking_even_when_offset_loses_float_gaps():
    item,config=sample_fixture(False)
    observations=p.empirical_observations([item],config)
    assert all(row['decision_failure']==0 for row in observations)


def test_conditional_bootstrap_preserves_fixed_instance_weights():
    draws=np.random.default_rng(1).integers(0,3,size=(1000,2,3))
    assert p._bootstrap_ci(np.array([[0,0,0],[1,1,1]]),draws=draws,alpha=.05)==[.5,.5]


def test_pec_materializes_iterable_angles_for_repeated_circuits():
    graph=maxcut_graph(num_qubits=2,degree=1,seed=1)
    kwargs=dict(depth=1,n_samples=4,shots_per_sample=16)
    left=pec_expectation_aer(graph,gammas=iter([.3]),betas=iter([.4]),**kwargs)
    right=pec_expectation_aer(graph,gammas=[.3],betas=[.4],**kwargs)
    assert left==right


def test_pec_rejects_fractional_shot_counts():
    with pytest.raises(ValueError,match='positive integers'):
        pec_expectation_aer(maxcut_graph(num_qubits=2,degree=1,seed=1),depth=1,
            gammas=[.3],betas=[.4],n_samples=2,shots_per_sample=1.5)


def test_affine_control_cannot_silently_use_a_negative_slope():
    item,config=sample_fixture()
    item['cdr_fit']['a']=-1.
    with pytest.raises(ValueError,match='positive'):
        p.empirical_observations([item],config)


def test_aggregation_is_keyed_and_rejects_missing_or_duplicate_records():
    item,config=sample_fixture()
    item['epsilon_opt']=.01
    item['analytic_by_budget']={'3':{name:{'GRI':.5,'I_hat':1.} for name in p.METHODS}}
    observations=p.empirical_observations([item],config)
    expected=p.aggregate([item],observations,config)
    assert p.aggregate([item],list(reversed(observations)),config)==expected
    for invalid in (observations[:-1],observations+[observations[0]]):
        with pytest.raises(ValueError,match='missing or duplicate'):
            p.aggregate([item],invalid,config)


def test_probability_generation_retains_outcomes_below_dictionary_cutoff(monkeypatch):
    import networkx as nx
    def circuit(*args,**kwargs):
        qc=QuantumCircuit(1)
        qc.ry(2e-5,0)
        return qc
    monkeypatch.setattr(p,'qaoa_maxcut_circuit',circuit)
    config=deepcopy(p.load_config())
    config['cell']['depth']=1
    landscape=SimpleNamespace(angles=np.array([[.3,.4]]))
    graph=nx.empty_graph(1)
    noisy,ideal,_=p._probability_arrays('tiny',graph,landscape,config)
    assert ideal[0,1]==pytest.approx(np.sin(1e-5)**2,rel=1e-12)
    assert np.all(noisy[:,:,1]>0)


def test_probability_validation_rejects_truncated_mass():
    with pytest.raises(ValueError,match='mass was lost'):
        p._validated_probabilities(np.array([1.-1e-8,0.]),2)
