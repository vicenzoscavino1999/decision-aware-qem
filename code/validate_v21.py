"""Run the targeted v21 validation suite from any working directory."""
from pathlib import Path
import subprocess,sys,os
root=Path(__file__).resolve().parent
env=os.environ.copy();env['PYTHONPATH']=str(root/'src')+os.pathsep+str(root)
env['DAQEM_AUDIT_REPO']=str(root)
tests=['tests/test_gri_risk.py','tests/test_qem_methods.py','tests/test_gap_kernel.py',
       'tests/test_contrast_matrix.py','tests/test_derisk_fakebackend_rem.py',
       'tests/test_v20_regressions.py','tests/test_v20_extended.py','tests/test_v21_corrections.py','revision_v19/test_revision.py']
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',*[str(root/p) for p in tests],'-q',
    '--junitxml='+str(root.parent/'reproduced/validation_tests.xml')],env=env))
