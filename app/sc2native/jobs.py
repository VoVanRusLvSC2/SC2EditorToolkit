"""Bounded FIFO jobs for one owned Editor; failures are never silently retried."""
import copy
import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path

OPERATIONS = ('start','open_document','execute','compile_current','export_galaxy','diagnostics',
              'validate_document','save_reopen_document','cutscene_open','cutscene_seek','capture_frame',
              'capture_terrain','export_map_image','capture_map_region','list_map_cameras','search_objects',
              'export_video','check_document','read_data','data_links','check_resources','audit_data',
              'query_audit','find_object_uses','compare_audits','doctor')
TERMINAL = {'SUCCEEDED','FAILED','CANCELLED','TIMED_OUT','INTERRUPTED'}


class JobQueue:
    def __init__(self,worker,*,capacity=32,history=256):
        self.worker=worker;self.capacity=capacity;self.history=history
        self.condition=threading.Condition();self.pending=deque();self.jobs={};self.active=None;self.stopping=False
        self.root=Path(worker.work)/'jobs';self.root.mkdir(exist_ok=True)
        # A server restart cannot safely replay operations against an unknown
        # document. Preserve history, mark incomplete work, never auto-resume.
        for path in sorted(self.root.glob('*.json'),key=lambda p:p.stat().st_mtime)[-history:]:
            try:
                job=json.loads(path.read_text(encoding='utf8'))
                if job['status'] not in TERMINAL:
                    job.update(status='INTERRUPTED',finishedAt=time.time(),error='Server stopped before completion; no automatic replay')
                    self._save(job)
                self.jobs[job['jobId']]=job
            except (OSError,ValueError,KeyError):continue
        self.thread=threading.Thread(target=self._run,name='SC2-owned-job-queue',daemon=True);self.thread.start()
        self.watchdog=threading.Thread(target=self._watch,name='SC2-owned-job-deadline',daemon=True);self.watchdog.start()

    def _save(self,job):
        path=self.root/(job['jobId']+'.json');temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(path)

    def submit(self,request):
        operation=request.get('operation');arguments=request.get('arguments',{})
        if operation not in OPERATIONS:raise ValueError('Unsupported queued operation')
        if not isinstance(arguments,dict):raise ValueError('arguments must be a JSON object')
        timeout=request.get('timeout_seconds',14400 if operation in ('export_video','audit_data') else 1800)
        if type(timeout) not in (int,float) or not 1<=timeout<=14400:raise ValueError('timeout_seconds must be 1..14400')
        with self.condition:
            if self.stopping:raise RuntimeError('Job queue is stopping')
            if len(self.pending)>=self.capacity:raise RuntimeError('Job queue is full')
            while len(self.jobs)>=self.history:
                victim=next((key for key,value in self.jobs.items() if value['status'] in TERMINAL),None)
                if victim is None:raise RuntimeError('Job history is full')
                del self.jobs[victim];(self.root/(victim+'.json')).unlink(missing_ok=True)
            job={'jobId':uuid.uuid4().hex,'operation':operation,'arguments':copy.deepcopy(arguments),'status':'QUEUED',
                 'createdAt':time.time(),'timeoutSeconds':timeout,'progress':{'phase':'queued'},'automaticRetry':False}
            # Commit admission before exposing it to the worker. Disk-full or
            # a failed rename must not leave an invisible queued side effect.
            self._save(job);self.jobs[job['jobId']]=job;self.pending.append(job['jobId']);self.condition.notify_all()
            return self._view(job)

    def _view(self,job):
        result=copy.deepcopy({k:v for k,v in job.items() if k!='arguments'})
        if job['status']=='RUNNING':
            result['progress']=copy.deepcopy(getattr(self.worker,'operation_progress',None) or {'phase':'running'})
            result['elapsedSeconds']=round(time.monotonic()-job['_startedMonotonic'],2)
        result.pop('_startedMonotonic',None)
        result['queuePosition']=list(self.pending).index(job['jobId'])+1 if job['jobId'] in self.pending else None
        return result

    def status(self,request):
        with self.condition:
            identifier=request.get('job_id')
            if identifier not in self.jobs:raise KeyError('Unknown job_id')
            return self._view(self.jobs[identifier])

    def wait(self,request):
        milliseconds=request.get('wait_ms',30000)
        if type(milliseconds) is not int or not 0<=milliseconds<=30000:raise ValueError('wait_ms must be 0..30000')
        deadline=time.monotonic()+milliseconds/1000
        with self.condition:
            while True:
                result=self.status(request)
                if result['status'] in TERMINAL or time.monotonic()>=deadline:return result
                self.condition.wait(max(0,deadline-time.monotonic()))

    def cancel(self,request):
        with self.condition:
            result=self.status(request);job=self.jobs[result['jobId']]
            if job['status']=='QUEUED':
                self.pending.remove(job['jobId']);job.update(status='CANCELLED',finishedAt=time.time(),progress={'phase':'cancelled-before-start'})
                self._save(job);self.condition.notify_all()
            elif job['status']=='RUNNING':job['stopRequested']='CANCELLED'
            return self._view(job)

    def run(self,operation,arguments):
        job=self.submit({'operation':operation,'arguments':arguments})
        while job['status'] not in TERMINAL:job=self.wait({'job_id':job['jobId']})
        if job['status'] in ('SUCCEEDED','FAILED') and 'result' in job:
            if job.get('exceptionType'):
                kind={'FileExistsError':FileExistsError,'FileNotFoundError':FileNotFoundError,'ValueError':ValueError,'KeyError':KeyError}.get(job['exceptionType'],RuntimeError)
                failure=kind(job['result'].get('error','Queued operation failed'))
                failure.error_info=copy.deepcopy(job['result'].get('errorInfo',{}));failure.job_id=job['jobId']
                raise failure
            return {**job['result'],'jobId':job['jobId']}
        raise RuntimeError(job.get('error') or 'Job '+job['status'])

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.pending or self.stopping)
                if self.stopping and not self.pending:return
                identifier=self.pending.popleft();job=self.jobs[identifier];self.active=identifier
                job.update(status='RUNNING',startedAt=time.time(),_startedMonotonic=time.monotonic(),progress={'phase':'starting'})
                self.worker.begin_operation(identifier)
                try:self._save(job)
                except OSError as failure:
                    job.update(status='FAILED',finishedAt=time.time(),error='Job history could not be written: '+str(failure),progress={'phase':'persistence-failed'})
                    self.active=None;self.condition.notify_all();continue
            try:
                from .contracts import decorate,error_info
                result=decorate(getattr(self.worker,job['operation'])(copy.deepcopy(job['arguments'])))
                state='FAILED' if result.get('status')=='FAILED' else 'SUCCEEDED';error=None
            except Exception as failure:
                result=decorate({'status':'FAILED','error':str(failure),'errorInfo':error_info(failure)});state='FAILED';error=str(failure);job['exceptionType']=type(failure).__name__
            with self.condition:
                stopped=job.get('stopRequested')
                if stopped:
                    state=stopped;error='Owned operation stopped; private Editor discarded; no automatic retry'
                    self.worker._reset_owned_editor()
                elif not self.worker.alive() and getattr(self.worker,'state',None):self.worker._reset_owned_editor()
                job.update(status=state,finishedAt=time.time(),result=result,progress={'phase':'finished'})
                if error:job['error']=error
                try:self._save(job)
                except OSError as failure:
                    job.update(status='FAILED',error='Job completed but history could not be written: '+str(failure),progress={'phase':'persistence-failed'})
                finally:self.active=None;self.condition.notify_all()

    def _watch(self):
        while True:
            with self.condition:
                if self.stopping and self.active is None:return
                if self.active:
                    job=self.jobs[self.active]
                    if time.monotonic()-job['_startedMonotonic']>=job['timeoutSeconds']:
                        job.setdefault('stopRequested','TIMED_OUT')
                    if job.get('stopRequested'):
                        # Identity checked by Worker; never cancel a callback
                        # and reuse that Editor. Discard only its private process.
                        self.worker.abort_owned_operation(job['stopRequested'])
                self.condition.wait(.1)

    def busy(self):
        with self.condition:return self.active is not None or bool(self.pending)

    def close(self):
        with self.condition:
            self.stopping=True
            for identifier in list(self.pending):self.cancel({'job_id':identifier})
            if self.active:self.jobs[self.active]['stopRequested']='CANCELLED'
            self.condition.notify_all()
        self.thread.join(30);self.watchdog.join(2)
