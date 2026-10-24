"""Keep compiler diagnostics separate from editor log observations."""
import re
import json
import difflib
from pathlib import Path

def parse_native_diagnostics(directory,native=None):
    path=Path(directory)/'native-log.txt'
    text=path.read_text(encoding='utf8') if path.exists() else ''
    rows={}
    for line in text.splitlines():
        match=re.match(r'compiler row=(\d+) column=(\d+) text=(.*)',line)
        if match:rows.setdefault(int(match[1]),{})[int(match[2])]=match[3]
    messages=[];observed=False;readable=False
    for line in text.splitlines():
        if line.startswith('diagnostics window='):observed=True
        if line.startswith('diagnostics readable='):readable=True
        if line.startswith('diagnostics row='):messages.append(line.partition(' text=')[2])
        if line.startswith('diagnostics text='):messages.append(line[len('diagnostics text='):])
    errors=[s for s in messages if re.search(r'(^|[\s\[])\b(ERROR|FATAL|Ошибка|ОШИБКА)\b',s)]
    warnings=[s for s in messages if re.search(r'(^|[\s\[])\b(WARNING|Warning|Предупреждение)\b',s)]
    truncated=bool((native or {}).get('diagnosticsTruncated',False))
    return {'compilerErrors':[{'index':r.get(0,''),'message':r.get(1,''),'line':r.get(2,''),'file':r.get(3,'')} for _,r in sorted(rows.items())],
        'editorLog':{'inspected':observed and readable,'windowFound':observed,'entries':messages,'recognizedErrors':errors,'recognizedWarnings':warnings,
            'clear':not errors if observed and readable and not truncated else None,'complete':observed and readable and not truncated,'rawLog':str(path)}}


def classify_native_message(text, *, channel=None, origin='nativeOutput', sequence=None):
    """Classify observed text only. Missing IDs/types stay unknown, never guessed."""
    error=re.search(r'\b(error|fatal|critical|ошибка)\b|could not|cannot\s|unable to|failed to|не удалось',text,re.I)
    warning=re.search(r'\b(warning|warn|предупреждение)\b',text,re.I)
    severity='error' if error else 'warning' if warning else 'info' if re.search(r'\b(info|debug|loading|loaded|saving|saved)\b',text,re.I) else 'unknown'
    missing=re.search(r'missing|not found|could not|cannot|unable|failed|invalid|не найден|не удалось|отсутств|неверн',text,re.I)
    category='unclassified'
    if re.search(r'dependenc|зависим',text,re.I) and (missing or severity=='error'):category='missingDependency'
    elif re.search(r'inherit|parent|наслед|родител',text,re.I) and (missing or severity in ('error','warning')):category='invalidInheritance'
    elif re.search(r'actor|актор',text,re.I) and re.search(r'conflict|duplicate|already exists|конфликт|дублик',text,re.I):category='actorConflict'
    elif re.search(r'model|\.m3\b|модел',text,re.I) and missing:category='missingModel'
    elif re.search(r'texture|\.dds\b|sound|\.wav\b|asset|текстур',text,re.I) and missing:category='missingAsset'
    elif re.search(r'catalog|\bdata\b|\.xml\b|CUnit|CActor|CEffect|CAbil|данных',text,re.I) and severity in ('error','warning'):category='dataValidation'
    if (channel or '').startswith(('Console - ','Консоль - ')) and text.strip()=='> browse':
        severity='info';category='consoleCommandEcho'
    ids=[]
    patterns=[r'\b(?:id|parent|link)\s*[:=]\s*[\'\"]?([A-Za-z_][\w]*)',
              r'\b(?:actor|unit|model|effect|ability|catalog|актор|модель)\s+[\'\"]([A-Za-z_][\w]*)[\'\"]',
              r'\bC(?:Actor|Unit|Model|Effect|Abil)\w*\[([A-Za-z_][\w]*)\]']
    for pattern in patterns:
        for value in re.findall(pattern,text,re.I):
            if value not in ids:ids.append(value)
    return {'message':text,'severity':severity,'severitySource':'native text interpretation',
            'type':category,'relatedIds':ids,'relatedIdsSource':'explicit native text' if ids else None,
            'channel':channel,'origin':origin,'sequence':sequence}


def _capture(path):
    try:
        if path.stat().st_size>2*1024**2:raise ValueError('Oversized native diagnostic capture')
        value=json.loads(path.read_text(encoding='utf8'))
        if not isinstance(value,dict):raise ValueError('Invalid native diagnostic capture')
        return value
    except (OSError,ValueError) as error:
        return {'complete':False,'channels':[],'error':str(error)}


