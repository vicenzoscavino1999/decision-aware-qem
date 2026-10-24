"""Release-level preflight, full tests, three-run determinism and analysis replay.

All generated files live outside the release. An execution receipt is committed
only after a step succeeds; partial steps are never accepted as completed runs.
"""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,os,platform,shutil,subprocess,sys,time
from pathlib import Path
from reproducibility.run_all import RunLock


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):digest.update(part)
    return digest.hexdigest()


def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def safe_member(root,name):
    relative=Path(name)
    path=(root/relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe manifest path: {name}')
    return path


def verify_files(root,records):
    if not isinstance(records,dict) or not records:raise ValueError('Empty or invalid file manifest')
    for name,digest in records.items():
        file=safe_member(root,name)
        if not file.is_file() or sha(file)!=digest:raise ValueError(f'File missing or changed: {name}')


def release_inventory(root):
    return {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
            and p!=root/'release_manifest.json' and p.suffix!='.pyc'
            and not {'.git','__pycache__','.pytest_cache'}.intersection(p.relative_to(root).parts)}


def environment():
    return dict(python=platform.python_version(),platform=platform.platform(),
        packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        rng={'root_seed':260616,'bit_generator':'PCG64DXSM'})


def preflight(root,output):
    if output.resolve().is_relative_to(root.resolve()):raise ValueError('Output must be outside the release')
    if sys.flags.optimize:raise ValueError('Python -O disables scientific assertions and is unsupported')
    manifest=json.loads((root/'release_manifest.json').read_text())
    if release_inventory(root)!=set(manifest['files']):raise ValueError('Release file inventory changed')
    verify_files(root,manifest['files'])
    pap=root/'code/EXPERIMENTAL_PLAN_v13_PRXQ.md'
    if sha(pap)!=manifest['pap_sha256']:raise ValueError('PAP anchor changed')
    if (root/'code/PAP_HASH.txt').read_text().strip().lower()!='sha256:'+sha(pap):raise ValueError('PAP_HASH mismatch')
    env=environment()
    if env['python']!='3.12.10':raise ValueError('Use Python 3.12.10')
    lock=root/('requirements-lock.linux.txt' if sys.platform=='linux' else 'requirements_this_run.txt')
    for line in lock.read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        name,version=line.split()[0].split('==')
        if importlib.metadata.version(name)!=version:raise ValueError(f'Dependency mismatch: {name}')
    output.mkdir(parents=True,exist_ok=True)
    probe=output/'.write_probe';probe.write_bytes(b'ok');probe.unlink()
    return dict(environment=env,release_manifest_sha256=sha(root/'release_manifest.json'),
                pap_sha256=sha(pap),free_disk_bytes=shutil.disk_usage(output).free,
                canonical_platform=sys.platform=='linux' and platform.machine()=='x86_64')


def execute(command,cwd,log):
    import psutil
    log.parent.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();peak=0;process_count=0
    with log.open('w',encoding='utf-8') as handle:
        process=subprocess.Popen(command,cwd=cwd,stdout=handle,stderr=subprocess.STDOUT)
        while process.poll() is None:
            try:
                parent=psutil.Process(process.pid);members=[parent]+parent.children(recursive=True)
                memory=0
                for item in members:
                    try:memory+=item.memory_info().rss
                    except psutil.Error:pass
                peak=max(peak,memory);process_count=max(process_count,len(members))
            except psutil.Error:pass
            try:process.wait(timeout=.25)
            except subprocess.TimeoutExpired:pass
    dump(log.with_suffix('.metrics.json'),dict(seconds=time.perf_counter()-started,peak_sum_rss_bytes=peak,max_processes=process_count,exit_code=process.returncode,
        measurement='sampled every 250 ms; sum of process RSS may count shared pages more than once'))
    if process.returncode:
        raise RuntimeError(f'Command failed ({process.returncode}); see {log}:\n{log.read_text(errors="replace")[-4000:]}')


def registry(path,pap):
    manifest=json.loads((path/'manifest.json').read_text())
    names=set(manifest['outputs'])|{'manifest.json',manifest['checkpoint_path']}
    dump(path/'reference_manifest.json',{'pap_hash':pap,'checksums':{name:'sha256:'+sha(path/name).upper() for name in sorted(names)}})


def run_fast(root,output):
    code=root/'code';runs=[]
    for label in ('a','b','c'):
        dest=output/f'level1_{label}'
        execute([sys.executable,str(code/'reproducibility/run_all.py'),'--mode','fast','--level','1','--output',str(dest)],code,output/f'level1_{label}.log')
        runs.append(dest)
    first=json.loads((runs[0]/'manifest.json').read_text())
    for later in runs[1:]:
        current=json.loads((later/'manifest.json').read_text())
        if set(first['outputs'])!=set(current['outputs']):raise ValueError('Determinism: output set changed')
        for name in first['outputs']:
            if (runs[0]/name).read_bytes()!=(later/name).read_bytes():raise ValueError(f'Determinism: {name} differs')
    registry(runs[0],first['pap_hash'])
    for i,run in enumerate(runs):
        execute([sys.executable,str(code/'reproducibility/verify.py'),'--reference',str(runs[0]),'--generated',str(run),'--exact-numeric'],code,output/f'verify_level1_{i}.log')
    execute([sys.executable,str(code/'reproducibility/verify.py'),'--reference',str(code/'reproducibility/reference_level1'),'--generated',str(runs[0]),'--exact-numeric'],code,output/'verify_shipped_reference.log')
    execute([sys.executable,'-m','pytest',str(code/'tests'),'-q','-o',f'cache_dir={output/"pytest_cache"}',f'--junitxml={output/"tests.xml"}'],code,output/'pytest.log')
    execute([sys.executable,str(code/'scripts/verify_freeze.py')],code,output/'freeze.log')
    from scripts.verify_manuscript import verify
    dump(output/'manuscript.json',verify(root))
    return dict(level1_runs=3,canonical_outputs=len(first['outputs']),exact_comparisons=2,full_test_suite=True)


def prepare(root,destination):
    from scripts.reproduce_all import prepare_consolidated
    temporary=destination.with_name(destination.name+'.preparing')
    if temporary.exists():temporary.rename(temporary.with_name(temporary.name+f'.incomplete.{time.time_ns()}'))
    prepare_consolidated(root,temporary)
    dump(temporary/'validation/environment.json',environment())
    # Manuscript verification needs the complete source and existing PDF.
    shutil.copytree(root/'manuscript',temporary/'manuscript')
    for name in ('decision_residual_fields_theory_v45.pdf',):shutil.copy2(root/name,temporary/name)
    temporary.rename(destination)
    return destination


def run_analysis(root,output,workers):
    destination=output/'analysis'
    if not destination.exists():prepare(root,destination)
    code=destination/'code'
    for script,stages in [('reproduce_integrated.py',('confirmatory','e1','pilot','c3')),('replay_consolidated.py',('e2','fakekolkata','hardware'))]:
        for stage in stages:
            print(f'ANALYSIS {stage}',flush=True)
            execute([sys.executable,str(code/'scripts'/script),'--stage',stage,'--workers',str(workers)],code,output/f'analysis_{stage}.log')
    # Current numerical verifiers check the source evidence and recomputed outputs.
    from scripts.reproduce_all import numerical
    reports=output/'numerical'
    if reports.exists():
        # Preserve earlier failed diagnostics before retrying.
        reports.rename(output/f'numerical.previous.{time.time_ns()}')
    numerical(destination,reports)
    execute([sys.executable,str(code/'scripts/generate_manuscript_figures.py'),'--package',str(destination),'--output-dir',str(output/'figures')],code,output/'figures.log')
    from scripts.compare_release import compare
    comparison=compare(root,destination);dump(output/'reference_comparison.json',comparison)
    return dict(stages=7,scope='offline analysis from archived simulation/hardware inputs',comparison=comparison)


def main(root):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['fast','analysis','supplements','all'],default='fast')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--restart',action='store_true',help='Archive this runner\'s previous outputs and recompute')
    args=p.parse_args()
    if args.workers<1:p.error('workers must be positive')
    output=args.output.resolve();started=time.perf_counter()
    if output.exists() and any(output.iterdir()) and not (output/'identity.json').is_file():
        raise FileExistsError('Nonempty output without this runner\'s identity; choose a new directory')
    info=preflight(root,output)
    with RunLock(output):
        identity=dict(release=info['release_manifest_sha256'],environment=info['environment'],mode=args.mode)
        identity_file=output/'identity.json'
        if identity_file.exists() and json.loads(identity_file.read_text())!=identity and not args.restart:
            raise ValueError('Release, environment or mode changed; use a new output directory')
        if args.restart:
            if not identity_file.exists():raise ValueError('Restart requires an existing owned run')
            history=safe_member(output,f'history/restart_{time.time_ns()}');history.mkdir(parents=True)
            for path in list(output.iterdir()):
                if path.name in ('history','.run_all.lock'):continue
                if not path.resolve().is_relative_to(output):raise ValueError('Output contains a link outside the run')
                path.replace(history/path.name)
        dump(identity_file,identity)
        resumed=(output/'execution.json').exists()
        result=dict(status='running',mode=args.mode,execution_mode='restarted' if args.restart else 'resumed' if resumed else 'clean',preflight=info,steps={})
        dump(output/'execution.json',result)
        try:
            if args.mode in ('fast','all'):result['steps']['fast']=run_fast(root,output)
            if args.mode in ('analysis','all'):result['steps']['analysis']=run_analysis(root,output,args.workers)
            if args.mode in ('supplements','all'):
                from scripts.release_supplements import run_supplements
                result['steps']['supplements']=run_supplements(root,output)
            result.update(status='complete',seconds=time.perf_counter()-started)
        except BaseException as exc:
            result.update(status='incomplete',error=f'{type(exc).__name__}: {exc}',seconds=time.perf_counter()-started)
            dump(output/'execution.json',result);raise
        dump(output/'execution.json',result)
        print('REPRODUCE_PASS: '+args.mode,flush=True)
    return 0
