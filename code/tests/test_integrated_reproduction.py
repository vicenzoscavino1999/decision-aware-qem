from pathlib import Path
import json,numpy as np,pytest
from experiments import a3_pullback_frontier as a3,e3_bstar_prediction as e3
from scripts.reproduce_integrated import check_receipt,sha,dump
from scripts.replay_c3_audit import propagate_current_reference


def test_confirmatory_reader_accepts_generation_profile_and_validates_raw_profile(tmp_path,monkeypatch):
    cfg=a3.load_config('confirmatory_full')
    cfg['gate0_config'].update(candidate_count=4,budget_grid=[8,16],B_max=16)
    def moments(**kwargs):
        means=np.tile(np.array([-1.,-.9,-.8,-.7]),(3,1));var=np.ones_like(means)
        a3._write_deterministic_npz(kwargs['evidence_path'],means=means,variances=var)
        return means,var,means[0],np.asarray(0)
    monkeypatch.setattr(a3,'_primitive_objective_moments',moments)
    frozen=a3.build_frozen_prediction_for_cell(instance_id='C001',output_root=tmp_path,config=cfg)
    metadata=dict(instance_id='C001',profile='confirmatory_full',candidate_count=4,budget_grid=[16,8])
    raw=tmp_path/'confirmatory/raw/C001.npz'
    arrays=dict(metadata_json=np.array(json.dumps(metadata)),ideal_values=np.array([-1.,-.9,-.8,-.7]),x_star=np.array(0),
        budgets=np.array([8,16]),zne_lambdas=np.array([1.,2.,3.]),primitive_objective_estimates=np.zeros((2,3,4,2)))
    a3._write_deterministic_npz(raw,**arrays)
    cfg['gate0_config']['profile']='confirmatory_full'
    frame=a3.analyze_cell_from_frozen_prediction(instance_id='C001',frozen_path=frozen,frozen_hash=a3._sha256(frozen),output_root=tmp_path,config=cfg)
    assert len(frame)==6
    metadata['profile']='full';arrays['metadata_json']=np.array(json.dumps(metadata));a3._write_deterministic_npz(raw,**arrays)
    with pytest.raises(ValueError,match='raw profile mismatch'):
        a3.analyze_cell_from_frozen_prediction(instance_id='C001',frozen_path=frozen,frozen_hash=a3._sha256(frozen),output_root=tmp_path,config=cfg)


def test_checkpoint_cannot_certify_changed_outputs_or_sources(tmp_path):
    p=tmp_path/'data.txt';p.write_text('result');receipt=tmp_path/'receipt.json'
    dump(receipt,dict(status='complete',fingerprint='first',outputs={'data.txt':sha(p)}))
    assert check_receipt(tmp_path,receipt,'first')['status']=='complete'
    with pytest.raises(ValueError,match='changed'):check_receipt(tmp_path,receipt,'second')
    p.write_text('tampered')
    with pytest.raises(ValueError,match='Output changed'):check_receipt(tmp_path,receipt,'first')


def test_incomplete_checkpoint_is_not_a_success(tmp_path):
    p=tmp_path/'receipt.json';dump(p,dict(status='running',fingerprint='x',outputs={}))
    with pytest.raises(ValueError,match='incomplete'):check_receipt(tmp_path,p,'x')


def test_learned_covariance_uses_current_maps_not_archived_covariance(tmp_path):
    primitive=tmp_path/'inputs/learned_primitives/P001.npz';old=tmp_path/'inputs/learned_evidence/P001_propagation.npz'
    frozen=tmp_path/'results/pilot/a3_frozen_prediction/P001.npz'
    for p in (primitive,old,frozen):p.parent.mkdir(parents=True,exist_ok=True)
    ideal=np.array([0.,.1,.2]);variance=np.ones((3,3))
    np.savez(primitive,x_star=0,ideal_values=ideal,variances=variance)
    np.savez(old,cdev_learned=variance.ravel(),sigma_learned=np.full((1,2,2,2),99.))
    gap_map=np.array([[-1.,1.,0.,0.,0.,0.,0.,0.,0.],[-1.,0.,1.,0.,0.,0.,0.,0.,0.]])
    np.savez(frozen,x_star=0,ideal_values=ideal,budgets=[5,10],gap_maps=gap_map[None])
    result=propagate_current_reference(tmp_path,'P001')
    np.testing.assert_allclose(result[0,0],[[.4,.2],[.2,.4]],rtol=0,atol=1e-12)
    np.testing.assert_allclose(result[0,1],[[.2,.1],[.1,.2]],rtol=0,atol=1e-12)
    with np.load(tmp_path/'results/pilot/cdev_evidence/P001_propagation.npz') as current:
        assert json.loads(str(current['metadata_json']))['reference_prediction_sha256']==sha(frozen)
    np.savez(primitive,x_star=0,ideal_values=ideal,variances=variance*2)
    with pytest.raises(ValueError,match='variances differ'):propagate_current_reference(tmp_path,'P001')
