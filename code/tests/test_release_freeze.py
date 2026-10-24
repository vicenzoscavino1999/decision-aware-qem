import json
import pytest
from scripts import verify_freeze as verifier
from scripts.build_freeze_manifest import freeze_hash_from_checksums

def test_freeze_rejects_changed_summary_hash(tmp_path,monkeypatch,capsys):
    data=json.loads(verifier.FREEZE_MANIFEST.read_text());data['freeze_hash']='sha256:WRONG'
    file=tmp_path/'freeze.json';file.write_text(json.dumps(data));monkeypatch.setattr(verifier,'FREEZE_MANIFEST',file)
    assert verifier.main()==1
    assert 'summary hash' in capsys.readouterr().out

def test_freeze_rejects_omitted_file_even_if_summary_is_rehashed(tmp_path,monkeypatch,capsys):
    data=json.loads(verifier.FREEZE_MANIFEST.read_text());data['checksums'].pop(next(iter(data['checksums'])))
    data['freeze_hash']=freeze_hash_from_checksums(data['checksums'])
    file=tmp_path/'freeze.json';file.write_text(json.dumps(data));monkeypatch.setattr(verifier,'FREEZE_MANIFEST',file)
    assert verifier.main()==1
    assert 'inventory differs' in capsys.readouterr().out

@pytest.mark.parametrize('field',['base_images','checksums'])
def test_freeze_rejects_runtime_contract_change(field,tmp_path,monkeypatch,capsys):
    data=json.loads(verifier.FREEZE_MANIFEST.read_text())
    data['runtime_contract'][field]=[] if field=='base_images' else {}
    file=tmp_path/'freeze.json';file.write_text(json.dumps(data));monkeypatch.setattr(verifier,'FREEZE_MANIFEST',file)
    assert verifier.main()==1
    assert 'mismatch' in capsys.readouterr().out
