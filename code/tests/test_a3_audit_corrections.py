import json
import numpy as np
import pytest
from sklearn.covariance import LedoitWolf
from experiments import a3_gaussianity_sigmahat_audit as a


def test_covariance_ci_fits_the_full_estimator_before_extracting():
    rng=np.random.default_rng(12);samples=rng.normal(size=(40,4))*[1,2,3,10]
    indices=rng.integers(0,40,size=(50,40));active=np.array([0,1])
    covs=np.array([LedoitWolf().fit(samples[row]).covariance_[:2,:2] for row in indices])
    lo,hi=np.quantile(covs,[.025,.975],axis=0)
    actual=a.covariance_ci_summary(samples,active,indices=indices,ci=.95)
    assert actual['max_cov_ci_width']==pytest.approx((hi-lo).max(),rel=1e-12)
    wrong=np.array([LedoitWolf().fit(samples[row,:2]).covariance_ for row in indices])
    l,u=np.quantile(wrong,[.025,.975],axis=0)
    assert abs((hi-lo).max()-(u-l).max())>.1


def test_budget_matching_uses_labels_not_axis_positions():
    estimates=np.zeros((4,3,2,2));estimates[:,:,1,0]=10;estimates[:,:,1,1]=20
    raw=dict(primitive_objective_estimates=estimates,ideal_values=np.array([0.,1.]),x_star=0,budgets=np.array([512,256]))
    frozen=dict(budgets=np.array([256,512]),method_names=np.array(['Raw']),method_coefficients=np.array([[1.,0.,0.]]))
    assert np.all(a.method_samples(raw,frozen,0)['Raw']==20)
    assert np.all(a.method_samples(raw,frozen,1)['Raw']==10)


def test_unresolved_risk_is_not_a_strict_order_or_pass():
    assert a.risk_order(['A','B'],[.1,.1])=='A~B'
    assert a.risk_order(['A','B'],[1e-30,2e-30])=='A~B'
    assert a.risk_order(['A','B'],[.1,.2])=='A<B'
    with pytest.raises(ValueError):a.projected_ratio_for_pair(sigma_left=np.eye(2),sigma_right=np.eye(2),sigma_pred_left=np.eye(2),sigma_pred_right=np.eye(2),grad_left=np.eye(2),grad_right=np.eye(2),tau=0,epsilon0=1e-12)


def test_hz_whitened_formula_and_affine_invariance():
    rng=np.random.default_rng(24);x=rng.normal(size=(40,3));n,p=x.shape
    centered=x-x.mean(axis=0);cov=centered.T@centered/n;inv=np.linalg.inv(cov)
    beta=(((2*p+1)*n/4)**(1/(p+4)))/np.sqrt(2)
    pair=sum(np.exp(-beta**2/2*((u-v)@inv@(u-v))) for u in centered for v in centered)/n**2
    single=sum(np.exp(-beta**2/(2*(1+beta**2))*(u@inv@u)) for u in centered)/n
    expected=n*(pair-2*(1+beta**2)**(-p/2)*single+(1+2*beta**2)**(-p/2))
    assert a.henze_zirkler_statistic(x)==pytest.approx(expected,abs=1e-13)
    transform=np.array([[2.,.4,0],[0,1.,.2],[.1,0,3.]])
    assert a.henze_zirkler_statistic(x@transform+[3,2,1])==pytest.approx(expected,abs=1e-13)


def test_degenerate_diagnostic_is_unavailable():
    assert a._anderson_reject_5(np.ones(20))==(None,None)
    assert a.tail_ratios(np.ones(20),[2.,3.])=={2.:None,3.:None}
    with pytest.raises(ValueError):a.tail_ratios([1,np.nan],[2.])
import numpy as np
from experiments import a3_gaussianity_sigmahat_audit as a
import pytest


def test_c3_uses_its_own_threshold_and_the_signed_learned_shift():
    case={'bootstrap_signed_projection_errors':np.array([[.08,.09,.1,.11,.12]])}
    values=a.c3_bootstrap_summary(case,0,signed_learned_error=.1,tau=.05,ci=.8)
    assert values['reference']['verdict']=='interval_above_threshold'
    assert values['learned']['verdict']=='interval_below_threshold'
    # A3's twice-larger tolerance would instead straddle one.
    assert a.c3_bootstrap_summary(case,0,signed_learned_error=0,tau=.1,ci=.8)['reference']['verdict']=='interval_crosses_threshold'

@pytest.mark.parametrize('mutation',['raw','gradient','evidence'])
def test_audit_refuses_stale_sources_and_mismatched_derivatives(tmp_path,mutation):
    folder=tmp_path/a.EVIDENCE_REL;folder.mkdir(parents=True)
    raw=tmp_path/a.raw_relpath('P001');raw.parent.mkdir(parents=True);raw.write_bytes(b'raw')
    frozen=tmp_path/a.FROZEN_REL_DIR/'P001.npz';frozen.parent.mkdir(parents=True);frozen.write_bytes(b'frozen')
    grad=np.ones((3,2,2));risks=np.array([.1,.2,.3]);path=folder/'P001_B256.npz'
    np.savez(path,gradients=grad,predicted_risks=risks)
    source=dict(raw_sha256=a.sha256(raw),frozen_sha256=a.sha256(frozen))
    metadata=dict(schema=a.AUDIT_SCHEMA,instance_id='P001',budget=256,evidence_sha256=a.sha256(path),**source)
    path.with_suffix('.json').write_text(json.dumps(metadata))
    (folder/'audit_index.json').write_text(json.dumps(dict(schema=a.AUDIT_SCHEMA,sources={'P001':source},cases={'P001_B256':a.sha256(path)},calibration_rows=[])))
    assert a.load_current_case_evidence(tmp_path,'P001',256,gradients=grad,predicted_risks=risks) is not None
    if mutation=='raw':raw.write_bytes(b'changed')
    elif mutation=='gradient':grad=grad*2
    else:path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError):a.load_current_case_evidence(tmp_path,'P001',256,gradients=grad,predicted_risks=risks)
