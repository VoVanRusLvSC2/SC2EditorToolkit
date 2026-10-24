"""Opt-in packaged native audits, incoming uses, changed-project diff and restart."""
import argparse
import json
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from live_parallel_workers import ROOT,Server,sha,existing_editors,process_time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--nydus',required=True);parser.add_argument('--work',required=True);parser.add_argument('--package',action='store_true')
    parser.add_argument('--original-audit',help='Reuse an immutable completed native audit after metadata-only fixes')
    parser.add_argument('--original-store',help='Stopped runtime directory containing that audit artifact store')
    args=parser.parse_args();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False)
    assert bool(args.original_audit)==bool(args.original_store),'Supply both original audit and store'
    source=Path(args.nydus).resolve(strict=True);original=sha(source);baseline=existing_editors()
    index=Path(args.original_store)/'exports/artifacts.json' if args.original_store else None
    summary={'status':'STARTED','checks':{},'sourceSha256':original};server=Server('audit',work/'server',args.package,artifact_index=index)
    def call(route,body):
        code,value=server.call(route,body);assert code in (200,202),(code,value)
        observed=value.get('desktopObservation')
        if observed:
            assert observed['visibleWindowsOnUserDesktopPeak']==observed['editorForegroundSamples']==0
            assert not observed['inputInjectionUsed'] and not observed['desktopSwitchApiUsed']
        return value
    def queued(operation,arguments):
        job=call('/jobs/submit',{'operation':operation,'arguments':arguments,'timeout_seconds':14400 if operation=='audit_data' else 3600})
        while job['status'] in ('QUEUED','RUNNING'):
            job=call('/jobs/wait',{'job_id':job['jobId'],'wait_ms':30000})
            print(json.dumps({'operation':operation,'status':job['status'],'progress':job.get('progress')}),flush=True)
        assert job['status']=='SUCCEEDED',job
        return job['result']
    try:
        doctor=call('/doctor',{});assert doctor['status']=='PREFLIGHT_PASSED',doctor
        assert doctor['graphicsReady'] is None and not doctor['editorLaunched'];summary['checks']['preflight']=True
        checked=queued('check_document',{'map':str(source),'scope':'library:810D62ED'})
        assert checked['nativeCompilePassed'] and checked['sourceUnchanged'],checked
        assert server.download(checked['checks']['galaxyExport']['artifact']);summary['checks']['nativeCompileAndExactExport']=True
        if args.original_audit:
            from sc2native.artifacts import ArtifactStore
            from sc2native.revisions import snapshot,bind_sources,BUILTIN
            first=json.loads(Path(args.original_audit).read_text(encoding='utf8'))
            stored=ArtifactStore(Path(args.original_store)/'exports').get(first['reportId'])
            recorded=json.loads(Path(stored['path']).read_text(encoding='utf8'))
            assert all(first.get(key)==value for key,value in recorded.items()),'Original audit response differs from immutable report'
            assert first['mapRevision']==original and not first['dependencyManifest']['unmatchedNativeSources']
            editor=next(check['details']['path'] for check in doctor['checks'] if check['check']=='originalEditor')
            current=snapshot(source,editor,work)
            assert current['revision']==first['projectRevision'],'Project changed since completed traversal'
            assert current['archives']==first['dependencyManifest']['archives']
            assert current['gameBuildManifests']==first['dependencyManifest']['gameBuildManifests']
            known={v['name'].casefold() for v in current['archives']}|BUILTIN
            aliases=[name for name in first['dataSources'][1:] if name.casefold() not in known]
            assert len(aliases)==1,'Cannot uniquely preserve the previously verified private document alias'
            manifest=bind_sources(current,first['dataSources'],aliases[0])
            summary['checks']['completedNativeAuditReusedUnchanged']=True
            summary['checks']['dependencyMetadataRevalidated']=True
            (work/'dependency-revalidation.json').write_text(json.dumps({'originalReportId':first['reportId'],
                'originalReportUnchanged':True,'nativeTraversalRepeated':False,'manifest':manifest},ensure_ascii=False,indent=2),encoding='utf8')
        else:
            first=queued('audit_data',{'map':str(source),'limit':50});manifest=first['dependencyManifest']
        (work/'original-audit.json').write_text(json.dumps(first,ensure_ascii=False,indent=2),encoding='utf8')
        assert first['catalogTraversalComplete'] and len(first['catalogs'])==109 and first['counts']['getterErrors']==0
        assert first['sourceUnchanged'] and first['privateDocumentUnchanged'] and first['nativeNewErrorsClear'] is True
        assert manifest['projectRevisionComplete'],manifest
        assert len(manifest['archives'])>=3 and manifest['gameBuildIdentityVerified']
        report=first['reportId'];assert report==first['reportArtifact']['id']
        uses=call('/data/audit/uses',{'report_id':report,'target_catalog':'Weapon','target_id':'GuassRifle','catalog':'Unit','limit':500})
        assert any(i['objectId']=='Marine' and i['field']=='WeaponArray[0].Link' for i in uses['items']),uses
        summary['checks']['incomingOriginalTypedUses']=uses['totalMatches']
        page=call('/data/audit/query',{'report_id':report,'section':'objects','catalog':'Unit','object_id':'Marine'})
        assert page['totalMatches']==1 and not page['editorRequired'];summary['checks']['exactObjectQuery']=True
        page=call('/data/audit/query',{'report_id':report,'kind':'missing-resource','limit':2})
        assert page['totalMatches']>2 and len(page['items'])==2 and page['nextOffset']==2;summary['checks']['findingPagination']=True
        assert call('/data/audit/compare',{'before_report_id':report,'after_report_id':report})['totalChanges']==0
        changed=work/'Changed.SC2Mod';shutil.copyfile(source,changed);tool=ROOT/'tools/mpqcli/mpqcli.exe'
        run=subprocess.run([str(tool),'read','Base.SC2Data/GameData/ModelData.xml',str(source)],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        xml=ET.fromstring(run.stdout);model=ET.SubElement(xml,'CModel',id='ToolkitV100MissingModel');ET.SubElement(model,'Model',value='Assets/ToolkitV100/Missing.m3')
        payload=work/'ModelData.xml';payload.write_bytes(ET.tostring(xml,encoding='utf-8',xml_declaration=True))
        subprocess.run([str(tool),'add','-w','-p','Base.SC2Data/GameData/ModelData.xml',str(changed),str(payload)],capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        second=queued('audit_data',{'map':str(changed),'limit':50})
        (work/'changed-audit.json').write_text(json.dumps(second,ensure_ascii=False,indent=2),encoding='utf8')
        assert second['counts']['getterErrors']==0 and first['projectRevision']!=second['projectRevision']
        assert second['dependencyManifest']['projectRevisionComplete'] and second['nativeNewErrorsClear'] is True
        diff=call('/data/audit/compare',{'before_report_id':report,'after_report_id':second['reportId'],'section':'objects','catalog':'Model','object_id':'ToolkitV100MissingModel'})
        assert diff['counts']=={'added':1,'removed':0,'modified':0},diff
        assert diff['sameEditorAdapter'] and not diff['sameProjectRevision'];summary['checks']['changedProjectObjectDiff']=True
        diff=call('/data/audit/compare',{'before_report_id':report,'after_report_id':second['reportId'],'section':'findings','limit':2})
        assert diff['counts']['added']>0 and diff['totalChanges']>0;summary['checks']['changedProjectFindingDiff']=diff['counts']
        summary['originalCounts']=first['counts'];summary['changedCounts']=second['counts'];summary['observations']=[first['desktopObservation'],second['desktopObservation']]
        # Restart the same artifact store; no native Editor should be launched by queries.
        server.close();old=server
        from sc2native.artifacts import ArtifactStore
        from sc2native.audit_store import query_audit
        from types import SimpleNamespace
        restored=SimpleNamespace(artifacts=ArtifactStore(old.runtime/'exports'))
        assert query_audit(restored,{'report_id':report,'section':'objects','object_id':'Marine','catalog':'Unit'})['totalMatches']==1
        summary['checks']['persistentArtifactStoreReopened']=True
        assert sha(source)==original;summary['sourceUnchanged']=True
        assert all(process_time(pid)==stamp for pid,stamp in baseline.items());summary['baselineEditorsPreserved']=True
        summary['status']='V1_NATIVE_AUDIT_ACCEPTANCE_PASSED'
    finally:
        server.close();summary['serverClosed']=server.process.poll() is not None
        owned=[]
        for state in server.runtime.glob('workers/*/startup/state.json'):
            value=json.loads(state.read_text());owned.append(process_time(value['pid'])!=value['createTimeFiletime'])
        summary['ownedEditorsClosed']=all(owned)
        (work/'VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(summary['status'],flush=True)

if __name__=='__main__':main()
