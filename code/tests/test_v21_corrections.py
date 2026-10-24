from pathlib import Path
from types import SimpleNamespace
import json,sys
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from daqem.decisions import zne_failures
from daqem.qem_methods import decision_optimal_zne_coeffs,richardson_constraints
from daqem.risk import gri_covariance_gradient


def test_archived_exact_accuracy_tie():
    sums=np.array([[[-4887,-4841],[-4562,-4584],[-4436,-4355]]])
    assert zne_failures(sums/512,0,512).tolist()==[True]
    sums[0,1,1]+=1
    assert zne_failures(sums/512,0,512).tolist()==[False]


def test_learned_richardson_tie_is_exact():
    c=np.array([1.7,-.4,-.3])
    # Gap sum (1,2,3) cancels for every point on the feasible line.
    x=np.array([[[0,1],[0,2],[0,3]]])/170
    assert zne_failures(x,0,170,coefficients=c).tolist()==[True]
    x[0,0,1]+=1/170
    assert zne_failures(x,0,170,coefficients=c).tolist()==[False]


@pytest.mark.parametrize('scale',[1e-24,1e-20,1.,1e20,1e24])
def test_covariance_scale_and_primal_dual_diagnostics(scale):
    A,b=richardson_constraints([1,2,3],1);Q=np.diag([1.,4.,9.])
    expected=np.array([21.,-3.,-5.])/13
    c,info=decision_optimal_zne_coeffs([scale*Q],1,A,b,return_diagnostics=True)
    assert (c@Q@c)/(expected@Q@expected)<1+1e-7
    assert abs(info['normalized_gap'])<1e-7
    assert info['stationarity_residual']<1e-7


def test_all_zero_objective_and_infeasible_constraints():
    A,b=richardson_constraints([1,2,3],1)
    c,info=decision_optimal_zne_coeffs([np.zeros((3,3))],1,A,b,return_diagnostics=True)
    assert np.allclose(A@c,b) and info['normalized_gap']==0
    with pytest.raises(ValueError,match='Infeasible'):
        decision_optimal_zne_coeffs([np.zeros((2,2))],1,[[1,1],[1,1]],[1,2])


def test_gradient_nearly_singular_positive_definite():
    rho=1-1e-10;sigma=np.array([[1.,rho],[rho,1.]])
    g=gri_covariance_gradient([1.,1.],sigma)
    expected=-np.exp(-1/(1+rho))/(4*np.pi*np.sqrt((1-rho)*(1+rho)))
    assert np.isfinite(g).all()
    assert g[0,1]==pytest.approx(expected,rel=1e-10)


def test_nearly_singular_3d_gradient_zero_mean():
    rho=1-1e-10;sigma=np.array([[1.,rho,.2],[rho,1.,.2],[.2,.2,1.]])
    expected=-1/(8*np.pi*np.sqrt((1-rho)*(1+rho)))
    assert gri_covariance_gradient(np.zeros(3),sigma)[0,1]==pytest.approx(expected,rel=1e-10)


def test_gradient_reports_insufficient_precision():
    with pytest.raises(ValueError,match='ill-conditioned|working precision'):
        gri_covariance_gradient([1,1],[[1,1-1e-15],[1-1e-15,1]])


@pytest.fixture
def cache_runner(monkeypatch):
    import run_fakekolkata_v21 as fb
    state={'generate':[],'analyze':[],'analysis_version':1,'probability_version':1}
    monkeypatch.setattr(fb,'FakeKolkataV2',lambda:object())
    monkeypatch.setattr(fb,'NoiseModel',SimpleNamespace(from_backend=lambda b:object()))
    monkeypatch.setattr(fb,'probability_identity',lambda name,*_:dict(instance=name,version=state['probability_version']))
    monkeypatch.setattr(fb,'analysis_identity',lambda name,h:dict(instance=name,hash=h,version=state['analysis_version']))
    def generate(name,*_):
        state['generate'].append(name);probs=np.full((3,25,1024),1/1024)
        return fb.old.CellData(instance_id=name,graph_edges=((0,1),),x_star=0,
            ideal_values=np.arange(25.),values_by_state=np.zeros(1024),noisy_observed_probs=probs,
            raw_gate_probs=probs,readout_matrices=np.tile(np.eye(2),(10,1,1)),mappings={})
    def analyze(cell):
        state['analyze'].append(cell.instance_id)
        record={'instance':cell.instance_id,'failures':{m:[0,1]*10 for m in [*fb.METHODS,'GRI-selector','MSE-selector']}}
        return record,(np.zeros((40,25)),np.zeros((40,3,25)),np.zeros((40,25)))
    monkeypatch.setattr(fb.old,'_probability_array_for_cell',generate)
    monkeypatch.setattr(fb,'analyze',analyze)
    def run(folder,*args):
        monkeypatch.setattr(sys,'argv',['run_fakekolkata_v21.py','--output',str(folder),*args]);fb.main()
        return json.loads((folder/'summary.json').read_text())
    return state,run


