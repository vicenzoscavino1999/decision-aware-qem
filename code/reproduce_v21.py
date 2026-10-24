"""Portable v21 analysis; defaults to validated supplied probability caches.

Run from any folder. Use --regenerate-probabilities for fresh density simulation.
No quantum service is contacted; no credentials are required.
"""
from pathlib import Path
import sys,subprocess,argparse,os,shutil,json
ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=ROOT.parent/'inputs')
    p.add_argument('--output',type=Path,default=ROOT.parent/'reproduced')
    p.add_argument('--regenerate-probabilities',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT)
    def run(script,*args):subprocess.run([sys.executable,str(ROOT/script),*map(str,args)],env=env,check=True)
    run('revision_v19/e1_reanalysis.py','--raw',a.inputs/'reproducibility/reference_confirmatory/raw','--output',a.output/'e1')
    run('run_archive_corrections.py','--repo',a.inputs,'--output',a.output)
    fake=a.output/'fakekolkata_fixed10';fake.mkdir(exist_ok=True)
    arguments=['--bounded-10-qubits','--output',fake,'--probability-inputs',ROOT.parent/'results/fakekolkata_fixed10']
    if a.regenerate_probabilities:arguments.append('--regenerate-probabilities')
    run('run_fakekolkata_v21.py',*arguments)
    print('Completed v21 reanalysis:',a.output)
if __name__=='__main__':main()
