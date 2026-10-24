import json
import pytest
from scripts.checkpoint import run_block
from scripts.release_pipeline import verify_files,sha

def test_resume_and_corruption_recompute_only_invalid_block(tmp_path):
    calls={'a':0,'b':0}
    def produce(key):
        calls[key]+=1;(tmp_path/f'{key}.txt').write_text(key);return {'key':key}
    for key in calls:run_block(tmp_path,key,'fixed',[f'{key}.txt'],lambda key=key:produce(key))
    (tmp_path/'a.txt').write_text('corrupt')
    for key in calls:run_block(tmp_path,key,'fixed',[f'{key}.txt'],lambda key=key:produce(key))
    assert calls=={'a':2,'b':1}

def test_failure_never_certifies_partial_files(tmp_path):
    def crash():
        (tmp_path/'one').write_text('partial');raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError):run_block(tmp_path,'case','fixed',['one','two'],crash)
    receipt=json.loads((tmp_path/'results/checkpoints/case.json').read_text())
    assert receipt['status']=='incomplete' and not receipt['outputs']

def test_changed_inputs_require_new_directory(tmp_path):
    def produce():(tmp_path/'one').write_text('one')
    run_block(tmp_path,'case','first',['one'],produce)
    with pytest.raises(ValueError,match='inputs changed'):run_block(tmp_path,'case','second',['one'],produce)

def test_missing_output_never_commits(tmp_path):
    with pytest.raises(ValueError,match='omitted'):run_block(tmp_path,'case','fixed',['missing'],lambda:None)

def test_manifest_rejects_escape_empty_and_tampering(tmp_path):
    path=tmp_path/'data';path.write_text('original');records={'data':sha(path)}
    verify_files(tmp_path,records)
    path.write_text('modified')
    with pytest.raises(ValueError,match='changed'):verify_files(tmp_path,records)
    with pytest.raises(ValueError,match='Unsafe'):verify_files(tmp_path,{'../outside':'x'})
    with pytest.raises(ValueError,match='Empty'):verify_files(tmp_path,{})
