"""No Editor required: exercise packaged HTTP routes and fail-before-start checks."""
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
work = root / 'local-tests' / ('packaged-http-' + uuid.uuid4().hex)
work.mkdir(parents=True)
info = None


def call(route, body=None, authorized=True):
    request = urllib.request.Request(info['url'] + route,
        None if body is None else json.dumps(body).encode('utf8'),
        {'Content-Type': 'application/json', **({'X-SC2-Token': info['token']} if authorized else {})})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


with (work / 'stdout.log').open('wb') as stdout, (work / 'stderr.log').open('wb') as stderr:
    process = subprocess.Popen([str(root / 'dist' / 'SC2NativeAPI.exe'), 'serve',
        '--work', str(work / 'runtime'), '--port', '0'], stdout=stdout, stderr=stderr,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 30
        while not (work / 'runtime' / 'api-info.json').is_file():
            assert process.poll() is None and time.monotonic() < deadline, 'API startup failed'
            time.sleep(.1)
        info = json.loads((work / 'runtime' / 'api-info.json').read_text())
        code, health = call('/health', authorized=False)
        assert code == 200 and health['version'] == '0.7.0-rc.1' and not health['workerRunning'], health
        assert call('/modules', authorized=False)[0] == 403
        assert call('/terrain/export', {'size': 512}, authorized=False)[0] == 403
        code, modules = call('/modules')
        terrain = next(m for m in modules['modules'] if m['id'] == 'terrain')
        assert code == 200 and terrain['fullMap']['experimental']
        assert 'export_map_image' in terrain['methods']
        for request in ({'size': True}, {'size': 8192}, {'include_units': 'false'},
                        {'include_doodads': 1}, {'camera': 'Front'}, {'overwrite': 'false'}):
            code, error = call('/terrain/export', request)
            assert code == 400 and error['status'] == 'FAILED', (request, code, error)
        target = work / 'Existing.png'
        target.write_bytes(b'preserve existing output')
        code, error = call('/terrain/export', {'output': str(target)})
        assert code == 409 and target.read_bytes() == b'preserve existing output', error
        assert not call('/health')[1]['workerRunning']
        assert not (work / 'runtime' / 'worker.json').exists()
        (work / 'VERIFICATION.json').write_text(json.dumps({
            'status': 'PACKAGED_HTTP_WITHOUT_EDITOR_PASSED', 'version': health['version'],
            'editorStarted': False, 'checks': ['health', 'auth', 'capabilities', 'export argument validation',
                                             'existing output preservation']}, indent=2), encoding='utf8')
        print('Packaged HTTP: passed; no Editor started')
    finally:
        if info:
            try:
                call('/shutdown', {})
            except Exception:
                pass
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=15)
