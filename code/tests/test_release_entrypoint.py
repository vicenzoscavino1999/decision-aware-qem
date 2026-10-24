import json,sys
import pytest
from scripts import release_pipeline as release

def setup_run(tmp_path,monkeypatch):
    root=tmp_path/'package';root.mkdir();out=tmp_path/'run'
    monkeypatch.setattr(release,'preflight',lambda *a:{'release_manifest_sha256':'fixed','environment':{'python':'test'}})
    def small_run(root,dest):
        (dest/'result.txt').write_text('checked');return {'checked':True}
    monkeypatch.setattr(release,'run_fast',small_run)
    monkeypatch.setattr(sys,'argv',['reproduce.py','--mode','fast','--output',str(out)])
    return root,out

def test_clean_resume_and_restart_preserve_previous_record(tmp_path,monkeypatch):
    root,out=setup_run(tmp_path,monkeypatch)
    release.main(root)
    assert json.loads((out/'execution.json').read_text())['execution_mode']=='clean'
    release.main(root)
    assert json.loads((out/'execution.json').read_text())['execution_mode']=='resumed'
    sys.argv.append('--restart');release.main(root)
    assert json.loads((out/'execution.json').read_text())['execution_mode']=='restarted'
    history=list((out/'history').glob('restart_*'))
    assert len(history)==1 and (history[0]/'result.txt').read_text()=='checked'

def test_unowned_directory_is_not_overwritten(tmp_path,monkeypatch):
    root,out=setup_run(tmp_path,monkeypatch);out.mkdir();(out/'notes.txt').write_text('user notes')
    with pytest.raises(FileExistsError,match='Nonempty'):release.main(root)
    assert list(out.iterdir())==[out/'notes.txt']

def test_failed_step_cannot_leave_complete_execution(tmp_path,monkeypatch):
    root,out=setup_run(tmp_path,monkeypatch)
    release.main(root)
    def fail(*args):raise RuntimeError('injected failure')
    monkeypatch.setattr(release,'run_fast',fail)
    with pytest.raises(RuntimeError):release.main(root)
    assert json.loads((out/'execution.json').read_text())['status']=='incomplete'

def test_new_environment_requires_new_run_or_explicit_restart(tmp_path,monkeypatch):
    root,out=setup_run(tmp_path,monkeypatch);release.main(root)
    previous=(out/'result.txt').read_bytes()
    monkeypatch.setattr(release,'preflight',lambda *a:{'release_manifest_sha256':'changed','environment':{'python':'test'}})
    with pytest.raises(ValueError,match='changed'):release.main(root)
    assert (out/'result.txt').read_bytes()==previous
    sys.argv.append('--restart');release.main(root)
    assert json.loads((out/'execution.json').read_text())['status']=='complete'

def test_inventory_includes_unexpected_source_but_excludes_interpreter_cache(tmp_path):
    (tmp_path/'expected.py').write_text('x=1')
    before=release.release_inventory(tmp_path)
    cache=tmp_path/'__pycache__';cache.mkdir();(cache/'expected.pyc').write_bytes(b'cache')
    assert release.release_inventory(tmp_path)==before
    (tmp_path/'unexpected.py').write_text('x=2')
    assert release.release_inventory(tmp_path)==before|{'unexpected.py'}
