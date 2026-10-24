"""Verify this integration, or reproduce its four stages in a NEW directory.

Scope: E1, regenerated E3, pilot A3/C3 and the archived E0 diagnostic.
This is not a full paper/repository release command.
"""
from __future__ import annotations
import argparse,importlib.metadata,json,shutil,subprocess,sys
from pathlib import Path
CODE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(CODE/'src'),str(CODE)]
from scripts.reproduce_integrated import fingerprint,check_receipt,sha
from scripts.verify_integrated import verify_e0


def verify_cached(package):
    result={}
    environment=package/'validation/environment.json'
    if environment.exists():
        expected_environment=json.loads(environment.read_text(encoding='utf-8'))
        for name,version in expected_environment['packages'].items():
            if importlib.metadata.version(name)!=version:raise ValueError(f'Environment changed: {name}')
        result['environment_packages_verified']=len(expected_environment['packages'])
    manifest=package/'SHA256SUMS.json'
    if manifest.exists():
        expected=json.loads(manifest.read_text(encoding='utf-8'))
        for rel,digest in expected.items():
            path=package/rel
            if not path.is_file() or sha(path)!=digest:raise ValueError(f'Package file missing or changed: {rel}')
        result['package_files_verified']=len(expected)
    for stage in ('confirmatory','e1','pilot','c3'):
        current,_=fingerprint(package,stage)
        receipt=check_receipt(package,package/f'results/integration/{stage}.json',current)
        result[stage]={'fingerprint':current,'outputs_verified':len(receipt['outputs'])}
    result['E0']=verify_e0(package)
    return result


def prepare(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.is_relative_to(source):raise ValueError('Destination must be outside the source package')
    if destination.exists():raise FileExistsError('Use a new destination; existing files are never overwritten')
    destination.mkdir(parents=True)
    ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc')
    shutil.copytree(source/'code',destination/'code',ignore=ignore)
    shutil.copytree(source/'inputs',destination/'inputs',ignore=ignore)
    shutil.copytree(source/'inputs/reproducibility/reference_confirmatory/raw',destination/'results/confirmatory/raw')
    pilot=destination/'results/pilot';pilot.mkdir(parents=True)
    for name in ('raw','a3_frozen_prediction','a3_primitive_evidence'):
        shutil.copytree(source/f'results/pilot/{name}',pilot/name)
    for name in ('pullback_frontier.csv','executability_diagnostic.json','executability_diagnostic.csv','executability_diagnostic.md'):
        shutil.copy2(source/f'results/pilot/{name}',pilot/name)
    (destination/'validation').mkdir()
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-run',type=Path,help='New destination; run all four stages using archived shot data')
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args();package=CODE.parent
    if args.workers<1:parser.error('--workers must be positive')
    if args.new_run is None:
        print(json.dumps(verify_cached(package),indent=2));return
    destination=prepare(package,args.new_run.resolve())
    runner=destination/'code/scripts/reproduce_integrated.py'
    for stage in ('confirmatory','e1','pilot','c3'):
        subprocess.run([sys.executable,str(runner),'--stage',stage,'--workers',str(args.workers)],check=True)
    for script,output,extra in [
        ('verify_integrated.py','independent_integration.json',[]),
        ('verify_a3_audit.py','independent_a3.json',[]),
        ('verify_a3_audit.py','independent_c3.json',['--c3-only'])]:
        subprocess.run([sys.executable,str(destination/'code/scripts'/script),'--package',str(destination),
                        '--output',str(destination/'validation'/output),*extra],check=True)
    subprocess.run([sys.executable,str(destination/'code/scripts/reproduce_integration.py')],check=True)
    print(f'INTEGRATION_COMPLETE: {destination}',flush=True)


if __name__=='__main__':main()
