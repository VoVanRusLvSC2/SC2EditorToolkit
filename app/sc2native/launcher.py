"""Report startup failures without a PyInstaller error dialog on the desktop."""
import json
import sys
import uuid
from pathlib import Path


def run(main):
    try:
        return main()
    except Exception as error:
        message={'status':'FAILED','stage':'startup','error':str(error)}
        if sys.stderr is not None:
            sys.stderr.write(json.dumps(message,ensure_ascii=False)+'\n');sys.stderr.flush()
        # Use a unique file: a rejected duplicate must not replace a live
        # server's token, worker state or previous error evidence.
        try:
            if '--work' in sys.argv:
                directory=Path(sys.argv[sys.argv.index('--work')+1])/'startup-errors'
                directory.mkdir(parents=True,exist_ok=True)
                (directory/(uuid.uuid4().hex+'.json')).write_text(json.dumps(message,ensure_ascii=False,indent=2),encoding='utf8')
        except (OSError,ValueError,IndexError):
            pass
        return 2
