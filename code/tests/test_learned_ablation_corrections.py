import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import norm
from qiskit import transpile
from qiskit_aer import AerSimulator
from daqem import cdev
from daqem.noise import depolarizing_noise_model
from daqem.learned_control import common_incumbent_gradient,diagnostic_interpretation
from daqem.risk import gri_covariance_gradient,gri_risk
from experiments.gate0_pilot_full_vs_diagonal import _criterion
from experiments.cdev_learned_arm import _active_pullback_rows

@pytest.mark.parametrize('kind,depth',[('one_qubit',1),('one_qubit',4),('two_qubit',1),('two_qubit',4)])
def test_decay_model_matches_actual_quantum_channel(kind,depth):
    gen=cdev.PauliLindbladGenerator('probe',kind,(0,) if kind=='one_qubit' else (0,1))
    circuit=cdev.characterization_circuit(gen,depth).remove_final_measurements(inplace=False)
    circuit.save_probabilities()
    sim=AerSimulator(method='density_matrix',noise_model=depolarizing_noise_model(),max_parallel_threads=1)
    p=sim.run(transpile(circuit,sim,optimization_level=0)).result().data()['probabilities']
    if kind=='one_qubit':expectation=(p[0]-p[1])*(-1)**depth;rate=.01
    else:expectation=p[0]-p[1]-p[2]+p[3];rate=.03
    assert abs(expectation-(1-rate)**depth)<1e-12

@pytest.mark.parametrize('n',[2,3])
@pytest.mark.parametrize('shared',[0.,.07,.8])
def test_full_gradient_matches_general_conditional_normal(n,shared):
    mu=np.linspace(.1,1.2,n);sigma=np.diag(np.linspace(.2,.5,n))+shared
    np.testing.assert_allclose(common_incumbent_gradient(mu,sigma),gri_covariance_gradient(mu,sigma),rtol=2e-7,atol=1e-9)

def test_gradient_direction_agrees_with_independent_quadrature():
    mu=np.linspace(.1,2.8,24);v=np.linspace(.1,.5,24);s=.2
    dv=np.linspace(-.02,.03,24);ds=.04
    def risk(t):
        return quad(lambda z:norm.pdf(z)*(1-np.prod(ndtr((mu-np.sqrt(s+t*ds)*z)/np.sqrt(v+t*dv)))), -12,12,epsabs=1e-12)[0]
    numeric=(risk(1e-3)-risk(-1e-3))/(2e-3)
    analytic=np.sum(common_incumbent_gradient(mu,np.diag(v)+s)*(np.diag(dv)+ds))
    assert abs(numeric-analytic)<1e-9

@pytest.mark.parametrize('y',[[],[np.nan],[np.inf],[1.1]])
def test_rate_fit_rejects_invalid_data(y):
    with pytest.raises(ValueError):cdev.fit_depolarizing_rate(np.ones(len(y)),np.array(y))

@pytest.mark.parametrize('args',[(np.array([.1]),np.array([.1,.2]),.1), (np.array([.1]),np.array([np.nan]),.1)])
def test_support_must_not_broadcast_or_accept_nan(args):
    with pytest.raises(ValueError):cdev.support_f1_score(args[0],args[1],threshold=args[2])

@pytest.mark.parametrize('weights',[[1.,-0.1],[1.,np.nan]])
def test_error_rejects_bad_weights(weights):
    with pytest.raises(ValueError):cdev.weighted_relative_l1_error([.1,.2],[.1,.3],weights,eps0=1e-12)

def test_negative_rates_cannot_be_silently_clamped():
    with pytest.raises(ValueError):cdev.learned_depolarizing_noise_model(p1=-.01,p2=.03)

@pytest.mark.parametrize('active,left,right,audit,expected',[
    (False,True,True,'pass','inactive_pair'),
    (True,None,True,'pass','inconclusive_missing_validation'),
    (True,True,True,'not_reported','inconclusive_missing_validation'),
    (True,False,True,'pass','empirical_fallback_only'),
    (True,True,True,'sampling_sensitive','inconclusive_sampling')])
def test_diagnostic_requires_valid_evidence(active,left,right,audit,expected):
    assert diagnostic_interpretation(active=active,true_matches=True,learned_matches=True,gaussian_left=left,gaussian_right=right,audit=audit)==expected

def test_risk_difference_does_not_claim_shot_savings():
    assert _criterion(.001,False,10000.,{'margin_threshold':.005,'bstar_gain_threshold':1.})=='none'
    assert _criterion(.01,False,10000.,{'margin_threshold':.005})=='gri_margin'

def test_duplicate_active_rows_are_rejected(tmp_path):
    (tmp_path/'pilot').mkdir()
    (tmp_path/'pilot/pullback_frontier.csv').write_text('problem_cell,pair_id,budget,active_pair\nP001,A_vs_B,256,False\nP001,A_vs_B,256,False\n')
    with pytest.raises(ValueError):_active_pullback_rows(tmp_path,'P001')

def test_probe_basis_canonicalizes_edges():
    basis=cdev.sparse_pl_basis(num_qubits=2,graph_edges=[(1,0),(0,1)])
    assert len(basis)==3

def test_general_rare_tail_respects_tight_union_bounds():
    z=np.array([12.5,13.1,14.])
    cov=np.array([[1.,.4,.5],[.4,1.,.35],[.5,.35,1.]])
    value=gri_risk(z,cov)
    marginal=norm.sf(z)
    assert marginal.max()<=value<=marginal.sum()*(1+1e-14)
    assert abs(value/marginal.sum()-1)<1e-8

def test_general_correlated_rare_tail_matches_conditional_integration():
    # Unequal off-diagonals bypass the specialized common-incumbent branch.
    z=np.array([8.7,8.75,15.])
    cov=np.array([[1.,.96,.1],[.96,1.,.1],[.1,.1,1.]])
    first=norm.sf(z[0]);second=norm.sf(z[1])
    joint=first*quad(lambda u:norm.cdf((.96*norm.isf(first*u)-z[1])/np.sqrt(1-.96**2)),0,1,epsabs=1e-11)[0]
    expected=first+second-joint
    value=gri_risk(z,cov)
    assert abs(value/expected-1)<1e-7
