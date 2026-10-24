"""Relaxed CDF arithmetic must never admit changed decisions or other fields."""
from copy import deepcopy
import pytest
from scripts.compare_release import equivalent,normalized_c3,CDF_ATOL

def compare(a,b):
    equivalent(a,b,'test',{'max_abs_difference':0.})

def test_cdf_bound_is_field_specific():
    compare({'gri':.3},{'gri':.3+6.49e-7})
    with pytest.raises(ValueError,match='Numeric'):
        compare({'gri':.3},{'gri':.3+2*CDF_ATOL})
    with pytest.raises(ValueError,match='Numeric'):
        compare({'mse':.3},{'mse':.3+6.49e-7})

@pytest.mark.parametrize('field,value,changed',[
    ('active_pair',True,False),('selected_method','Raw','Decision-ZNE'),
    ('success_decision',1,0),('c3_interpretation','inactive_pair','inconclusive_sampling')])
def test_discrete_changes_are_never_tolerated(field,value,changed):
    with pytest.raises(ValueError,match='Exact'):
        compare({field:value},{field:changed})

def example(tau):
    return {'c2':[{'cell':'P001','pair_id':'a_vs_b','budget':1,'tau_C':tau,
                  'projected_error_over_tolerance':.01/tau}],
            'c3':[{'cell':'P001','pair_id':'a_vs_b','budget':1,
                   'true_vs_sigmahat_ratio':.02/tau,'learned_vs_sigmahat_ratio':.03/tau,
                   'sampling_intervals_at_C3_tolerance':{
                       'reference':{'bootstrap_ratio_ci_low':.001/tau,'bootstrap_ratio_ci_high':.002/tau,'verdict':'interval_above_threshold'}}}]}

def test_ratio_normalization_preserves_physical_errors_and_rejects_corruption():
    a=example(1e-10);b=example(2e-10);before=deepcopy(b)
    compare(normalized_c3(a),normalized_c3(b))
    assert b==before
    b['c3'][0]['learned_vs_sigmahat_ratio']*=1.01
    with pytest.raises(ValueError,match='Numeric'):
        compare(normalized_c3(a),normalized_c3(b))

def test_ratio_normalization_does_not_hide_threshold_verdict_flip():
    a=example(1e-10);b=deepcopy(a)
    b['c3'][0]['sampling_intervals_at_C3_tolerance']['reference']['verdict']='interval_below_threshold'
    with pytest.raises(ValueError,match='Exact'):
        compare(normalized_c3(a),normalized_c3(b))
