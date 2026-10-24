"""Prepare an external manuscript build, E1 refit, or E2 shot replay directory."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'code/src')]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    e1=sub.add_parser('e1-refit');e1.add_argument('--output',type=Path,required=True)
    paper=sub.add_parser('manuscript');paper.add_argument('--output',type=Path,required=True)
    e2=sub.add_parser('e2-shots');e2.add_argument('--archive',type=Path,required=True);e2.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or out.is_relative_to(ROOT):p.error('Choose a new output directory outside the package')
    if a.mode=='manuscript':
        import shutil
        shutil.copytree(ROOT/'manuscript',out)
        result={'source':'manuscript','files':sum(p.is_file() for p in out.rglob('*'))}
    elif a.mode=='e1-refit':
        from scripts.release_supplements import extract_verified
        result=extract_verified(ROOT/'evidence/e1_particiones_v1.zip',out,'e1_particiones_v1/',refit=True)
    else:
        metadata=json.loads((ROOT/'external_data.json').read_text())['files'][0]
        h=hashlib.sha256()
        with a.archive.open('rb') as f:
            for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=metadata['sha256']:raise ValueError('E2 archive checksum mismatch')
        with zipfile.ZipFile(a.archive) as z:
            names=[]
            for entry in z.infolist():
                if entry.is_dir():continue
                rel=PurePosixPath(entry.filename)
                if rel.is_absolute() or '..' in rel.parts or '\\' in entry.filename or ':' in entry.filename:
                    raise ValueError('Unsafe E2 archive path')
                if rel.parts[0]!='datos_E2_v3':raise ValueError('Unexpected E2 directory')
                names.append(entry.filename)
            if len(set(names))!=len(names):raise ValueError('Duplicate E2 member')
            out.mkdir(parents=True)
            for name in names:
                target=out.joinpath(*PurePosixPath(name).parts);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(name) as source,target.open('xb') as dest:
                    import shutil
                    shutil.copyfileobj(source,dest)
        result={'archive_sha256':h.hexdigest(),'files':len(names)}
    (out/'preparation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PREPARATION_COMPLETE:',out)

if __name__=='__main__':main()
