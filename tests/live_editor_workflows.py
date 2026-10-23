"""Opt-in original Editor queue/report/Data/resource/fault matrix acceptance."""
import argparse
import json
import time
from pathlib import Path
from live_parallel_workers import ROOT,Server,sha,existing_editors,process_time


def main():
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True);p.add_argument('--work',required=True)
    p.add_argument('--package',action='store_true');p.add_argument('--nydus');p.add_argument('--water',action='store_true')
    args=p.parse_args();work=Path(args.work).resolve();work.mkdir(parents=True,exist_ok=False)
    manifest=json.loads(Path(args.matrix).read_text(encoding='utf8'));cases={c['name']:c for c in manifest['cases']}
    baseline=existing_editors();server=Server('workflows',work/'server',args.package);summary={'status':'STARTED','packaged':args.package,'checks':{},'sourceHashes':{}}
    def call(route,request):
        code,result=server.call(route,request)
        observation=result.get('desktopObservation')
        if observation:
            assert observation['visibleWindowsOnUserDesktopPeak']==observation['editorForegroundSamples']==0,observation
            assert not observation['inputInjectionUsed'] and not observation['desktopSwitchApiUsed']
        return code,result
    def wait(job):
        end=time.monotonic()+3600;phases=[]
        while time.monotonic()<end:
            code,result=call('/jobs/wait',{'job_id':job['jobId'],'wait_ms':30000});assert code==200,result
            phase=result.get('progress',{}).get('phase')
            if not phases or phases[-1]!=phase:phases.append(phase)
            if result['status'] in ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','INTERRUPTED'):
                result['observedPhases']=phases;return result
        raise TimeoutError('Live workflow deadline')
    def queued(operation,arguments,timeout=1800):
        code,job=call('/jobs/submit',{'operation':operation,'arguments':arguments,'timeout_seconds':timeout});assert code==202,job
        return job
    healthy=cases['healthy']['map']
    try:
        first=queued('check_document',{'map':healthy,'save_reopen':True})
        second=queued('diagnostics',{})
        cancelled=queued('search_objects',{'map':healthy})
        code,value=call('/jobs/cancel',{'job_id':cancelled['jobId']});assert value['status']=='CANCELLED'
        report_job=wait(first);assert report_job['status']=='SUCCEEDED',report_job
        report=report_job['result'];assert report['status']=='NATIVE_MAP_CHECK_PASSED',report
        assert report['nativeCompilePassed'] and report['nativeGenerationVerified'] and report['sourceUnchanged']
        assert report['checks']['document']['nativeSaveVerified'] and report['checks']['document']['nativeReopenVerified']
        exported=json.loads(server.download(report['reportArtifact']));assert exported['sourceSha256']==sha(healthy)
        assert server.download(report['checks']['galaxyExport']['artifact'])
        assert wait(second)['status']=='SUCCEEDED';summary['checks']['fifoReportAndQueuedCancellation']=True
        summary['checks']['nativeReport']=report['reportArtifact']['sha256']
        for case,expected in (('healthy','45'),('data-overrides','73')):
            code,data=call('/data/read',{'map':cases[case]['map'],'catalog':'Unit','object_id':'Marine','field_limit':500})
            assert code==200 and data['identityVerified'] and data['complete'],data
            life=[f for f in data['fields'] if f['field'] in ('LifeMax','CUnit_LifeMax')]
            assert len(life)==1 and expected in life[0]['values'],life
            speed=[f for f in data['fields'] if f['field']=='CUnit_Speed'];assert len(speed)==1 and speed[0]['values']==['2.25'],speed
            assert json.loads(server.download(data['dataArtifact']))['identityVerified']
            summary['checks'][case+'NativeLifeMax']=expected
        code,links=call('/data/links',{'catalog':'Unit','object_id':'Marine'})
        assert links['status']=='NATIVE_DATA_LINKS_READ' and any('GuassRifle' in n['text'] for t in links['links'] for n in t['nodes']),links
        summary['checks']['nativeObjectExplorerLinks']=True
        for catalog,identifier in (('Abil','attack'),('Effect','GuassRifle'),('Sound','Marine_Ready')):
            code,entry=call('/data/read',{'catalog':catalog,'object_id':identifier})
            assert code==200 and entry['identityVerified'] and entry['complete'],entry
            summary['checks']['nativeCatalog'+catalog]=True
        for case in ('malformed-data','missing-dependency'):
            code,fault=call('/editor/validate',{'map':cases[case]['map'],'baseline_template':healthy})
            assert fault['status']=='FAILED' and fault['sourceUnchanged'] and fault['diagnostics']['newErrors'],fault
            summary['checks'][case]=True
        recovered=wait(queued('check_document',{'map':healthy}))
        assert recovered['result']['status']=='NATIVE_MAP_CHECK_PASSED',recovered
        summary['checks']['faultRecoveryAndOldMessagesBaseline']=True
        if 'localized' in cases:
            localized=wait(queued('check_document',{'map':cases['localized']['map'],'save_reopen':True}))
            assert localized['result']['status']=='NATIVE_MAP_CHECK_PASSED',localized
            doc=localized['result']['checks']['document'];saved=Path(doc['savedArchive']['path'])
            from sc2native.components import read_string_table
            strings=read_string_table(saved,ROOT/'tools/mpqcli/mpqcli.exe','ruRU.SC2Data/LocalizedData/GameStrings.txt',work)
            assert strings['SC2NativeToolkit/LocalizationProbe']=='Проверка локализации — ёжик',strings
            summary['checks']['localizedNativeSaveReopenAndCompile']=True
        timed=wait(queued('export_map_image',{'map':healthy,'size':4096},timeout=1))
        assert timed['status']=='TIMED_OUT',timed
        fresh=wait(queued('check_document',{'map':healthy}));assert fresh['result']['status']=='NATIVE_MAP_CHECK_PASSED',fresh
        summary['checks']['nativeDeadlineAndFreshWorkerRecovery']=True
        if args.water:
            code,water=call('/terrain/export',{'map':cases['water']['map'],'size':1024})
            assert code==200 and water['wholeMapVerified'] and water['objectFiltersVerified'],water
            server.download(water['artifact']);summary['checks']['waterNativeExport']=water['artifact'];summary['waterVisualReview']='PENDING'
        if args.nydus:
            nydus=Path(args.nydus).resolve(strict=True);before=sha(nydus)
            checked=wait(queued('check_document',{'map':str(nydus),'scope':'library:810D62ED'}))
            assert checked['result']['nativeCompilePassed'] and checked['result']['sourceUnchanged'],checked
            assert sha(nydus)==before;summary['checks']['additionalDependencyStackNativeCompile']=True
        code,model=call('/data/resources',{'map':cases['data-overrides']['map'],'catalog':'Model','object_id':'Marine'})
        assert code==200 and model['resourceValidationPassed'] is True,model
        summary['checks']['nativeHealthyMainModelFile']=True
        code,bad=call('/data/resources',{'catalog':'Model','object_id':'NativeToolkitMissingModel'})
        assert bad['status']=='FAILED' and bad['resourceValidationPassed'] is False and (bad['diagnostics']['newErrors'] or bad.get('resourceErrors')),bad
        summary['checks']['nativeMissingModelDetected']=True
        assert model['previewRequested'] is False and bad['previewRequested'] is False
        for case in cases.values():
            assert sha(case['map'])==case['sha256'];summary['sourceHashes'][case['name']]=case['sha256']
        summary['status']='EDITOR_WORKFLOW_ACCEPTANCE_PASSED'
    finally:
        server.close()
        summary['ownedWorkersClosed']=server.process.poll() is not None
        summary['baselineEditorsStillObserved']=[pid for pid,stamp in baseline.items() if process_time(pid)==stamp]
        (work/'VERIFICATION.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
