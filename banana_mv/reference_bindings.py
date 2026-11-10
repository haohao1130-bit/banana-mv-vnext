"""Preserve explicit reference provenance without guessing identities by order."""
import json
import re


def reference_manifest(brief, image_count):
    from banana_mv.core import map_image_mentions
    mapped=map_image_mentions(brief,image_count)
    result=[]
    for line in mapped.splitlines():
        m=re.match(r'^\s*<Picture (\d+)>\s*[:：]\s*(.+)',line)
        if not m:continue
        # Only the explicit identifying label is shared, never the rest of a
        # declaration that might contain future plot or mutable clothing.
        label=re.split(r'[，,。.!！?？;；\n]',m[2],maxsplit=1)[0].strip()
        if not label or len(label)>80 or re.search(r'之後|然後|最後|結局|脫下|擊倒|\b(?:then|finally|ending)\b',label,re.I):continue
        entry={'picture':int(m[1]),'label':label}
        if entry not in result:result.append(entry)
    return result


def bind_definitions(definitions, manifest):
    """Normalize structured tables, adding only unambiguous explicit provenance.

    Stable names/identity prefixes may match user reference labels. Unknown names,
    background roles and arbitrary Subject/Picture numbering are never guessed.
    """
    original=definitions if isinstance(definitions,str) else json.dumps(definitions,ensure_ascii=False)
    try:data=json.loads(original)
    except (ValueError,TypeError):return original,[]
    if not isinstance(data,list) or not all(isinstance(row,dict) for row in data):return original,[]
    lines=[];warnings=[]
    for row in data:
        identifier=str(row.get('subject_id',row.get('id','')))
        m=re.fullmatch(r'(?:<Subject\s+(\d+)>|S(\d+))',identifier)
        if not m:
            lines.append(json.dumps(row,ensure_ascii=False));continue
        subject=f'<Subject {m[1] or m[2]}>'
        identity=str(row.get('identity',row.get('appearance','')))
        name=str(row.get('name',''))
        found={entry['picture'] for entry in manifest if
               name==entry['label'] or re.match(r'^'+re.escape(entry['label'])+r'(?:[，,。.:：\s]|$)',identity)}
        existing={int(n) for n in re.findall(r'<Picture\s+(\d+)>',json.dumps(row,ensure_ascii=False))}
        # Explicit model references stay intact; conflict with a known source
        # label is warned for review rather than silently swapping a person.
        if len(found)>1 and not existing:
            warnings.append(subject+' matches multiple user labels; ambiguous provenance was not guessed.')
            found=set()
        if existing:
            if found and existing!=found:warnings.append(subject+' picture provenance conflicts with the explicit user label; review before rendering.')
            pictures=existing
        else:pictures=found
        if pictures:
            source='Identity/reference source: '+', '.join(f'<Picture {n}>' for n in sorted(pictures))+'. '
        else:
            source=''
            # Original supporting cast may legitimately have no picture.
            if row.get('requires_reference') is True:
                warnings.append(subject+' requires a reference but has no explicit Picture provenance.')
        details={k:v for k,v in row.items() if k not in ('subject_id','id')}
        lines.append(subject+': '+source+json.dumps(details,ensure_ascii=False))
    return '\n'.join(lines),warnings
