"""Independent numerical checks and old/new comparisons for integrated E1/E3/E0."""
from __future__ import annotations
import argparse,hashlib,json,math,sys
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
from scripts.verify_generation import structured_risk
from scripts.verify_a3_audit import lw_cov


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def compare_table(new,old,keys):
    new=new.sort_values(keys).reset_index(drop=True);old=old.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(new[keys],old[keys],check_dtype=False)
    return {c:int((new[c].fillna('NA')!=old[c].fillna('NA')).sum()) for c in new.columns.intersection(old.columns) if c not in keys}


def verify_e0(package):
    import jsonschema
    p=package/'results/pilot'
    d=json.loads((p/'executability_diagnostic.json').read_text())
    schema=json.loads((CODE/'reproducibility/config/executability_diagnostic.schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(d)
    rows=pd.read_csv(p/'executability_diagnostic.csv').astype(object)
    rows=rows.where(pd.notna(rows),None).to_dict('records')
    assert len(rows)==len(d['rows'])
    for csv_row,json_row in zip(rows,d['rows']):
        assert set(csv_row)==set(json_row)
        for key,value in json_row.items():
            # The archived JSON rows use pandas' ten-decimal serialization.
            if isinstance(value,float):assert math.isclose(csv_row[key],value,rel_tol=0,abs_tol=5.1e-11)
            else:assert csv_row[key]==value,(key,csv_row[key],value)
    assert len({r['block'] for r in rows})==5
    w=d['workloads']
    for name in ('E1_static','E2_dynamic','Pilot_shared'):
        item=w[name]
        circuits=math.prod(item[k] for k in ('instances','replicates_per_instance','rounds','candidates','scales'))
        assert item['circuits']==circuits and item['shots']==circuits*item['B_max']
    item=w['Uniform_Cdev'];circuits=math.prod(item[k] for k in ('basis_labels','depths','identical_repeats'))
    assert item['circuits']==circuits and item['shots']==circuits*item['shots_per_circuit']
    for row in rows:
        if row['block']=='E3_pullback':assert row['estimated_shots']==row['acquisition_circuits']==0
        else:
            item=w[row['block']];assert row['estimated_shots']==item['shots'] and row['acquisition_circuits']==item['circuits']
        if row['block'] in ('E1_static','E2_dynamic','Pilot_shared'):
            expected=row['acquisition_circuits']*d['batch_timing']['amortized_seconds_per_circuit']/3600
            assert abs(row['wall_hours_proxy']-expected)<1e-12
        else:assert row['wall_hours_proxy'] is None
    return dict(schema_version=2,rows_checked=5,benchmark='reused from generation/executability correction, no new timing measurement')


def verify_e1(package):
    new=package/'results/e1';old=package/'inputs/previous_e1'
    details={}
    for name,keys in [('outcomes.csv',['instance','base_t','comparison','policy','replicate_id']),
                      ('summary.csv',['base_t','comparison','kind','policy','reference'])]:
        a=pd.read_csv(new/name);b=pd.read_csv(old/name)
        details[name]=dict(rows=len(a),changes=compare_table(a,b,keys))
    details['budget_ledger_identical']=sha(new/'budget_ledger.csv')==sha(old/'budget_ledger.csv')
    return details


def verify_e3(package):
    root=package/'results/confirmatory'
    table=pd.read_csv(root/'e3_independent_mean_and_failure.csv')
    frontier=pd.read_csv(root/'e3_pullback_frontier.csv')
    errors={k:0. for k in ('primitive_mean','primitive_variance','covariance','risk','derivative','projected_error')}
    differences={k:0. for k in ('primitive_mean_unit','primitive_variance_unit','method_coefficients','risks_pred','gradients')}
    decisions=0;directions=0;changes=[];probs=0;unmasked=0
    def check(key,a,b,tol):
        error=float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
        errors[key]=max(errors[key],error)
        assert error<=tol,(key,error,tol)
    for instance in (f'C{i:03}' for i in range(1,49)):
        with np.load(root/f'a3_frozen_prediction/{instance}.npz') as d:f={k:d[k] for k in d.files}
        with np.load(package/f'inputs/reproducibility/reference_confirmatory/a3/{instance}.npz') as d:old={k:d[k] for k in d.files}
        with np.load(root/f'raw/{instance}.npz') as d:raw={k:d[k] for k in d.files}
        meta=json.loads(str(f['metadata_json']));path=package/'results'/meta['primitive_evidence_path']
        assert meta['primitive_evidence_hash'].lower()=='sha256:'+sha(path)
        assert meta['prospective_preregistration'] is False
        with np.load(path) as e:p=e['probabilities'];values=e['values_by_state']
        assert p.shape==(3,25,1024) and np.all(p>=0)
        np.testing.assert_allclose(p.sum(axis=-1),1,atol=3e-15,rtol=0)
        means=np.array([[math.fsum(float(w)*float(v) for w,v in zip(a,values)) for a in scale] for scale in p])
        variances=np.array([[math.fsum(float(w)*(float(v)-float(m))**2 for w,v in zip(a,values)) for a,m in zip(scale,mm)] for scale,mm in zip(p,means)])
        check('primitive_mean',f['primitive_mean_unit'],means,1e-13);check('primitive_variance',f['primitive_variance_unit'],variances,1e-13);probs+=75
        for key in differences:differences[key]=max(differences[key],float(np.max(abs(f[key]-old[key]))))
        x=int(f['x_star']);comp=[i for i in range(25) if i!=x];names=list(f['method_names'])
        ordered=sorted(range(40),key=lambda r:hashlib.sha256(f'v19-e1-independent-2026-10-22|{instance}|{r}'.encode()).hexdigest())
        test=ordered[20:]
        for bi,budget in enumerate(f['budgets']):
            rbi=list(raw['budgets']).index(budget);primitive=raw['primitive_objective_estimates'][...,rbi]
            sums=np.rint(primitive*budget).astype(np.int64)
            np.testing.assert_allclose(sums,primitive*budget,atol=1e-9,rtol=0)
            flags={};covariances=[]
            for mi,name in enumerate(names):
                c=f['method_coefficients'][mi]
                marginal=(c*c)@variances/budget
                sigma=np.diag(marginal[comp])+marginal[x]
                check('covariance',f['sigma_pred'][mi,bi],sigma,3e-12)
                check('risk',f['risks_pred'][mi,bi],structured_risk(f['mu'],sigma),2e-6)
                grad=f['gradients'][mi,bi]
                for direction in (np.diag(.05*marginal[comp]*np.cos(np.arange(24))),np.full((24,24),.03*marginal[x])):
                    h=.001
                    derivative=(structured_risk(f['mu'],sigma+h*direction)-structured_risk(f['mu'],sigma-h*direction))/(2*h)
                    check('derivative',derivative,np.sum(grad*direction),2e-9);directions+=1
                unmasked+=int(np.any(abs(grad[~old['active_masks'][mi,bi]])>1e-12))
                observed=[]
                for coeff in (old['method_coefficients'][mi],c):
                    if name=='Raw':weights=[Fraction(1),Fraction(0),Fraction(0)]
                    elif name=='Accuracy-ZNE':weights=[Fraction(4,3),Fraction(1,3),Fraction(-2,3)]
                    else:
                        t=Fraction(float(coeff[2]));weights=[2+t,-1-2*t,t]
                    observed.append(np.array([any(sum(weights[k]*int(r[k,j]-r[k,x]) for k in range(3))<=0 for j in comp) for r in sums]))
                flags[name]=observed[1];decisions+=len(observed[1])
                changed=int(np.count_nonzero(observed[0]!=observed[1]))
                if changed:changes.append(dict(instance=instance,budget=int(budget),method=name,changed=changed))
                est=np.einsum('s,rsc->rc',c,primitive);covariances.append(lw_cov(est[:,comp]-est[:,[x]]))
            for pi,pair in enumerate(f['pair_names']):
                left,right=str(pair).split('_vs_');li,ri=names.index(left),names.index(right)
                row=frontier[(frontier.problem_cell==instance)&(frontier.budget==budget)&(frontier.pair_id==pair)].iloc[0]
                delta=f['risks_pred'][li,bi]-f['risks_pred'][ri,bi]
                assert abs(delta-f['delta_pred'][pi,bi])<1e-15
                assert row.active_pair==bool(abs(delta)>=.005)
                projection=abs(np.trace(f['gradients'][li,bi].T@(covariances[li]-f['sigma_pred'][li,bi]))-np.trace(f['gradients'][ri,bi].T@(covariances[ri]-f['sigma_pred'][ri,bi])))
                check('projected_error',projection,row.delta_rank_projected,1e-11)
                tau=.5*abs(delta);denominator=max(tau,1e-12)
                assert math.isclose(row.tau_flip_projected,tau,abs_tol=1e-15,rel_tol=1e-12)
                # Check the stored division exactly, then the independent physical
                # numerator. Dividing roundoff by an inactive 1e-12 floor is ill-conditioned.
                assert math.isclose(row.projected_error_over_tolerance,row.delta_rank_projected/denominator,abs_tol=1e-12,rel_tol=2e-12)
                assert math.isclose(row.projected_error_over_tolerance*denominator,projection,abs_tol=1e-11,rel_tol=2e-10)
                norm=np.linalg.norm(f['gradients'][li,bi],ord='fro')+np.linalg.norm(f['gradients'][ri,bi],ord='fro')
                error=np.linalg.norm(covariances[li]-f['sigma_pred'][li,bi],ord='fro')+np.linalg.norm(covariances[ri]-f['sigma_pred'][ri,bi],ord='fro')
                frob_denominator=max(denominator/(norm+1e-12),1e-12)
                assert math.isclose(row.frobenius_error_over_tolerance*frob_denominator,error,abs_tol=1e-10,rel_tol=2e-10)
                if row.active_pair:
                    obs=table[(table.instance==instance)&(table.budget==budget)&(table.pair==pair)].iloc[0]
                    assert obs.left_test_failure==flags[left][test].mean()
                    assert obs.right_test_failure==flags[right][test].mean()
        print(f'verified {instance}',flush=True)
    oldroot=package/'inputs/previous_e3'
    comparison_changes=compare_table(table,pd.read_csv(oldroot/'e3_independent_mean_and_failure.csv'),['instance','budget','pair'])
    frontier_changes=compare_table(frontier,pd.read_csv(oldroot/'e3_pullback_frontier.csv'),['problem_cell','budget','pair_id'])
    return dict(instances=48,primitive_distributions=probs,covariances=48*3*6,strict_decisions=decisions,
                derivative_directions=directions,max_errors=errors,difference_from_archived_prediction=differences,
                decision_changes=changes,gradients_with_entries_outside_old_mask=unmasked,
                comparison_changes=comparison_changes,frontier_changes=frontier_changes)


def main():
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=dict(e0=verify_e0(args.package),e1=verify_e1(args.package),e3=verify_e3(args.package))
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
