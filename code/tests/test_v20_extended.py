import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import numpy as np
from scipy.stats import norm
from scipy.integrate import quad
from daqem.risk import gri_risk,gri_covariance_gradient
from daqem.qem_methods import decision_optimal_zne_coeffs,richardson_constraints
from run_archive_corrections import dynamic_ledger

def test_rare_independent_union():
    p=norm.sf(9.)
    assert np.isclose(gri_risk([9.,9.],np.eye(2)),2*p-p*p,rtol=1e-6,atol=0)

def test_units_multivariate():
    mu=np.array([.8,1.5]);cov=np.array([[1.,.2],[.2,2.]])
    for a in [1e-9,1e9]:
        assert np.isclose(gri_risk(a*mu,a*a*cov),gri_risk(mu,cov),atol=1e-8)

def test_gradient_against_independent_quadrature():
    mu=np.array([.4,1.2]);cov=np.array([[.7,.15],[.15,1.3]])
    def risk(s):
        sd=np.sqrt(np.diag(s));rho=s[0,1]/np.prod(sd);z=mu/sd
        success=quad(lambda x:norm.pdf(x)*norm.cdf((z[1]-rho*x)/np.sqrt(1-rho*rho)),
                     -np.inf,z[0],epsabs=1e-12)[0]
        return 1-success
    E=np.array([[.2,-.4],[-.4,.1]]);h=1e-5
    observed=(risk(cov+h*E)-risk(cov-h*E))/(2*h)
    assert np.isclose(np.sum(gri_covariance_gradient(mu,cov)*E),observed,atol=1e-9)

def test_three_dimensional_gradient_exact_zero_mean():
    sigma=np.array([[1.,.2,.3],[.2,2.,.1],[.3,.1,.8]])
    direction=np.array([[0.,1.,0.],[1.,0.,0.],[0.,0.,0.]])
    rho=sigma[0,1]/np.sqrt(sigma[0,0]*sigma[1,1])
    expected=-1/(4*np.pi*np.sqrt(sigma[0,0]*sigma[1,1])*np.sqrt(1-rho*rho))
    assert np.isclose(np.sum(gri_covariance_gradient(np.zeros(3),sigma)*direction),expected,rtol=1e-12)

def test_zero_variance_optimum():
    A,rho=richardson_constraints([1.,2.,3.],1)
    Q=np.diag([1.,0.,0.]);c=decision_optimal_zne_coeffs([Q],[1.],A,rho)
    assert c@Q@c < 1e-12
    assert np.allclose(c,[0,3,-2],atol=1e-5)

def test_proposals_and_training_are_charged_without_double_counting():
    ledger=dynamic_ledger(256,1,256)
    expected=19*5*8192+5*256+(40*3*25*256)/40
    assert ledger['total_shots_per_trajectory']==expected
    assert dynamic_ledger(256,3,256)['total_shots_per_trajectory']-expected==20*5*2*256

def test_fisher_null_fixed_gap_counterexample():
    p,q=.5,.5+(-.5)**3/4
    kl=p*np.log(p/q)+(1-p)*np.log((1-p)/(1-q))
    assert kl>0
    assert 2*((p-q)/2)**2==.00048828125

def test_weakly_active_constraint():
    sigma=np.array([[1.,.5],[.5,1.]]);mu=np.array([1.,.5])
    alpha=np.linalg.solve(sigma,mu);y=-sigma@alpha
    assert np.allclose(alpha,[1,0])
    assert np.allclose(y,-mu)  # Both constraints bind despite zero multiplier.

def test_fakekolkata_test_data_cannot_change_fit_or_selection(monkeypatch):
    from types import SimpleNamespace
    import run_fakekolkata_v21 as fb
    rng=np.random.default_rng(17);ideal=np.linspace(0,2,25)
    raw=ideal[None,:,None]+rng.normal(size=(40,25,1))
    primitive=ideal[None,None,:,None]+rng.normal(size=(40,3,25,1))
    primitive=np.rint(primitive*170)/170
    rem=ideal[None,:,None]+rng.normal(size=(40,25,1))
    arrays=[raw,primitive,rem]
    monkeypatch.setattr(fb.old,'_primitive_samples',lambda *args:tuple(arrays))
    cell=SimpleNamespace(instance_id='unit',ideal_values=ideal,x_star=0)
    first,_=fb.analyze(cell)
    for arr in arrays:arr[20:]=rng.integers(-1000,1000,size=arr[20:].shape)
    second,_=fb.analyze(cell)
    assert first['coefficients']==second['coefficients']
    assert first['choices']==second['choices']
    assert first['scores']==second['scores']
    assert first['failures']!=second['failures']
    assert first['ledger']['GRI-selector']['fit']==127500
    assert first['ledger']['GRI-selector']['selection']==383500
