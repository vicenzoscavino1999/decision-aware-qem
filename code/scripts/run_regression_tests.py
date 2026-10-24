"""Run the full corrected release test suite and preserve its XML and log."""
from pathlib import Path
import argparse,json,os,subprocess,sys
CODE=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();output=a.output_dir.resolve()
    if output.exists():raise FileExistsError('Use a new report directory')
    output.mkdir(parents=True)
    env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(CODE/'src'),str(CODE)])
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    command=[sys.executable,'-m','pytest',str(CODE/'tests'),'-q','-o',f'cache_dir={output / "cache"}',f'--junitxml={output / "tests.xml"}']
    with (output/'pytest.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,env=env,cwd=CODE,stdout=log,stderr=subprocess.STDOUT)
    (output/'execution.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,suite='full_release_suite'),indent=2)+'\n')
    print((output/'pytest.log').read_text(encoding='utf-8')[-3000:])
    raise SystemExit(result.returncode)
