"""No Editor required: exercise packaged HTTP routes and fail-before-start checks."""
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from map_archive_fixture import create_archive

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
        assert code == 200 and health['version'] == '0.10.0-rc.1' and not health['workerRunning'], health
        assert call('/modules', authorized=False)[0] == 403
        assert call('/terrain/export', {'size': 512}, authorized=False)[0] == 403
        code, modules = call('/modules')
        terrain = next(m for m in modules['modules'] if m['id'] == 'terrain')
        assert code == 200 and terrain['fullMap']['experimental']
        assert 'export_map_image' in terrain['methods']
        assert 'capture_region' in terrain['methods']
        assert 'list_map_cameras' in terrain['methods']
        editor = next(m for m in modules['modules'] if m['id'] == 'editor')
        assert 'save_reopen' in editor['methods'] and 'validate_document' in editor['methods']
        archive = create_archive(work / 'fixture', root / 'tools/mpqcli/mpqcli.exe')
        import hashlib
        before_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        code, found = call('/objects/search', {'map': str(archive), 'query': 'marine', 'limit': 1})
        assert code == 200 and found['totalMatches'] == 2 and found['nextOffset'] == 1, found
        assert found['objects'][0]['position'] == {'x': 8, 'y': 12, 'z': 0}, found
        assert not found['editorRequired'] and found['sourceUnchanged'], found
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == before_hash
        code, cameras = call('/terrain/cameras', {'map': str(archive)})
        assert code == 200 and cameras['count'] == 1 and not cameras['editorRequired'], cameras
        code, invalid_compile = call('/convert', {'template': str(archive), 'compile': 'false'})
        assert code == 400 and 'JSON boolean' in invalid_compile['error'] and not call('/health')[1]['workerRunning']
        assert cameras['cameras'][0]['cameraId'] == '4' and cameras['sourceUnchanged'], cameras
        code, error = call('/terrain/capture', {'map': str(archive), 'map_camera_id': 'missing'})
        assert code == 400 and not call('/health')[1]['workerRunning'], error
        for invalid in ({'overwrite':'false'},{'allow_empty':1},{'output':''}):
            code, error = call('/terrain/capture', invalid)
            assert code == 400 and not call('/health')[1]['workerRunning'], error
        for bounds in ({'left': 0}, {'left': -1, 'bottom': 0, 'right': 10, 'top': 10}):
            code, error = call('/terrain/region', {'map': str(archive), 'bounds': bounds})
            assert code == 400 and error['status'] == 'FAILED', error
        target_region = work / 'ExistingRegion.png'
        target_region.write_bytes(b'preserve existing region')
        code, error = call('/terrain/region', {'bounds': {'left': 0, 'bottom': 0, 'right': 10, 'top': 10}, 'output': str(target_region)})
        assert code == 409 and target_region.read_bytes() == b'preserve existing region', error
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
        for route in ('/editor/validate','/editor/save-reopen'):
            assert call(route, {'map': ''}, authorized=False)[0] == 403
            for request in ({'map': ''}, {'map': 5}, {'include_diffs': 'true'}, {'output': False}):
                code, error = call(route, request)
                assert code == 400 and error['status'] == 'FAILED', (route, request, error)
        code, error = call('/editor/save-reopen', {'map': str(archive), 'output': str(archive), 'overwrite': True})
        assert code == 400 and hashlib.sha256(archive.read_bytes()).hexdigest() == before_hash, error
        existing_archive = work / 'Existing.SC2Map'
        existing_archive.write_bytes(b'preserve archive output')
        code, error = call('/editor/save-reopen', {'map': str(archive), 'output': str(existing_archive)})
        assert code == 409 and existing_archive.read_bytes() == b'preserve archive output', error
        assert not call('/health')[1]['workerRunning']
        (work / 'VERIFICATION.json').write_text(json.dumps({
            'status': 'PACKAGED_HTTP_WITHOUT_EDITOR_PASSED', 'version': health['version'],
            'editorStarted': False, 'checks': ['health', 'auth', 'capabilities', 'export argument validation',
                                             'existing output preservation', 'saved object coordinates and pagination',
                                             'region validation before Editor startup']}, indent=2), encoding='utf8')
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
