"""Operation-scoped native diagnostics and private native save/reopen checks."""
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

import file_prepare as files
import native_xml_oracle as oracle
from .components import snapshot_components,compare_components
from .diagnostics import operation_diagnostics


def _archive(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('A nonempty archive path is required')
    path=Path(value).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in ('.sc2map','.sc2mod'):
        raise ValueError('An existing saved .SC2Map/.SC2Mod archive is required')
    return path


def _phase(worker,directory,name,operation,*,path=None,fresh_session=False,revision=None):
    output=directory/name;output.mkdir()
    error=None
    try:native=worker._native(output,operation,**({'map_path':path} if path else {}))
    except Exception as failure:
        error=str(failure);native=getattr(failure,'native_result',None) or {'status':'NOT_CONFIRMED','error':None,'failure':error}
    evidence=output/('01-'+operation)
    diagnostic=operation_diagnostics(evidence,native,fresh_session=fresh_session)
    result={'phase':name,'operation':operation,'mapRevision':revision,
            'nativeConfirmed':native.get('status')=='NATIVE_DLL_REQUEST_COMPLETED' and native.get('error')==0,
            'native':native,'diagnostics':diagnostic}
    if error:result['error']=error
    oracle.save(output/'phase-result.json',result)
    return result


def _loaded(worker,path):
    worker.state['currentDocument']=path.name;worker.state['documentPath']=str(path)
    worker.scene=None;worker.last_result=None
    oracle.save(worker.work/'worker.json',worker.state)


def _checks(phases):
    failed=[p for p in phases if not p['nativeConfirmed']]
    errors=[{'phase':p['phase'],**e} for p in phases for e in p['diagnostics']['newErrors']]
    warnings=[{'phase':p['phase'],**e} for p in phases for e in p['diagnostics']['newWarnings']]
    clear=False if errors or failed else True if all(p['diagnostics']['newErrorsClear'] is True for p in phases) else None
    return {'newErrors':errors,'newWarnings':warnings,'newErrorsClear':clear,
            'nativeCommandsConfirmed':not failed,'failedPhases':[p['phase'] for p in failed],
            'inspectionComplete':all(p['diagnostics']['inspectionComplete'] for p in phases)}


def validate_document(worker,request,*,roundtrip=False):
    for key in ('include_diffs','overwrite'):
        if key in request and type(request[key]) is not bool:raise ValueError(key+' must be a JSON boolean')
    for key in ('map','template','baseline_template','output'):
        if key in request and (not isinstance(request[key],str) or not request[key].strip()):raise ValueError(key+' must be a nonempty path string')
    if request.get('map') and request.get('template') and Path(request['map']).resolve()!=Path(request['template']).resolve():
        raise ValueError('map and template must identify the same archive')
    source=_archive(request.get('map') or request.get('template') or (worker.state['documentPath'] if worker.alive() else ''))
    target=Path(request['output']).resolve() if request.get('output') else None
    if target:
        if not roundtrip:raise ValueError('output is only supported for native save/reopen')
        if target==source:raise ValueError('Native checks never overwrite the supplied source archive')
        if target.suffix.lower()!=source.suffix.lower():raise ValueError('Output archive type must match the source')
        if target.exists() and not request.get('overwrite',False):raise FileExistsError(target)
    source_hash=files.sha(source)
    baseline=_archive(request.get('baseline_template') or str(source));baseline_hash=files.sha(baseline)
    if target==baseline:raise ValueError('Native checks never overwrite the supplied baseline archive')
    identifier=uuid.uuid4().hex;directory=worker.work/'document-checks'/identifier;directory.mkdir(parents=True)
    prepared=directory/('NativeCheck-'+identifier[:12]+source.suffix);shutil.copyfile(source,prepared)
    if files.sha(prepared)!=source_hash or files.sha(source)!=source_hash:raise RuntimeError('Source archive changed while preparing the private copy')
    result={'status':'STARTED_NOT_CONFIRMED','requestId':identifier,'module':'editor',
            'operation':'nativeSaveReopen' if roundtrip else 'validateDocument',
            'scope':'saved archive loading and new native diagnostics; not a gameplay or exhaustive Data validation test',
            'source':str(source),'sourceSha256':source_hash,'preparedCopy':str(prepared),
            'phases':[],'nativeLoadVerified':False,'nativeSaveVerified':False,'nativeReopenVerified':False,
            'componentComparisonVerified':False,'nativeValidationPassed':None}
    phases=result['phases'];saved=None
    try:
        fresh=not worker.alive()
        worker.ensure(baseline,render_backend=request.get('render_backend'),editor_path=request.get('editor_path'))
        result['ownedEditor']={key:worker.state[key] for key in ('pid','createTimeFiletime','desktop')}
        if fresh:phases.append(_phase(worker,directory,'00-startup','diagnostics',fresh_session=True,revision=baseline_hash))
        worker.last_result=None;worker.scene=None
        load=_phase(worker,directory,'01-load','load',path=prepared,revision=source_hash);phases.append(load)
        result['nativeLoadVerified']=load['nativeConfirmed'] and bool(load['native'].get('mapLoaded'))
        if not result['nativeLoadVerified']:raise RuntimeError('Original document loading was not confirmed')
        _loaded(worker,prepared)
        data=_phase(worker,directory,'02-data','load-data',revision=files.sha(prepared));phases.append(data)
        if not data['nativeConfirmed'] or not data['native'].get('documentIo',{}).get('dataLoaded'):
            raise RuntimeError('Original Data module loading was not confirmed')
        result['nativeDataModuleLoaded']=True
        if roundtrip:
            result['beforeSaveSha256']=files.sha(prepared)
            tool=files.mpq_tool();before=snapshot_components(prepared,tool,directory/'component-reads')
            oracle.save(directory/'components-before-save.json',before)
            if files.sha(prepared)!=result['beforeSaveSha256']:raise RuntimeError('Private archive changed while reading original components')
            saved=directory/('NativeSaved-'+identifier[:12]+source.suffix)
            save=_phase(worker,directory,'03-save','save-document',path=saved,revision=result['beforeSaveSha256']);phases.append(save)
            result['nativeSaveVerified']=save['nativeConfirmed'] and bool(save['native'].get('documentIo',{}).get('saved'))
            if not result['nativeSaveVerified']:raise RuntimeError('Original Editor serialization was not confirmed')
            _loaded(worker,saved)
            result['savedSha256']=files.sha(saved)
            after=snapshot_components(saved,tool,directory/'component-reads');oracle.save(directory/'components-after-save.json',after)
            if files.sha(saved)!=result['savedSha256']:raise RuntimeError('Native saved archive changed while reading components')
            saved_diff=compare_components(before,after,before_archive=prepared,after_archive=saved,tool=tool,
                work=directory/'component-reads',include_diffs=request.get('include_diffs',False))
            comparison={'sourceSha256':source_hash,'beforeSaveSha256':result['beforeSaveSha256'],
                        'savedSha256':result['savedSha256'],'beforeToSaved':saved_diff,
                        'savedToReopened':None,'textDiffsRequested':request.get('include_diffs',False)}
            oracle.save(directory/'component-comparison.json',comparison)
            result['componentComparison']={
                'beforeCount':before['count'],'savedCount':after['count'],'reopenedCount':None,
                'changedByNativeSave':saved_diff['changedCount'],'added':saved_diff['added'],'removed':saved_diff['removed'],'modified':saved_diff['modified'],
                'savedToReopenedEqual':None,
                'changes':[{k:v for k,v in change.items() if k!='textDiff'} for change in saved_diff['changes'][:200]],
                'changesTruncated':len(saved_diff['changes'])>200}
            reopen=_phase(worker,directory,'04-reopen','reopen-document',path=saved,revision=result['savedSha256']);phases.append(reopen)
            io=reopen['native'].get('documentIo',{})
            result['nativeReopenVerified']=reopen['nativeConfirmed'] and bool(io.get('closed') and io.get('reopened') and reopen['native'].get('mapLoaded'))
            if not result['nativeReopenVerified']:raise RuntimeError('Native close and disk reopen were not confirmed')
            _loaded(worker,saved)
            phases.append(_phase(worker,directory,'05-reopened-data','load-data',revision=files.sha(saved)))
            reopened=snapshot_components(saved,tool,directory/'component-reads');oracle.save(directory/'components-after-reopen.json',reopened)
            reopened_diff=compare_components(after,reopened)
            result['reopenedSha256']=files.sha(saved)
            result['componentComparisonVerified']=saved_diff['complete'] and reopened_diff['complete'] and reopened_diff['equal'] and result['reopenedSha256']==result['savedSha256']
            if not result['componentComparisonVerified']:raise RuntimeError('Saved components changed after the original disk reopen')
            comparison.update(reopenedSha256=result['reopenedSha256'],savedToReopened=reopened_diff)
            oracle.save(directory/'component-comparison.json',comparison)
            result['componentComparison']={
                'beforeCount':before['count'],'savedCount':after['count'],'reopenedCount':reopened['count'],
                'changedByNativeSave':saved_diff['changedCount'],'added':saved_diff['added'],'removed':saved_diff['removed'],'modified':saved_diff['modified'],
                'savedToReopenedEqual':reopened_diff['equal'],
                'changes':[{k:v for k,v in change.items() if k!='textDiff'} for change in saved_diff['changes'][:200]],
                'changesTruncated':len(saved_diff['changes'])>200}
        result['diagnostics']=_checks(phases)
        result['nativeValidationPassed']=result['diagnostics']['newErrorsClear']
        result['status']=('NATIVE_SAVE_REOPEN_VERIFIED' if roundtrip else 'NATIVE_DOCUMENT_VALIDATED') if result['nativeValidationPassed'] is True else 'FAILED' if result['nativeValidationPassed'] is False else 'NATIVE_DOCUMENT_CHECK_INCOMPLETE'
        if result['status']=='FAILED':result['error']='New native errors or an unconfirmed native operation were observed; see phase diagnostics'
    except Exception as error:
        result.update(status='FAILED',error=str(error),nativeValidationPassed=False)
        result['diagnostics']=_checks(phases) if phases else {'newErrorsClear':None,'inspectionComplete':False,'newErrors':[],'newWarnings':[],'failedPhases':['startup']}
        if not phases and worker.state:
            # Startup can fail before a document workspace exists. Preserve the
            # original host evidence; never turn unreadable startup logs into zero.
            report=worker.state.get('startupReport')
            result['startupEvidence']=report or str(directory)
            result['startupState']=dict(worker.state)
        # Unknown/failed native operations may leave a modal window or no active
        # document. End only this owned worker, retaining its lifetime job.
        if not result.get('nativeLoadVerified') or (roundtrip and not result.get('nativeReopenVerified')):
            if worker.monitor:worker._background_result(result)
            worker._reset_owned_editor()
    try:result['sourceUnchanged']=files.sha(source)==source_hash and files.sha(baseline)==baseline_hash
    except OSError:result['sourceUnchanged']=False
    if not result['sourceUnchanged']:result.update(status='FAILED',error='Supplied source or baseline archive changed',nativeValidationPassed=False)
    if worker.monitor:worker._background_result(result)
    if result['status']=='NATIVE_SAVE_REOPEN_VERIFIED':
        result['savedArchive']=worker.artifacts.publish_file(saved,suffix=source.suffix.lower(),mime='application/octet-stream',output=target,overwrite=request.get('overwrite',False))
    if (directory/'component-comparison.json').is_file():
        result['componentDiffArtifact']=worker.artifacts.publish_file(directory/'component-comparison.json',suffix='.json',mime='application/json')
    result['evidenceDirectory']=str(directory)
    oracle.save(directory/'result.json',result)
    return result
