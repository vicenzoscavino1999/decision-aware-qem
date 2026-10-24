from copy import deepcopy
import numpy as np
import pytest
from experiments import e0_executability_audit as e0


def table_inputs():
    config, learning = e0.load_configs()
    timings = {b: {'median_seconds': .01, 'seconds_per_shot': .01/b} for b in config['budget_grid']}
    batch = dict(amortized_seconds_per_circuit=.01,budget=8192,batch_size=50,
                 median_total_seconds=.5,samples_seconds=[.5]*3)
    return config, learning, timings, batch


def test_counts_follow_actual_profiles_and_reuse():
    table, report = e0.build_budget_table(*table_inputs())
    shots=table.set_index('block').estimated_shots.to_dict()
    assert shots == dict(E1_static=48*40*25*3*8192,
        E2_dynamic=32*40*20*5*3*8192,Pilot_shared=4*200*25*3*8192,
        Uniform_Cdev=25*5*8*4096,E3_pullback=0)
    assert report['workloads']['Uniform_Cdev']['learning_runs']==1
    assert report['global_gate']=='conditional' and report['journal_recommendation'] is None
    for item in report['unresolved_blocks'].values():
        assert item['estimated_shots'] is None and item['wall_hours'] is None
    assert table.set_index('block').loc['E3_pullback','timing_status'].endswith('not_measured')
    assert np.isnan(table.set_index('block').loc['Uniform_Cdev','wall_hours_proxy'])


def test_cost_does_not_count_reusing_methods_as_extra_acquisition():
    args=table_inputs();before,_=e0.build_budget_table(*args)
    args[0]['static_workload']['method_menu_core'].append('reuse_the_same_raw')
    after,_=e0.build_budget_table(*args)
    np.testing.assert_array_equal(before.estimated_shots,after.estimated_shots)


def test_characterization_count_tracks_depths_and_identical_repeats():
    _,learning,_,_=table_inputs()
    learning['pauli_twirls']=2;learning['characterization_depths']=[1,3]
    assert e0.characterization_workload(learning)['shots']==25*2*2*4096


def test_unknown_hardware_never_turns_global_gate_into_go():
    args=table_inputs();args[0]['hardware_schedulable']['sigma_microcell']=True
    _,report=e0.build_budget_table(*args)
    assert report['unresolved_blocks']['Hardware_Sigma_microcell']['schedulability']=='go'
    assert report['global_gate']=='conditional'


def test_mismatched_benchmark_cell_has_no_time_proxy():
    args=table_inputs();args[0]['benchmark_cell']['qubits']=4
    table,_=e0.build_budget_table(*args)
    assert table.wall_hours_proxy.isna().all()


@pytest.mark.parametrize('bad',[0,-1,1.5,True])
def test_invalid_replicates_rejected(bad):
    config=table_inputs()[0]['static_workload'];config['replicates']=bad
    with pytest.raises(ValueError):e0.primitive_workload(config)


def test_Bmax_must_equal_max_grid():
    config=table_inputs()[0]['static_workload'];config['B_max']=4096
    with pytest.raises(ValueError):e0.primitive_workload(config)


@pytest.mark.parametrize('value',[True,'true','YES','go','schedulable'])
def test_hardware_go(value): assert e0.hardware_decision(value)=='go'


@pytest.mark.parametrize('value',[False,'false','NO','no-go','unschedulable'])
def test_hardware_no_go(value): assert e0.hardware_decision(value)=='no-go'


def test_hardware_unknown_or_invalid():
    assert e0.hardware_decision(None)=='conditional'
    for value in [1,0,'maybe',[],{}]:
        with pytest.raises(ValueError):e0.hardware_decision(value)
