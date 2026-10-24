import hashlib,json,subprocess
from pathlib import Path
import pytest
from scripts import reproduce_all as runner


def fixture_package(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'verify_cached',lambda p:{'core_verified':True})
    monkeypatch.setattr(runner,'identity',lambda p,s:('fixed',{}))
    monkeypatch.setattr(runner,'check_receipt',lambda *a:{'outputs':{}})
    data=tmp_path/'evidence/controls/result.json';data.parent.mkdir(parents=True);data.write_text('{"value":1}')
    report=tmp_path/'validation/consolidated/import_provenance.json';report.parent.mkdir(parents=True)
    report.write_text(json.dumps([{'destination':data.relative_to(tmp_path).as_posix(),'sha256':hashlib.sha256(data.read_bytes()).hexdigest()}]))
    return data,report


def test_global_check_rejects_changed_auxiliary_even_when_main_caches_pass(tmp_path,monkeypatch):
    data,_=fixture_package(tmp_path,monkeypatch)
    assert runner.checks(tmp_path)['imported_files_verified']==1
    data.write_text('{"value":2}')
    with pytest.raises(ValueError,match='Changed imported evidence'):runner.checks(tmp_path)


def test_global_check_requires_auxiliary_provenance(tmp_path,monkeypatch):
    _,report=fixture_package(tmp_path,monkeypatch);report.unlink()
    with pytest.raises(FileNotFoundError,match='Missing consolidated'):runner.checks(tmp_path)


def test_numerical_reports_preserve_existing_directory(tmp_path):
    report=tmp_path/'reports';report.mkdir();record=report/'old.json';record.write_text('old')
    with pytest.raises(FileExistsError):runner.numerical(tmp_path,report)
    assert record.read_text()=='old'


def test_failed_verifier_cannot_write_global_completion(tmp_path,monkeypatch):
    def fail(*args,**kwargs):raise subprocess.CalledProcessError(1,args[0])
    monkeypatch.setattr(runner.subprocess,'run',fail)
    output=tmp_path/'reports'
    with pytest.raises(subprocess.CalledProcessError):runner.numerical(tmp_path,output)
    assert not (output/'verification_summary.json').exists()
