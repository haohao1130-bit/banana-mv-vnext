"""Provision the official writing guide once for Windows local startup."""
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

GUIDE_NAME='VIDEO_PROMPT_WRITING_GUIDE_ref_en.md'
GUIDE_URL='https://huggingface.co/MiniMaxAI/MiniMax-H3/resolve/main/docs/'+GUIDE_NAME


def guide_record(path):
    path=Path(path)
    if not path.is_file():return {'path':str(path),'available':False}
    data=path.read_bytes()
    return {'path':str(path),'available':True,'sha256':hashlib.sha256(data).hexdigest(),
            'bytes':len(data)}


def ensure_local_guide(cfg):
    """Keep existing files; failed downloads warn without blocking the UI."""
    path=Path(cfg['guides']['ref'])
    if path.is_file():return dict(guide_record(path),status='existing')
    temporary=None
    try:
        with urlopen(Request(GUIDE_URL,headers={'User-Agent':'BananaMVVNext/1.0'}),timeout=8) as response:data=response.read(262145)
        text=data.decode('utf-8-sig')
        if len(data)>262144 or not text.lstrip().startswith('# Full-Reference'):
            raise ValueError('The official endpoint did not return the writing guide.')
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.download')
        temporary.write_text(text,encoding='utf-8');temporary.replace(path)
        return dict(guide_record(path),status='downloaded',source=GUIDE_URL)
    except (OSError,ValueError) as error:
        if temporary is not None:temporary.unlink(missing_ok=True)
        return {'path':str(path),'available':False,'status':'warning','error':str(error)}
