"""Compile the revised paper in a new directory using an installed pdflatex."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

PACKAGE=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--figures',type=Path,help='Regenerated vector-figure directory; otherwise use the supplied figures')
    p.add_argument('--pdflatex',default='pdflatex',help='Installed compiler name or executable path')
    a=p.parse_args();dest=a.output_dir.resolve()
    if dest.exists():raise FileExistsError('Use a new build directory')
    if dest.is_relative_to(PACKAGE):raise ValueError('Build outside the delivered package')
    compiler=shutil.which(a.pdflatex)
    if compiler is None:raise FileNotFoundError('Install a TeX distribution with pdflatex, or supply --pdflatex')
    figures=(a.figures or PACKAGE/'manuscript/figures').resolve()
    dest.mkdir(parents=True)
    for name in ['main.tex','quantumarticle.cls']:shutil.copy2(PACKAGE/'manuscript'/name,dest/name)
    (dest/'figures').mkdir()
    for name in ['F1_accuracy_decision_separation.pdf','F6_gate0_full_vs_diagonal.pdf','F7_e1_reanalysis.pdf','F8_dynamic_full_cost.pdf','F9_e3_comparisons.pdf']:
        shutil.copy2(figures/name,dest/'figures'/name)
    for i in range(3):
        result=subprocess.run([compiler,'-interaction=nonstopmode','-halt-on-error','main.tex'],cwd=dest,capture_output=True)
        (dest/f'pass_{i+1}.log').write_bytes(result.stdout+result.stderr)
        result.check_returncode()
    log=(dest/'main.log').read_text(encoding='utf-8',errors='replace')
    forbidden=['Overfull','undefined','multiply defined','Rerun to get cross-references right']
    if any(s in log for s in forbidden):raise ValueError('Unresolved typesetting diagnostics; inspect main.log')
    receipt=dict(status='complete',passes=3,compiler=compiler,source_sha256=hashlib.sha256((dest/'main.tex').read_bytes()).hexdigest(),pdf_sha256=hashlib.sha256((dest/'main.pdf').read_bytes()).hexdigest())
    (dest/'compile_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dest/'main.pdf')

if __name__=='__main__':main()
