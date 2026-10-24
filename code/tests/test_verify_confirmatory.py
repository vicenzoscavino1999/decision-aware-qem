"""Corrected archive checks replace historical assertions and their skips."""
import json,shutil
from pathlib import Path
import pandas as pd
import pytest
from scripts.verify_e2_integrated import verify
from scripts.compare_release import equivalent
PACKAGE=Path(__file__).resolve().parents[2]

def test_corrected_confirmatory_archive_quantities():
    result=verify(PACKAGE)
    assert result['outcomes_verified']==15360
    assert result['both_cross_instances']==13
    row=next(r for r in result['series'] if r['selector']=='MSE' and r['budget']==4096)
    assert row['successful_trajectories']==971
    e3=json.loads((PACKAGE/'results/confirmatory/e3_summary.json').read_text())
    assert e3['active_pairs']==502 and e3['directionally_sensitive_pass']==487 and e3['fail']==15

def test_corrected_verifier_rejects_changed_cost(tmp_path):
    shutil.copytree(PACKAGE/'evidence/e2',tmp_path/'evidence/e2')
    shutil.copytree(PACKAGE/'results/e2',tmp_path/'results/e2')
    file=tmp_path/'results/e2/e2_full_ledger.csv'
    frame=pd.read_csv(file);frame.loc[0,'total_shots_per_trajectory']+=1;frame.to_csv(file,index=False)
    with pytest.raises(AssertionError):verify(tmp_path)

def test_decision_flip_cannot_be_hidden_by_numeric_tolerance():
    with pytest.raises(ValueError,match='Exact value changed'):
        equivalent({'success':True},{'success':False},'decision',{'max_abs_difference':0.})
