"""Verify the consolidated corrected evidence, or replay it into a new directory.

No hardware submission or long E2 simulation is performed. E2 reanalysis starts
from saved trajectory outcomes; original shot files have a separate manifest.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from scripts.reproduce_integration import verify_cached,prepare
from scripts.replay_consolidated import identity
from scripts.reproduce_integrated import check_receipt,sha


def checks(package):
    result={'core':verify_cached(package)}
    for stage in ('e2','fakekolkata','hardware'):
        finger,_=identity(package,stage)
        receipt=check_receipt(package,package/f'results/integration/{stage}.json',finger)
        result[stage]={'outputs_verified':len(receipt['outputs']),'fingerprint':finger}
    provenance=package/'validation/consolidated/import_provenance.json'
    if not provenance.is_file():raise FileNotFoundError('Missing consolidated input provenance')
    items=json.loads(provenance.read_text())
    for item in items:
        if sha(package/item['destination'])!=item['sha256']:raise ValueError(f"Changed imported evidence: {item['destination']}")
    result['imported_files_verified']=len(items)
    result['scope']='Corrected analysis records and code; not a new physical acquisition or publication release'
    return result


def numerical(package,destination):
    if destination.exists():raise FileExistsError('Use a new report directory to preserve existing verification records')
    destination.mkdir(parents=True)
    jobs=[
      ('verify_integrated.py',['--package',str(package),'--output',str(destination/'core.json')]),
      ('verify_a3_audit.py',['--package',str(package),'--output',str(destination/'a3.json')]),
      ('verify_a3_audit.py',['--package',str(package),'--output',str(destination/'c3.json'),'--c3-only']),
      ('verify_e2_integrated.py',['--package',str(package),'--output',str(destination/'e2.json')]),
      ('verify_consolidated_fakekolkata.py',['--package',str(package),'--report-dir',str(destination)]),
      ('verify_consolidated_hardware.py',['--package',str(package),'--report-dir',str(destination)]),
      ('verify_aux_cdr_pec.py',['--results',str(package/'evidence/cdr_pec/results'),'--output',str(destination/'cdr_pec.json')]),
      ('verify_aux_noise.py',['--results',str(package/'evidence/noise/results'),'--output',str(destination/'noise.json')]),
      ('verify_aux_controls.py',['--package',str(package/'evidence/controls'),'--output',str(destination/'controls.json')]),
      ('verify_learned_ablation.py',['--package',str(package/'evidence/learned_ablation'),'--output',str(destination/'learned_ablation.json')])]
    for script,args in jobs:
        with (destination/(f'{len(list(destination.glob("*.log"))):02d}_'+script+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,str(CODE/'scripts'/script),*args],stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Verified '+script,flush=True)
    result={'status':'complete','scope':'Independent numerical checks on saved evidence; see individual reports for their limits',
            'verifiers':{script:sha(CODE/'scripts'/script) for script,_ in jobs},
            'reports':{p.name:sha(p) for p in destination.glob('*.json')}}
    (destination/'verification_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def prepare_consolidated(package,destination):
    destination=prepare(package,destination)
    shutil.copytree(package/'evidence',destination/'evidence')
    shutil.copy2(package/'protocol.json',destination/'protocol.json')
    shutil.copy2(package/'requirements_this_run.txt',destination/'requirements_this_run.txt')
    shutil.copytree(package/'manuscript_review',destination/'manuscript_review')
    shutil.copy2(package/'validation/environment.json',destination/'validation/environment.json')
    reports=destination/'validation/consolidated';reports.mkdir(parents=True)
    for name in ('import_provenance.json','external_E2_raw_manifest.json'):
        shutil.copy2(package/'validation/consolidated'/name,reports/name)
    return destination


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group()
    group.add_argument('--numerical',type=Path,metavar='NEW_REPORT_DIR')
    group.add_argument('--new-run',type=Path,metavar='NEW_PACKAGE_DIR')
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--e2-raw',type=Path,help='Optional original E2 root to validate against the external manifest')
    a=p.parse_args();package=CODE.parent
    if a.workers<1:p.error('--workers must be positive')
    if a.new_run:
        destination=prepare_consolidated(package,a.new_run.resolve())
        for script,stages in [('reproduce_integrated.py',('confirmatory','e1','pilot','c3')),('replay_consolidated.py',('e2','fakekolkata','hardware'))]:
            for stage in stages:
                subprocess.run([sys.executable,str(destination/'code/scripts'/script),'--stage',stage,'--workers',str(a.workers)],check=True)
        subprocess.run([sys.executable,str(destination/'code/scripts/reproduce_all.py'),'--numerical',str(destination/'verification_run')],check=True)
        subprocess.run([sys.executable,str(destination/'code/scripts/plot_integrated_figures.py'),'--package',str(destination),'--output-dir',str(destination/'figures')],check=True)
        print(f'CONSOLIDATED_ANALYSIS_COMPLETE: {destination}');return
    result=checks(package)
    if a.e2_raw:
        metadata=json.loads((package/'validation/consolidated/external_E2_raw_manifest.json').read_text())
        for rel,entry in metadata['files'].items():
            if sha(a.e2_raw/rel)!=entry['sha256']:raise ValueError(f'E2 raw file mismatch: {rel}')
        result['external_E2_round_files_verified']=len(metadata['files'])
    if a.numerical:result['numerical']=numerical(package,a.numerical.resolve())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
