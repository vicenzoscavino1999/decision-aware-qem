import hashlib,json,sys,zipfile
from pathlib import Path
import pytest
from scripts import release_pipeline as release
from scripts.release_supplements import extract_verified

def archive(path,entries):
    with zipfile.ZipFile(path,'w') as z:
        manifest={name:hashlib.sha256(content).hexdigest() for name,content in entries.items()}
        for name,content in entries.items():z.writestr('study/'+name,content)
        z.writestr('study/manifest_sha256.json',json.dumps(manifest))

def test_rejects_traversal_before_writing(tmp_path):
    src=tmp_path/'bad.zip';archive(src,{'../escaped.txt':b'no'})
    dest=tmp_path/'copy'
    with pytest.raises(ValueError,match='Unsafe'):extract_verified(src,dest,'study/')
    assert not dest.exists() and not (tmp_path/'escaped.txt').exists()

def test_extraction_checks_omitted_reports_too(tmp_path):
    src=tmp_path/'bad.zip'
    with zipfile.ZipFile(src,'w') as z:
        z.writestr('study/data.txt','good');z.writestr('study/verification.json','tampered')
        z.writestr('study/manifest_sha256.json',json.dumps({'data.txt':hashlib.sha256(b'good').hexdigest(),
            'verification.json':hashlib.sha256(b'original').hexdigest()}))
    with pytest.raises(ValueError,match='checksum'):extract_verified(src,tmp_path/'copy','study/',omit={'verification.json'})
    assert not (tmp_path/'copy').exists()

def test_new_copy_omits_only_requested_reports(tmp_path):
    src=tmp_path/'good.zip';archive(src,{'data.txt':b'input','verification.json':b'old'})
    dest=tmp_path/'copy';extract_verified(src,dest,'study/',omit={'verification.json'})
    assert (dest/'data.txt').read_bytes()==b'input' and not (dest/'verification.json').exists()
    with pytest.raises(FileExistsError):extract_verified(src,dest,'study/')

def test_nested_historical_manifest_is_part_of_release_inventory(tmp_path):
    history=tmp_path/'history';history.mkdir()
    (history/'release_manifest.json').write_text('{}')
    (tmp_path/'release_manifest.json').write_text('{}')
    assert release.release_inventory(tmp_path)=={'history/release_manifest.json'}

def test_supplement_failure_prevents_complete_all_receipt(tmp_path,monkeypatch):
    import scripts.release_supplements as supplements
    root=tmp_path/'package';root.mkdir();out=tmp_path/'run'
    def preflight(*args):
        out.mkdir();return {'release_manifest_sha256':'fixed','environment':{'python':'test'}}
    monkeypatch.setattr(release,'preflight',preflight)
    monkeypatch.setattr(release,'run_fast',lambda *a:{'complete':True})
    monkeypatch.setattr(release,'run_analysis',lambda *a:{'complete':True})
    def fail(*args):raise ValueError('supplement discrepancy')
    monkeypatch.setattr(supplements,'run_supplements',fail)
    monkeypatch.setattr(sys,'argv',['reproduce.py','--mode','all','--output',str(out)])
    with pytest.raises(ValueError,match='supplement discrepancy'):release.main(root)
    receipt=json.loads((out/'execution.json').read_text())
    assert receipt['status']=='incomplete' and 'supplements' not in receipt['steps']