def operation_diagnostics(directory,native=None,*,fresh_session=False):
    """New output during one native operation, with an explicit reliability gate.

    RichEdit append mutations catch repeated identical messages even if a later
    log reset/trim hides them. Unsupported replacement or missing snapshots must
    not turn into a trustworthy zero-error result.
    """
    directory=Path(directory);before=_capture(directory/'diagnostics-before.json');after=_capture(directory/'diagnostics-after.json')
    journal=_capture(directory/'diagnostics-events.json')
    if fresh_session:
        # There was no owned process before this request. Its initial output is
        # new session-start output, even though it predates the first IPC call.
        before={**after,'channels':[{**c,'entries':[]} for c in after.get('channels',[])]}
        journal={'complete':True,'events':[]}
    complete=before.get('complete') is True and after.get('complete') is True
    previous={c['key']:c for c in before.get('channels',[]) if isinstance(c,dict) and 'key' in c}
    current={c['key']:c for c in after.get('channels',[]) if isinstance(c,dict) and 'key' in c}
    if len(previous)!=len(before.get('channels',[])) or len(current)!=len(after.get('channels',[])):complete=False
    events=journal.get('events',[]) if isinstance(journal.get('events',[]),list) else []
    messages=[];old=[];comparisons=[]
    for key,channel in current.items():
        old_rows=[r.get('text','') for r in previous.get(key,{}).get('entries',[])]
        new_rows=[r.get('text','') for r in channel.get('entries',[])]
        old.extend(classify_native_message(t,channel=key,origin='baseline') for t in old_rows)
        mutations=[e for e in events if e.get('channel')==key]
        appends=[e for e in mutations if e.get('kind')=='append']
        only_appends=all(e.get('kind')=='append' for e in mutations)
        rows=[];reliable=True;basis='snapshotAppend';reset=False
        if appends and only_appends and journal.get('complete') is True:
            rows=[t for t in ''.join(e.get('text','') for e in appends).splitlines() if t]
            basis='nativeAppendMessages'
        elif new_rows[:len(old_rows)]==old_rows:
            rows=new_rows[len(old_rows):]
        else:
            # Preserve observed additions but flag reset/replacement ambiguity.
            reset=True;reliable=False;basis='snapshotSequenceDifference'
            for tag,_,_,start,end in difflib.SequenceMatcher(None,old_rows,new_rows,autojunk=False).get_opcodes():
                if tag in ('insert','replace'):rows.extend(new_rows[start:end])
        if mutations and not only_appends:
            if any(e.get('kind') in ('clear','set','unknown') for e in mutations) or not rows:
                reliable=False;reset=True
            # Confirmed appends are new even if a later reset removes them from
            # the final snapshot. Preserve them without duplicating visible rows.
            observed={}
            for row in rows:observed[row]=observed.get(row,0)+1
            consumed={}
            for event in appends:
                for row in event.get('text','').splitlines():
                    if not row:continue
                    consumed[row]=consumed.get(row,0)+1
                    if consumed[row]>observed.get(row,0):rows.append(row)
        if key not in previous or not channel.get('complete',False):reliable=False
        if journal.get('complete') is not True:reliable=False
        if not reliable:complete=False
        messages.extend(classify_native_message(t,channel=key,sequence=index) for index,t in enumerate(rows))
        comparisons.append({'channel':key,'baselineRows':len(old_rows),'afterRows':len(new_rows),
                            'newOutputRows':len(rows),'basis':basis,'reliable':reliable,'resetOrReplacementObserved':reset})
    if set(previous)-set(current):complete=False
    for event in events:
        if event.get('kind')=='dialog':messages.append(classify_native_message(event.get('text',''),channel='nativeDialog',origin='nativeDialog',sequence=event.get('sequence')))
    # A still-visible failure dialog is direct evidence even if there was no
    # supported RichEdit mutation. Avoid adding the same acknowledged dialog twice.
    for dialog in after.get('dialogs',[]):
        text=dialog.get('text','')
        if text and not any(m['message']==text for m in messages):messages.append(classify_native_message(text,channel=dialog.get('window'),origin='nativeDialog'))
    errors=[m for m in messages if m['severity']=='error'];warnings=[m for m in messages if m['severity']=='warning']
    unknown=[m for m in messages if m['severity']=='unknown']
    clear=False if errors else True if complete and not unknown else None
    return {'status':'COMPLETE' if complete and not unknown else 'PARTIAL_OR_UNKNOWN','inspectionComplete':complete,
            'classificationComplete':not unknown,'freshOwnedSession':fresh_session,
            'scope':'new native output observed during this operation; not a gameplay test',
            'newErrors':errors,'newWarnings':warnings,'newMessages':messages,'unclassifiedMessages':unknown,
            'baselineMessages':old,'newErrorsClear':clear,'newErrorCount':len(errors) if complete and not unknown else None,
            'knownNewErrorCount':len(errors),'comparisons':comparisons,
            'nativeOperationFailed':bool((native or {}).get('error')),
            'evidence':{part:str(directory/('diagnostics-'+part+'.json')) for part in ('before','after','events')}}
