"""Bounded review-output parsing for the existing unconstrained TextGenerate backend."""
import hashlib
import json
import re
import uuid
from pathlib import Path

SCHEMA = {'type':'object','required':['issues'],'additionalProperties':False,
          'properties':{'issues':{'type':'array','items':{'type':'object',
            'required':['index','reason'],'additionalProperties':False,
            'properties':{'index':{'type':'integer'},'reason':{'type':'string','minLength':1}}}}}}


def _unpack(raw):
    text=re.sub(r'<think>.*?</think>','',str(raw),flags=re.S).strip()
    if text.startswith('```'):
        if '\n' not in text:raise ValueError('incomplete review fence')
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    return text


def _trailing_commas(text):
    # A deliberately narrow repair: punctuation outside strings only. Never
    # insert missing issue entries, close truncated data or reinterpret reasons.
    out=[];quoted=False;escaped=False
    for i,ch in enumerate(text):
        if quoted:
            out.append(ch)
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch=='"':quoted=False
        elif ch=='"':quoted=True;out.append(ch)
        elif ch==',' and text[i+1:].lstrip().startswith(('}',']')):continue
        else:out.append(ch)
    return ''.join(out)


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key: '+key)
        result[key]=value
    return result


def parse_review(raw, allowed_indices=None):
    text=_unpack(raw)
    try:data=json.loads(text,object_pairs_hook=_unique_object);method='json'
    except json.JSONDecodeError:
        data=json.loads(_trailing_commas(text),object_pairs_hook=_unique_object);method='trailing_comma_repair'
    if not isinstance(data,dict) or set(data)!={'issues'} or not isinstance(data['issues'],list):
        raise ValueError('expected exactly an object containing issues array')
    result=[]
    for row in data['issues']:
        if (not isinstance(row,dict) or set(row)!={'index','reason'} or
            type(row['index']) is not int or not isinstance(row['reason'],str) or not row['reason'].strip()):
            raise ValueError('issue requires integer index and nonempty reason')
        if allowed_indices is not None and row['index'] not in allowed_indices:
            raise ValueError('issue index outside reviewed scope')
        item={'index':row['index'],'reason':row['reason'].strip()}
        if item not in result:result.append(item)
    return result,method


def reviewed_json(system, payload, call, folder, prefix, allowed_indices, retries=2):
    """Fresh complete review on malformed JSON; never turn parse failure into pass."""
    folder=Path(folder);attempts=[];error=''
    budget=min(2,max(0,int(retries)))
    base=system+'\nReturn valid JSON matching this schema: '+json.dumps(SCHEMA)
    for attempt in range(budget+1):
        raw='';token=uuid.uuid4().hex[:8]
        record={'attempt':attempt+1,'raw_file':f'{prefix}_{token}.txt'}
        try:
            raw=call(base+('\nPrevious response was invalid: '+error+'. Return a complete fresh review with escaped JSON strings.' if error else ''),payload)
            (folder/record['raw_file']).write_text(raw,encoding='utf-8')
            issues,method=parse_review(raw,allowed_indices)
            record.update(status='valid',parse_method=method);attempts.append(record)
            return issues,{'status':'valid','attempts':attempts}
        except (ValueError,KeyError,TypeError,RuntimeError,OSError) as exc:
            if raw and not (folder/record['raw_file']).exists():
                (folder/record['raw_file']).write_text(str(raw),encoding='utf-8')
            error=str(exc);record.update(status='failed',error=error);attempts.append(record)
    return None,{'status':'review_failed_open','attempts':attempts,'error':error}


def content_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
