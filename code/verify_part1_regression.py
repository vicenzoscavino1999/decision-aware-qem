"""Check that factoring exact ZNE keys preserves all archived failure labels."""
from pathlib import Path
import argparse,importlib.util,json,sys
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import numpy as np
from daqem.decisions import zne_failures
from revision_v19.e1_reanalysis import block_mean

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=Path(r'D:\Copia_Laptop_D\paper fisica 5\revision_v21'))
    parser.add_argument('--output',type=Path,default=ROOT.parent/'validation/archived_decisions.json')
    args=parser.parse_args();base=args.base
    spec=importlib.util.spec_from_file_location('legacy_decisions',base/'code/src/daqem/decisions.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    counts={'E1':0,'E3':0,'FakeKolkata':0};mismatches=[]
    def compare(label,instance,values,shots,coeff):
        old=legacy.zne_failures(values,0,shots,coefficients=coeff)
        new=zne_failures(values,0,shots,coefficients=coeff)
        counts[label]+=len(old)
        if not np.array_equal(old,new):mismatches.append([label,instance,shots])
    for row in json.loads((base/'results/e1/diagnostics.json').read_text()):
        instance=row['instance'];t=row['base_t']
        with np.load(base/f'inputs/reproducibility/reference_confirmatory/raw/{instance}.npz') as d:
            arr=d['primitive_objective_estimates'];budgets=d['budgets'];assert int(d['x_star'])==0
        for blocks,shots,coeff in [([(0,t)],t,None), ([(t//2,t),(2*t,4*t)],5*t//2,None),
                                  ([(0,t)],t,row['coefficients']['Decision-ZNE']),
                                  ([(0,2*t)],2*t,row['coefficients']['Decision-ZNE'])]:
            compare('E1',instance,block_mean(arr,budgets,blocks),shots,coeff)
    for i in range(1,49):
        instance=f'C{i:03}'
        with np.load(base/f'inputs/reproducibility/reference_confirmatory/raw/{instance}.npz') as d:
            arr=d['primitive_objective_estimates'];budgets=d['budgets']
        with np.load(base/f'inputs/reproducibility/reference_confirmatory/a3/{instance}.npz') as d:
            coeff=dict(zip(d['method_names'].tolist(),d['method_coefficients']))['Decision-ZNE']
        for bi,budget in enumerate(budgets):
            for c in [None,coeff]:compare('E3',instance,arr[:,:,:,bi],int(budget),c)
        row=json.loads((base/f'results/fakekolkata_fixed10/{instance}_analysis.json').read_text())
        with np.load(base/f'results/fakekolkata_fixed10/{instance}_samples.npz') as d:arr=d['primitive']
        for c in [None,row['coefficients']['Decision-ZNE']]:compare('FakeKolkata',instance,arr,170,c)
    report={'failure_labels_compared':counts,'total':sum(counts.values()),'mismatches':mismatches,
            'scope':'Preserves existing strict-failure decisions; does not claim E2 historical trajectories were fully regenerated.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));assert not mismatches

if __name__=='__main__':main()
