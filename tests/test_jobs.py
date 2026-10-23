import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from sc2native.jobs import JobQueue,TERMINAL


class FakeWorker:
    def __init__(self,root):
        self.work=Path(root);self.operation_progress={};self.stop=threading.Event();self.calls=[];self.state=None;self.resets=0
    def begin_operation(self,identifier):self.stop.clear();self.operation_progress={'phase':'starting'}
    def alive(self):return False
    def _reset_owned_editor(self):self.resets+=1
    def abort_owned_operation(self,reason):self.stop.set()
    def diagnostics(self,request):
        self.calls.append(request['id']);self.operation_progress={'phase':'native-diagnostics'}
        if request.get('block'):self.stop.wait(5)
        if request.get('delay'):time.sleep(request['delay'])
        return {'status':'READ','id':request['id']}
    def search_objects(self,request):raise FileExistsError('Existing immutable output')


class Jobs(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.worker=FakeWorker(self.temp.name);self.queue=JobQueue(self.worker,capacity=3,history=10)
    def tearDown(self):self.queue.close();self.temp.cleanup()
    def done(self,job):
        until=time.monotonic()+5
        while time.monotonic()<until:
            value=self.queue.wait({'job_id':job['jobId'],'wait_ms':100})
            if value['status'] in TERMINAL:return value
        self.fail('Job did not terminate')
    def test_fifo_and_isolated_request_snapshot(self):
        arguments={'id':1,'delay':.1}
        a=self.queue.submit({'operation':'diagnostics','arguments':arguments});arguments['id']=99
        b=self.queue.submit({'operation':'diagnostics','arguments':{'id':2}})
        self.assertEqual(self.done(a)['status'],'SUCCEEDED');self.assertEqual(self.done(b)['result']['id'],2)
        self.assertEqual(self.worker.calls,[1,2])
    def test_cancel_queued_never_calls_worker(self):
        a=self.queue.submit({'operation':'diagnostics','arguments':{'id':1,'block':True}})
        until=time.monotonic()+2
        while self.queue.status({'job_id':a['jobId']})['status']!='RUNNING' and time.monotonic()<until:time.sleep(.01)
        b=self.queue.submit({'operation':'diagnostics','arguments':{'id':2}})
        self.assertEqual(self.queue.cancel({'job_id':b['jobId']})['status'],'CANCELLED')
        self.queue.cancel({'job_id':a['jobId']});self.assertEqual(self.done(a)['status'],'CANCELLED')
        self.assertEqual(self.worker.calls,[1]);self.assertEqual(self.worker.resets,1)
    def test_deadline_discards_owned_worker_then_next_job_runs_once(self):
        a=self.queue.submit({'operation':'diagnostics','arguments':{'id':1,'block':True},'timeout_seconds':1})
        b=self.queue.submit({'operation':'diagnostics','arguments':{'id':2}})
        self.assertEqual(self.done(a)['status'],'TIMED_OUT');self.assertEqual(self.done(b)['status'],'SUCCEEDED')
        self.assertEqual(self.worker.calls,[1,2]);self.assertEqual(self.worker.resets,1)
    def test_synchronous_error_type_is_preserved(self):
        with self.assertRaises(FileExistsError):self.queue.run('search_objects',{})
        self.assertFalse(self.queue.busy())
    def test_invalid_requests_never_execute(self):
        for body in ({'operation':'close'},{'operation':'diagnostics','arguments':[]},{'operation':'diagnostics','timeout_seconds':True},
                     {'operation':'diagnostics','timeout_seconds':float('nan')}):
            with self.assertRaises(ValueError):self.queue.submit(body)
        self.assertFalse(self.worker.calls)
        with self.assertRaises(KeyError):self.queue.status({'job_id':'not-owned'})
    def test_running_progress_and_bounded_wait(self):
        a=self.queue.submit({'operation':'diagnostics','arguments':{'id':1,'block':True}})
        view=self.queue.wait({'job_id':a['jobId'],'wait_ms':50})
        self.assertEqual(view['status'],'RUNNING');self.assertEqual(view['progress']['phase'],'native-diagnostics')
        self.assertNotIn('arguments',view);self.queue.cancel({'job_id':a['jobId']});self.done(a)
    def test_restart_history_marks_incomplete_without_replaying(self):
        self.queue.close();path=Path(self.temp.name)/'jobs'/'interrupted.json'
        path.write_text(json.dumps({'jobId':'interrupted','operation':'diagnostics','arguments':{'id':8},'status':'RUNNING'}),encoding='utf8')
        self.queue=JobQueue(self.worker)
        self.assertEqual(self.queue.status({'job_id':'interrupted'})['status'],'INTERRUPTED');self.assertFalse(self.worker.calls)
    def test_disk_full_admission_has_no_queued_side_effect(self):
        with patch.object(self.queue,'_save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.queue.submit({'operation':'diagnostics','arguments':{'id':9}})
        self.assertFalse(self.queue.busy());self.assertFalse(self.worker.calls)
    def test_disk_full_finish_keeps_queue_alive_and_reports_failure(self):
        original=self.queue._save
        def save(job):
            if job.get('result',{}).get('id')==1:raise OSError('disk full')
            original(job)
        with patch.object(self.queue,'_save',side_effect=save):
            a=self.queue.submit({'operation':'diagnostics','arguments':{'id':1}})
            self.assertEqual(self.done(a)['status'],'FAILED')
        b=self.queue.submit({'operation':'diagnostics','arguments':{'id':2}})
        self.assertEqual(self.done(b)['status'],'SUCCEEDED');self.assertEqual(self.worker.calls,[1,2])

if __name__=='__main__':unittest.main()