def test_regenerate_resume_and_dependency_invalidation(tmp_path,cache_runner):
    state,run=cache_runner
    run(tmp_path,'--instances','C001')
    run(tmp_path,'--instances','C001')
    assert len(state['generate'])==len(state['analyze'])==1
    run(tmp_path,'--instances','C001','--regenerate-probabilities')
    assert len(state['generate'])==len(state['analyze'])==2
    state['analysis_version']+=1
    run(tmp_path,'--instances','C001')
    assert len(state['generate'])==2 and len(state['analyze'])==3
    state['probability_version']+=1
    run(tmp_path,'--instances','C001')
    assert len(state['generate'])==3 and len(state['analyze'])==4
    (tmp_path/'C001_samples.npz').write_bytes(b'corrupt sample')
    run(tmp_path,'--instances','C001')
    assert len(state['generate'])==3 and len(state['analyze'])==5
    (tmp_path/'C001_probabilities.npz').write_bytes(b'corrupt probabilities')
    run(tmp_path,'--instances','C001')
    assert len(state['generate'])==4


def test_requested_subset_and_unique_ids(tmp_path,cache_runner):
    state,run=cache_runner
    run(tmp_path,'--instances','C001','C002')
    summary=run(tmp_path,'--instances','C001')
    assert summary['instances']==1 and summary['test_decisions']==20
    assert summary['instance_ids']==['C001']
    with pytest.raises(SystemExit):run(tmp_path,'--instances','C001','C001')


def test_wrapper_propagates_force(monkeypatch,tmp_path):
    import reproduce_v21 as wrapper
    calls=[]
    monkeypatch.setattr(wrapper.subprocess,'run',lambda command,**kw:calls.append(command))
    monkeypatch.setattr(sys,'argv',['reproduce_v21.py','--output',str(tmp_path),'--regenerate-probabilities'])
    wrapper.main()
    child=[cmd for cmd in calls if Path(cmd[1]).name=='run_fakekolkata_v21.py'][0]
    assert '--regenerate-probabilities' in child


def test_real_model_identity_ignores_generated_ids_and_preserves_calibration():
    import run_fakekolkata_v21 as fb
    def model():
        backend=fb.FakeKolkataV2();noise=fb.NoiseModel.from_backend(backend)
        return fb.bounded_backend(backend,noise)
    b1,n1,p1=model();b2,n2,p2=model()
    first=fb.probability_identity('C001',b1,n1,p1)
    assert first==fb.probability_identity('C001',b2,n2,p2)
    b2.target['x'][(0,)].error+=.001
    assert first!=fb.probability_identity('C001',b2,n2,p2)


def test_zero_fraction_requires_finite_information():
    # Singular alternative: one measurement separates the hypotheses perfectly.
    from scipy.special import rel_entr
    # Joint (uninformative bit, separating bit) distributions for budget two.
    p0=np.array([.5,0,.5,0]);p1=np.array([0,.5,0,.5])
    decision=np.array([0,1,0,1])
    assert p0[decision!=0].sum()==p1[decision==0].sum()==0
    assert np.isinf(rel_entr(p0,p1).sum())
    assert np.abs(p0-p1).sum()/2==1
    # Under the added finite-KL hypothesis, a sublinear count contributes o(B).
    p,q=.5,.4;kl=p*np.log(p/q)+(1-p)*np.log((1-p)/(1-q))
    assert np.isfinite(kl)
    contributions=np.array([np.sqrt(B)*kl/B for B in [100,10000,1000000]])
    assert np.all(np.diff(contributions)<0) and contributions[-1]<1e-4
