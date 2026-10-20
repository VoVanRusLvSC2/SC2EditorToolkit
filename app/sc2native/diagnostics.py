"""Keep compiler diagnostics separate from editor log observations."""
import re
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
