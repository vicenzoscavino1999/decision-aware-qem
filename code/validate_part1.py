"""Validate this correction and the 94 previously checked regressions."""
from pathlib import Path
import os,subprocess,sys
root=Path(__file__).resolve().parent
env=os.environ.copy();env['PYTHONPATH']=str(root/'src')+os.pathsep+str(root)
env['DAQEM_AUDIT_REPO']=str(root)
tests=['test_gri_risk','test_qem_methods','test_gap_kernel','test_contrast_matrix',
       'test_derisk_fakebackend_rem','test_v20_regressions','test_v20_extended','test_v21_corrections',
       'test_dynamic_optimizer','test_e2_confirmatory_b44','test_budget_ledger',
       'test_selector_logic','test_cdr','test_pec','test_cdev_learning','test_part1_exact_dynamic']
paths=[str(root/'tests'/f'{name}.py') for name in tests]+[str(root/'revision_v19/test_revision.py')]
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',*paths,'-q',
    '--junitxml='+str(root.parent/'validation/tests.xml')],env=env))
