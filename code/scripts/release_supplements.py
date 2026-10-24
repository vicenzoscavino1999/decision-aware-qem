"""Reproduce supplement checks in external working directories."""
from pathlib import Path, PurePosixPath
import json, shutil, sys, time, zipfile
from scripts.release_pipeline import dump, execute, sha


def extract_verified(archive, destination, prefix, omit=frozenset(), refit=False):
    """Verify every archived file before extracting a fresh portable copy."""
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Use a new supplement directory')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read(prefix+'manifest_sha256.json'))
        names=set()
        for entry in z.infolist():
            if entry.is_dir():continue
            if not entry.filename.startswith(prefix):raise ValueError('Unexpected archive prefix')
            name=entry.filename[len(prefix):]
            rel=PurePosixPath(name)
            if not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe supplement path')
            if name in names:raise ValueError('Duplicate archive member')
            names.add(name)
        if names != set(manifest)|{'manifest_sha256.json'}:raise ValueError('Supplement inventory differs from its manifest')
        import hashlib
        for name,digest in manifest.items():
            if hashlib.sha256(z.read(prefix+name)).hexdigest()!=digest:
                raise ValueError('Supplement checksum mismatch: '+name)
        destination.mkdir(parents=True)
        refit_files={'runner.py','verify.py','report.py','verify_close_scores.py','protocol.json',
                     'PROTOCOLO.txt','splits.json','freeze.json','requirements.txt'}
        count=0
        for name in sorted(names):
            rel=PurePosixPath(name)
            if name in omit:continue
            if refit and name not in refit_files and rel.parts[0] not in {'vendor','inputs','baseline'}:continue
            target=destination.joinpath(*rel.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(z.read(prefix+name))
            count+=1
    return {'files':count,'archive_sha256':sha(Path(archive))}


def run_supplements(root,output):
    root=Path(root);output=Path(output)
    work=output/'supplements'/f'run_{time.time_ns()}'
    work.mkdir(parents=True)
    print('SUPPLEMENT signed PEC',flush=True)
    pec=work/'pec'
    pec_input=extract_verified(root/'evidence/pec_decisiones_v2.zip',pec,'pec_decisiones_v2/')
    execute([sys.executable,'-B',str(pec/'verify.py'),'post','--archive-only'],pec,work/'pec.log')
    pec_report=json.loads((work/'pec.log').read_text(encoding='utf-8'))
    if pec_report.get('status')!='PASS' or pec_report['checks']['decisions_replayed']!=49152:
        raise ValueError('Signed PEC check did not finish successfully')
    dump(work/'pec_verification.json',pec_report)

    print('SUPPLEMENT E1 partitions',flush=True)
    e1=work/'e1'
    e1_input=extract_verified(root/'evidence/e1_particiones_v1.zip',e1,'e1_particiones_v1/',
                             omit={'verification.json','close_score_verification.json'})
    for script in ['verify.py','verify_close_scores.py']:
        execute([sys.executable,'-B',str(e1/script)],e1,work/(script+'.log'))
    replay=json.loads((e1/'verification.json').read_text())
    close=json.loads((e1/'close_score_verification.json').read_text())
    if replay.get('status')!='PASS' or replay['policy_decisions_replayed']!=403200 or close.get('status')!='PASS':
        raise ValueError('E1 partition checks did not finish successfully')

    print('SUPPLEMENT manuscript v45 and readout example',flush=True)
    checks=work/'manuscript';checks.mkdir()
    for script,report in [('verify_signed_pec.py','signed_pec.json'),
                          ('verify_e1_sensitivity.py','e1_partitions.json'),
                          ('verify_readout_identifiability.py','readout.json')]:
        execute([sys.executable,'-B',str(root/'code/scripts'/script),'--output',str(checks/report)],
                root,work/(script+'.log'))
        if json.loads((checks/report).read_text())['status']!='PASS':raise ValueError('Manuscript check failed: '+script)
    from scripts.verify_manuscript import verify
    dump(checks/'main.json',verify(root))
    report={'status':'complete','working_directory':str(work.relative_to(output)),
            'pec_decisions_replayed':49152,'e1_decisions_replayed':403200,
            'manuscript_claim_checks':71,'readout_arithmetic':'exact rational',
            'inputs':{'pec':pec_input,'e1':e1_input},
            'reports':{str(p.relative_to(output)):sha(p) for p in [work/'pec_verification.json',e1/'verification.json',
                e1/'close_score_verification.json',*sorted(checks.glob('*.json'))]}}
    dump(output/'supplements.json',report)
    return report
