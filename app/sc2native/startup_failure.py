"""Bounded startup evidence, independent of the running Editor and its input."""
import json
from pathlib import Path


def tail(path,limit=8192):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0,2);stream.seek(max(0,stream.tell()-limit))
            return stream.read(limit).decode('utf8',errors='replace')
    except OSError:return None


class NativeStartupError(RuntimeError):
    def __init__(self,directory,exit_code,state=None,observation=None,reason=None):
        directory=Path(directory);state=state or {}
        self.evidence_directory=directory
        status=state.get('status','STARTUP_STATE_UNAVAILABLE')
        logs={}
        for name in ('host.stdout.log','host.stderr.log','startup/bootstrap.log','startup/bootstrap.log.graphics.log','startup/dispatch.log'):
            value=tail(directory/name)
            if value is not None:logs[name]=value
        native={key:state[key] for key in ('status','pid','createTimeFiletime','instanceId','renderBackend','exitCode','dispatchReady','readyModule','bootstrapFailure','editorSha256','editorVersion') if key in state}
        message=f'Hidden Editor not ready: {status}; hostExitCode={exit_code}; {directory}'
        if reason:message+='; '+reason
        super().__init__(message)
        self.error_info={'code':'EDITOR_STARTUP_FAILED','message':message,'automaticRetry':False,
            'nextStep':'Keep the startup evidence and report its failure phase and logs before retrying.',
            'evidence':{'directory':str(directory),'hostExitCode':exit_code,'native':native,'logs':logs}}
        if observation is not None:self.error_info['evidence']['desktopObservation']=observation
        try:(directory/'startup-failure.json').write_text(json.dumps(self.error_info,ensure_ascii=False,indent=2),encoding='utf8')
        except OSError as error:self.error_info['evidencePersistenceError']=str(error)
