"""Opt-in frozen MCP queries against two completed, private native audits.

Stop the HTTP server first. This reopens its persisted artifact store without
starting an Editor or repeating the native traversal.
"""
import argparse
import json
import subprocess
from pathlib import Path

from live_parallel_workers import existing_editors, process_time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--before', required=True, help='Completed audit response JSON')
    parser.add_argument('--after', required=True, help='Completed changed audit response JSON')
    parser.add_argument('--response', required=True)
    args = parser.parse_args()
    work = Path(args.work).resolve(strict=True)
    before = json.loads(Path(args.before).read_text(encoding='utf8'))['reportId']
    after = json.loads(Path(args.after).read_text(encoding='utf8'))['reportId']
    baseline = existing_editors()
    startup_before = sorted(str(p) for p in work.glob('workers/*/startup/state.json'))
    messages = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2025-06-18'}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
    ]
    calls = [
        ('sc2_query_audit', {'report_id': before, 'section': 'objects',
                             'catalog': 'Unit', 'object_id': 'Marine'}),
        ('sc2_find_object_uses', {'report_id': before, 'target_catalog': 'Weapon',
                                  'target_id': 'GuassRifle', 'catalog': 'Unit'}),
        ('sc2_compare_audits', {'before_report_id': before, 'after_report_id': after,
                                'section': 'objects', 'catalog': 'Model',
                                'object_id': 'ToolkitV100MissingModel'}),
        ('sc2_query_audit', {'report_id': before, 'kind': 'missing-resource', 'limit': 2}),
        ('sc2_query_audit', {'report_id': '0' * 32}),
        ('sc2_query_audit', {'report_id': before, 'unsupported': True}),
    ]
    for ident, (name, arguments) in enumerate(calls, 3):
        messages.append({'jsonrpc': '2.0', 'id': ident, 'method': 'tools/call',
                         'params': {'name': name, 'arguments': arguments}})
    run = subprocess.run(
        [str(Path(args.package).resolve() / 'SC2NativeMCP.exe'), '--work', str(work)],
        input='\n'.join(json.dumps(m) for m in messages) + '\n',
        text=True, encoding='utf8', capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=180)
    assert run.returncode == 0, run.stderr
    rows = [json.loads(line) for line in run.stdout.splitlines()]
    assert [r['id'] for r in rows] == list(range(1, 9)), run.stdout
    assert rows[0]['result']['serverInfo']['version'] == '1.0.0'
    tools = rows[1]['result']['tools']
    assert len(tools) == 31
    assert all(t['inputSchema']['additionalProperties'] is False and
               'outputSchema' in t for t in tools)
    results = [r['result'] for r in rows[2:]]
    assert all(not r['isError'] and r['structuredContent']['outcome'] == 'completed'
               for r in results[:4]), results
    objects, uses, diff, findings = [r['structuredContent'] for r in results[:4]]
    assert objects['totalMatches'] == 1
    assert any(i['objectId'] == 'Marine' and i['field'] == 'WeaponArray[0].Link'
               for i in uses['items'])
    assert diff['counts'] == {'added': 1, 'removed': 0, 'modified': 0}
    assert diff['sameEditorAdapter'] and not diff['sameProjectRevision']
    assert findings['totalMatches'] > 2 and findings['nextOffset'] == 2
    for result, code in zip(results[4:], ('NOT_FOUND', 'INVALID_ARGUMENT')):
        assert result['isError']
        content = result['structuredContent']
        assert content['outcome'] == 'failed' and content['errorInfo']['code'] == code
    assert all(r['structuredContent']['editorRequired'] is False for r in results[:4])
    assert startup_before == sorted(str(p) for p in work.glob('workers/*/startup/state.json'))
    assert all(process_time(pid) == stamp for pid, stamp in baseline.items())
    assert existing_editors() == baseline
    summary = {'status': 'SAVED_NATIVE_AUDITS_FROZEN_MCP_PASSED', 'tools': len(tools),
               'nativeEditorStarted': False, 'originalTypedUses': uses['totalMatches'],
               'changedModel': diff['counts'], 'missingResourceFindings': findings['totalMatches'],
               'unknownReportRejected': True, 'extraArgumentRejected': True,
               'persistentArtifactStoreReopened': True}
    Path(args.response).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
