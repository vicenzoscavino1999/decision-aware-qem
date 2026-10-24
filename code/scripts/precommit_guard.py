"""Read-only syntax guard for staged Python, JSON and YAML files."""
import ast,json,sys
from pathlib import Path
import yaml

def check(name):
    file=Path(name)
    if not file.is_file():return
    text=file.read_text(encoding='utf-8-sig')
    if file.suffix=='.py':ast.parse(text,filename=name)
    elif file.suffix=='.json':json.loads(text)
    elif file.suffix in ('.yaml','.yml'):yaml.safe_load(text)

if __name__=='__main__':
    for name in sys.argv[1:]:check(name)
