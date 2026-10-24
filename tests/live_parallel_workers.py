"""Opt-in concurrent owned Editors; never controls existing Editors or games."""
import os
import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from ctypes import wintypes as W
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from editor_installation import resolve_editor
from sc2native.runtime import ENUM, input_desktop, kernel, process_time, user


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ProcessEntry(ctypes.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD),
                ('heap', ctypes.c_size_t), ('module', W.DWORD), ('threads', W.DWORD),
                ('parent', W.DWORD), ('priority', W.LONG), ('flags', W.DWORD),
                ('name', W.WCHAR * 260)]


def existing_editors():
    kernel.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = W.HANDLE
    kernel.Process32FirstW.argtypes = [W.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [W.HANDLE, ctypes.POINTER(ProcessEntry)]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    assert handle and handle != ctypes.c_void_p(-1).value
    entry = ProcessEntry()
    entry.size = ctypes.sizeof(entry)
    result = {}
    try:
        ok = kernel.Process32FirstW(handle, ctypes.byref(entry))
        assert ok, 'Cannot observe baseline processes'
        while ok:
            if entry.name.casefold() == 'sc2editor_x64.exe':
                result[entry.pid] = process_time(entry.pid)
            ok = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result


class Server:
    def __init__(self, name, work, packaged, editor=None, allow_screensaver=False, artifact_index=None):
        self.name, self.work, self.info, self.state = name, work, None, None
        self.allow_screensaver = allow_screensaver
        self.created = None
        self.work.mkdir()
        self.runtime = self.work / 'runtime'
        if artifact_index is not None:
            exports = self.runtime / 'exports'
            exports.mkdir(parents=True)
            shutil.copyfile(artifact_index, exports / 'artifacts.json')
        executable = [str(ROOT / os.environ.get('SC2_PACKAGE_DIR','dist') / 'SC2NativeAPI.exe')] if packaged else [sys.executable, str(ROOT / 'app/hidden_api.py')]
        editor_args = ['--editor', str(editor)] if editor else []
        with (work / 'stdout.log').open('wb') as out, (work / 'stderr.log').open('wb') as err:
            self.process = subprocess.Popen(executable + ['serve', '--port', '0', '--work', str(self.runtime)] + editor_args,
                stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            until = time.monotonic() + 60
            while not (self.runtime / 'api-info.json').is_file():
                assert self.process.poll() is None and time.monotonic() < until, 'API startup failed'
                time.sleep(.1)
            self.info = json.loads((self.runtime / 'api-info.json').read_text(encoding='utf8'))
        except Exception:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=30)
            raise
        self.counter = 0

    def call(self, route, body=None, token=None):
        request = urllib.request.Request(self.info['url'] + route,
            None if body is None else json.dumps(body).encode(),
            {'Content-Type': 'application/json', 'X-SC2-Token': token or self.info['token']})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=1200) as response:
                code, result = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            code, result = error.code, json.load(error)
        self.counter += 1
        (self.work / ('response-%03d.json' % self.counter)).write_text(json.dumps(
            {'route': route, 'http': code, 'seconds': time.monotonic() - started, 'result': result}, indent=2), encoding='utf8')
        print(self.name, route, code, result.get('status'), result.get('error'), flush=True)
        return code, result

    def good(self, route, body=None):
        code, result = self.call(route, body)
        assert code == 200 and result.get('status') != 'FAILED', result.get('error')
        observed = result.get('desktopObservation')
        if observed:
            assert observed['visibleWindowsOnUserDesktopPeak'] == observed['editorForegroundSamples'] == 0
            assert not observed['inputInjectionUsed'] and not observed['desktopSwitchApiUsed']
            if not self.allow_screensaver:
                assert observed['inputDesktopChanges'] == 0
        return result

    def download(self, artifact):
        request = urllib.request.Request(self.info['url'] + artifact['download'], headers={'X-SC2-Token': self.info['token']})
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
        assert hashlib.sha256(content).hexdigest() == artifact['sha256']
        return content

    def convert(self, letter, template):
        result = self.good('/convert', {'template': str(template),
            'triggers_file': str(ROOT / ('tests/fixtures/Triggers-' + letter + '.xml')),
            'context_label': 'Native oracle marker 20261020', 'compile': True})
        assert result['nativeCompilePassed'] and result['compilerErrors'] == 0
        expected, forbidden = ('170121', '170122') if letter == 'A' else ('170122', '170121')
        assert expected in result['galaxy'] and forbidden not in result['galaxy'], 'Cross-worker script contamination'
        for step in result['steps'].values():
            assert step['pid'] == step['dllPid'] == self.state['pid']
            assert step['transport'] == 'owned-startup-thread-local'
        artifact = self.good('/galaxy/export', {})['artifact']
        assert artifact['sha256'] == result['sourceSha256']
        assert self.download(artifact).decode('utf8') == result['galaxy']
        return {'letter': letter, 'sha256': result['sourceSha256'], 'artifact': artifact}

    def close(self):
        if self.process.poll() is None:
            try:
                self.call('/shutdown', {})
            except Exception:
                pass
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=30)
        if self.state and self.created:
            until = time.monotonic() + 15
            while process_time(self.state['pid']) == self.created and time.monotonic() < until:
                time.sleep(.1)
            assert process_time(self.state['pid']) != self.created, 'Owned Editor survived its API'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--package', action='store_true')
    parser.add_argument('--allow-screensaver', action='store_true',
        help='Allow observed Default/Screen-saver transitions; still reject owned foreground/visible windows and input injection')
    parser.add_argument('--editor-path', help='Explicit installation: test CLI selection for A and request selection for B')
    parser.add_argument('--map')
    parser.add_argument('--map-camera', default='2001')
    parser.add_argument('--scene')
    parser.add_argument('--scene-template')
    parser.add_argument('--scene-camera', default='Front Formation Camera')
    parser.add_argument('--require-audio', action='store_true', help='Use a scene with an audible native cue')
    args = parser.parse_args()
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    template = Path(args.template).resolve(strict=True)
    pins = {template: sha(template), ROOT / os.environ.get('SC2_PACKAGE_DIR','dist') / 'SC2NativeAPI.exe': sha(ROOT / os.environ.get('SC2_PACKAGE_DIR','dist') / 'SC2NativeAPI.exe')}
    editor = resolve_editor(args.editor_path)
    pins[editor] = sha(editor)
    if args.map:
        map_path = Path(args.map).resolve(strict=True)
        pins[map_path] = sha(map_path)
    if args.scene:
        assert args.scene_template, '--scene-template is required'
        for value in (args.scene,args.scene_template):
            path=Path(value).resolve(strict=True);pins[path]=sha(path)
    baseline, servers, owned, samples, errors = existing_editors(), [], {}, [], []
    stop = threading.Event()
    initial_desktop = input_desktop()
    allowed_desktops = ('Default', 'Screen-saver') if args.allow_screensaver else ('Default',)
    assert initial_desktop in allowed_desktops, 'Test requires Default desktop, or --allow-screensaver for the system screensaver'

    def observe():
        while not stop.is_set():
            try:
                for server in list(servers):
                    for path in server.runtime.glob('workers/*/startup/state.json'):
                        try:
                            state = json.loads(path.read_text(encoding='utf8'))
                            if state.get('pid') and state.get('createTimeFiletime'):
                                owned[state['pid']] = state['createTimeFiletime']
                        except (OSError, ValueError):
                            pass
                foreground = W.DWORD()
                user.GetWindowThreadProcessId(user.GetForegroundWindow(), ctypes.byref(foreground))
                visible = []
                @ENUM
                def enum(hwnd, unused):
                    pid = W.DWORD()
                    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in owned and user.IsWindowVisible(hwnd):
                        visible.append(pid.value)
                    return True
                user.EnumWindows(enum, 0)
                samples.append({'desktop': input_desktop(), 'foreground': foreground.value,
                    'ownedVisibleWindows': len(visible), 'ownedAlive': sum(process_time(pid) == created for pid, created in list(owned.items())),
                    'existingEditorsAlive': sum(process_time(pid) == created for pid, created in baseline.items())})
            except Exception as error:
                errors.append(str(error))
            stop.wait(.2)
    thread = threading.Thread(target=observe, daemon=True)
    thread.start()
    try:
        for name in ('A', 'B'):
            servers.append(Server(name, work / ('server-' + name), args.package,
                args.editor_path if name == 'A' else None, allow_screensaver=args.allow_screensaver))
        first, second = servers
        assert first.info['url'] != second.info['url'] and first.info['token'] != second.info['token']
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(s.good, '/editor/start', dict({'template': str(template), 'render_backend': 'vulkan'},
                **({'editor_path': args.editor_path} if args.editor_path and s is second else {}))) for s in servers]
            for server, future in zip(servers, futures):
                server.state = future.result()
                server.created = process_time(server.state['pid'])
                assert server.created and server.state['pid'] not in baseline
                assert server.state['renderBackend'] == 'vulkan'
                assert Path(server.state['editorInfo']['path']).samefile(editor)
                assert server.state['editorInfo']['originalBinaryVerified']
        assert first.state['pid'] != second.state['pid'] and first.state['instanceId'] != second.state['instanceId']
        assert first.call('/modules', token=second.info['token'])[0] == 403
        assert second.call('/modules', token=first.info['token'])[0] == 403
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for letters in (('A', 'B'), ('B', 'A')):
                futures = [pool.submit(s.convert, letter, template) for s, letter in zip(servers, letters)]
                pair = [future.result() for future in futures]
                assert pair[0]['sha256'] != pair[1]['sha256']
                for server, foreign in zip(servers, reversed(pair)):
                    assert server.call(foreign['artifact']['download'])[0] == 404
                results.append(pair)
            if args.map:
                rendering = pool.submit(first.good, '/terrain/capture', {'map': str(map_path),
                    'map_camera_id': args.map_camera, 'output': str(work / 'Terrain.png')})
                parallel_compile = pool.submit(second.convert, 'B', template)
                parallel_compile.result()
                frame = rendering.result()
                assert frame['requestedTerrainFrameVerified'] and frame['imageHasDetail'] and not frame['emptyFrame']
                assert frame['mapCamera']['nativeSelectionVerified']
                first.download(frame['artifact'])
        if args.scene:
            first.good('/open', {'map':str(Path(args.scene_template).resolve())})
            first.good('/cutscene/open', {'scene':str(Path(args.scene).resolve())})
            frame=first.good('/render/capture', {'camera':args.scene_camera,'time_ms':1980})
            assert frame['requestedCutsceneFrameVerified'] and frame['imageHasDetail'] and not frame['emptyFrame']
            (work/'Cutscene.png').write_bytes(first.download(frame['artifact']))
            clip=first.good('/cutscene/export', {'camera':args.scene_camera,'start_ms':990,'end_ms':1980,'fps':10,
                'output':str(work/'NativeAudioClip.mp4')})
            assert clip['status']=='CUTSCENE_MP4_EXPORTED' and clip['video']['fullDecodePassed'] and clip['audio']['fullDecodePassed']
            assert clip['audioIncluded']
            assert clip['audio']['capture']['rendererWarmup']['nativeCaptureConfirmed']
            if args.require_audio: assert not clip['audio']['silent'], 'Expected native cue was silent'
            first.download(clip['artifact'])
        for server in servers:
            assert server.good('/editor/diagnostics', {})['status'] == 'EDITOR_DIAGNOSTICS_READ'
        first.close()
        assert process_time(second.state['pid']) == second.created, 'Closing A stopped B'
        survivor = second.convert('A', template)
        second.good('/editor/diagnostics', {})
        second.close()
        assert all(sha(path) == digest for path, digest in pins.items()), 'Input or executable changed'
        stop.set()
        thread.join(5)
        assert samples and not errors, errors
        assert any(sample['ownedAlive'] == 2 for sample in samples), 'No observed concurrent Editors'
        assert all(sample['desktop'] in allowed_desktops and sample['foreground'] not in owned and not sample['ownedVisibleWindows'] for sample in samples)
        desktop_changes = sum(a['desktop'] != b['desktop'] for a,b in zip(samples,samples[1:]))
        report = {'status': 'CONCURRENT_HIDDEN_EDITORS_PASSED', 'packaged': args.package,
            'concurrentWorkers': 2, 'nativeConversions': 6 if args.map else 5, 'nativeCompilerErrors': 0,
            'distinctInstanceIds': True, 'distinctPids': True, 'parallelScriptMarkersIsolated': True,
            'crossTokenRejected': True, 'crossArtifactRejected': True, 'exactGalaxyDownloads': True,
            'editorSelection': 'explicit CLI and API request' if args.editor_path else 'automatic discovery',
            'terrainDuringOtherWorkerCompile': bool(args.map), 'shutdownOneOtherCompiles': True,
            'cutsceneAndAudioMp4': bool(args.scene),
            'audibleClipRequired': args.require_audio,
            'existingEditorsAtStart': len(baseline),
            'existingEditorsStillAlive': sum(process_time(pid) == created for pid, created in baseline.items()),
            'existingEditorsControlled': False, 'sourcesUnchanged': True, 'allTestEditorsClosed': True,
            'observations': len(samples), 'samplesWithBothAlive': sum(s['ownedAlive'] == 2 for s in samples),
            'hiddenVisibleWindows': 0, 'hiddenForegroundSamples': 0, 'desktopChanges': desktop_changes,
            'observedInputDesktops': sorted({s['desktop'] for s in samples}),
            'screensaverObservationAllowed': args.allow_screensaver,
            'inputInjectionUsed': False, 'desktopSwitchApiUsed': False}
        (work / 'VERIFICATION.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps(report, indent=2), flush=True)
    finally:
        for server in servers:
            server.close()
        stop.set()
        thread.join(5)
        (work / 'observations.json').write_text(json.dumps(samples), encoding='utf8')
        (work / 'observer-errors.json').write_text(json.dumps(errors), encoding='utf8')


if __name__ == '__main__':
    main()
