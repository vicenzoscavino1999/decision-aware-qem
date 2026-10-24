"""Four contract regressions exposed by the v19 audit; all must pass in v20.

These assert mathematically required behavior, not the presence of a bug.
Set DAQEM_AUDIT_REPO to audit a different repository path.
No hardware jobs, quantum simulation, or changes to the repository are performed.
"""
from pathlib import Path
import ast
import importlib.util
import os
import sys

import numpy as np
from scipy.stats import norm

REPO = Path(os.environ.get('DAQEM_AUDIT_REPO', str(Path(__file__).resolve().parents[1])))
sys.path.insert(0, str(REPO/'src'))
from daqem.risk import gri_risk
from daqem.gap_kernel import nearest_psd
from daqem.qem_methods import decision_optimal_zne_coeffs, richardson_constraints


def test_gaussian_tail_must_remain_positive():
    actual = gri_risk([9.], [[1.]])
    expected = norm.sf(9.)
    assert np.isclose(actual, expected, rtol=1e-10, atol=0), (actual, expected)


def test_socp_must_not_depend_on_energy_units():
    A,rhs=richardson_constraints([1.,2.,3.],1)
    Q=np.diag([1.,0.,0.])
    c=decision_optimal_zne_coeffs([Q],[1.],A,rhs)
    scaled=decision_optimal_zne_coeffs([Q*1e-12],[1e-6],A,rhs)
    assert np.allclose(c,scaled,atol=1e-5,rtol=1e-5), (c,scaled)


def test_v19_risk_must_not_depend_on_energy_units():
    spec=importlib.util.spec_from_file_location('v19_audited',REPO/'revision_v19/e1_reanalysis.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values=np.column_stack([np.zeros(10),np.arange(1.,11.),[1.,3.,2.,5.,4.,7.,6.,9.,8.,10.]])
    actual=module.risk_score(values,0,42)
    scaled=module.risk_score(values*1e-9,0,42)
    assert np.isclose(actual,scaled,rtol=1e-6,atol=1e-9), (actual,scaled)


def test_hardware_gradient_matches_exact_directional_derivative():
    path=REPO/'experiments/hardware_sigma/run_main.py'
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'gri_score','gri_sigma_gradient'}]
    assert len(functions)==2
    module=ast.Module(body=functions,type_ignores=[])
    ns={'np':np,'nearest_psd':nearest_psd,'gri_risk':gri_risk}
    exec(compile(module,str(path),'exec'),ns)
    rho=.2
    sigma=np.array([[1.,rho],[rho,1.]])
    gradient=ns['gri_sigma_gradient'](np.zeros(2),sigma)
    direction=np.array([[0.,1.],[1.,0.]])
    actual=np.sum(gradient*direction)
    expected=-1/(2*np.pi*np.sqrt(1-rho**2))
    assert np.isclose(actual,expected,rtol=1e-5,atol=1e-8), (actual,expected)
