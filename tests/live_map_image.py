"""Opt-in whole-map acceptance checks. Starts only an owned hidden worker.

Use make_terrain_fixture.py first. Review the three resulting images visually
for hills, all four corner landmarks and doodads; pixel statistics cannot prove
that every model was rendered. This script is never part of unittest discovery.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', required=True, help='Private generated fixture map')
    parser.add_argument('--work', required=True, help='Fresh output directory')
    parser.add_argument('--package', action='store_true')
    parser.add_argument('--size', type=int, default=2048, choices=(512, 1024, 2048, 4096))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = Path(args.map).resolve(strict=True)
    fixture = json.loads(source.with_suffix('.fixture.json').read_text(encoding='utf8'))
    if fixture['units'] < 4 or fixture['doodads'] < 1:
        raise ValueError('Fixture needs corner unit landmarks and placed doodads')
    original_hash = sha(source)
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=False)
    runtime = work / 'runtime'
    command = ([str(root / 'dist' / 'SC2NativeAPI.exe')] if args.package else
               [sys.executable, str(root / 'app' / 'hidden_api.py')])
    info = None

    def call(route, body=None):
        request = urllib.request.Request(
            info['url'] + route,
            data=None if body is None else json.dumps(body).encode('utf8'),
            headers={'X-SC2-Token': info['token'], 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=1200) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{error}: {error.read().decode()}') from error

    def save(name, result):
        (work / (name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf8')

    with (work / 'stdout.log').open('wb') as stdout, (work / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(command + ['serve', '--work', str(runtime), '--port', '0'],
                                   stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 30
            while not (runtime / 'api-info.json').is_file():
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('API startup failed; inspect private logs')
                time.sleep(.1)
            info = json.loads((runtime / 'api-info.json').read_text(encoding='utf8'))
            images = {}
            for name, units, doodads in [('All', True, True), ('NoUnits', False, True),
                                          ('Ground', False, False)]:
                print(f'Original full-map export: {name}', flush=True)
                target = work / (name + '.png')
                result = call('/terrain/export', {
                    'map': str(source), 'size': args.size, 'include_units': units,
                    'include_doodads': doodads, 'output': str(target)})
                save(name, result)
                assert result['status'] == 'MAP_IMAGE_EXPORTED' and result['wholeMapVerified'], result
                assert result['sourceUnchanged'] and not result['desktopScreenshot'], result
                settings = result['native']['terrainExport']
                assert all(settings[k] for k in ('fullMap', 'topDown', 'optionsConfirmed', 'exported'))
                observation = result['desktopObservation']
                assert not observation['visibleWindowsOnUserDesktopPeak'], observation
                assert not observation['editorForegroundSamples'], observation
                assert not observation.get('inputDesktopChanges', 0), observation
                with Image.open(target) as image:
                    images[name] = image.convert('RGB')
                width, height = images[name].size
                expected_height = round(args.size * fixture['dimensions'][1] / fixture['dimensions'][0])
                assert width == args.size and abs(height - expected_height) <= 1, (width, height)
                native_files = [p for p in (runtime / 'map-images').rglob('*.tga')
                                if sha(p) == result['nativeImageSha256']]
                assert len(native_files) == 1, native_files
                with Image.open(native_files[0]) as native:
                    assert native.convert('RGB').tobytes() == images[name].tobytes()
                request = urllib.request.Request(info['url'] + result['artifact']['download'],
                                                headers={'X-SC2-Token': info['token']})
                with urllib.request.urlopen(request, timeout=30) as response:
                    assert hashlib.sha256(response.read()).hexdigest() == result['artifact']['sha256'] == sha(target)
            differences = {}
            for left, right in [('All', 'NoUnits'), ('NoUnits', 'Ground')]:
                diff = ImageChops.difference(images[left], images[right])
                changed = sum(max(pixel) > 8 for pixel in diff.getdata())
                differences[left + '-' + right] = changed
                assert changed > 16, f'Visibility switch produced no meaningful pixel difference: {left}/{right}'
            target = work / 'All.png'
            before = sha(target)
            try:
                call('/terrain/export', {'map': str(source), 'output': str(target)})
            except RuntimeError as error:
                assert 'exist' in str(error).lower(), str(error)
            else:
                raise AssertionError('Existing image accepted without overwrite permission')
            assert sha(target) == before and sha(source) == original_hash
            found = call('/objects/search', {'map': str(source), 'kinds': ['unit'], 'query': 'CommandCenter'})
            save('Objects', found)
            assert found['totalMatches'] == 1 and found['sourceUnchanged'], found
            landmark = found['objects'][0]['position']
            bounds = {'left': max(0, landmark['x'] - 5), 'bottom': max(0, landmark['y'] - 5),
                      'right': landmark['x'] + 5, 'top': landmark['y'] + 5}
            region = call('/terrain/region', {'map': str(source), 'size': args.size,
                                            'bounds': bounds, 'output': str(work / 'CornerRegion.png')})
            save('CornerRegion', region)
            assert region['status'] == 'MAP_REGION_CAPTURED' and region['regionCropVerified'], region
            assert not region['region']['resampled'] and region['sourceUnchanged'], region
            assert not region['coordinateMappingValidated'], region
            # Automated math is not a native coordinate calibration. A person
            # must confirm that this southwest crop actually shows CommandCenter.
            save('VERIFICATION', {
                'status': 'AUTOMATED_MAP_EXPORT_CHECKS_PASSED_VISUAL_REVIEW_REQUIRED',
                'sourceUnchanged': True, 'pixelDifferences': differences,
                'visualReviewRequired': 'Check hills, four corner unit landmarks, doodads and boundaries in All.png; confirm CommandCenter is in CornerRegion.png',
                'scope': 'This fixture and installed Editor/device only'})
            print('Automated checks passed. Visually review All.png, NoUnits.png and Ground.png.', flush=True)
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
