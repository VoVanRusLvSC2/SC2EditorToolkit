"""Read-only saved placement queries. No Editor, renderer or input automation."""
import math
import re
import subprocess
import xml.etree.ElementTree as ET

KINDS = ('unit', 'doodad', 'point', 'camera', 'other')


def number(value, label):
    try:
        valid = type(value) in (int, float) and math.isfinite(float(value))
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(label + ' must be a finite JSON number')
    return float(value)


def bounds_option(value):
    if not isinstance(value, dict) or set(value) != {'left', 'bottom', 'right', 'top'}:
        raise ValueError('bounds must contain exactly left, bottom, right and top')
    result = {key: number(value[key], 'bounds.' + key) for key in ('left', 'bottom', 'right', 'top')}
    if result['left'] >= result['right'] or result['bottom'] >= result['top']:
        raise ValueError('bounds require left < right and bottom < top')
    return result


def search_options(request):
    query = request.get('query', '')
    if not isinstance(query, str) or len(query) > 256:
        raise ValueError('query must be a string of at most 256 characters')
    kinds = request.get('kinds', list(KINDS))
    if not isinstance(kinds, list) or not kinds or any(k not in KINDS for k in kinds):
        raise ValueError('kinds must be a nonempty list of unit, doodad, point, camera or other')
    result = {'query': query, 'kinds': kinds}
    for key, default, minimum, maximum in [('limit', 100, 1, 500), ('offset', 0, 0, 500000)]:
        value = request.get(key, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{key} must be an integer in {minimum}..{maximum}')
        result[key] = value
    if 'owner' in request:
        owner = request['owner']
        if type(owner) is not int or not 0 <= owner <= 255:
            raise ValueError('owner must be an integer in 0..255')
        result['owner'] = owner
    if 'bounds' in request:
        result['bounds'] = bounds_option(request['bounds'])
    return result


def xml_root(data, expected):
    if len(data) > 64 * 1024**2:
        raise ValueError(expected + ' XML exceeds 64 MiB')
    text = data.decode('utf-8-sig')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD/entity declarations are not accepted')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError('Invalid ' + expected + ' XML: ' + str(error)) from error
    if root.tag != expected:
        raise ValueError('Unsupported XML root; expected ' + expected)
    return root


def vector(text, dimensions):
    try:
        values = [float(v) for v in re.split(r'[,\s]+', text.strip())]
    except (AttributeError, ValueError):
        return None
    return values if len(values) == dimensions and all(math.isfinite(v) for v in values) else None


def terrain_metadata(data):
    root = xml_root(data, 'terrain')
    height = root.find('heightMap')
    if height is None:
        raise ValueError('Terrain heightMap is missing')
    dimensions = vector(height.get('dim'), 2)
    offset = vector(height.get('offset'), 3)
    scale = vector(height.get('scale'), 3)
    if (not dimensions or not offset or not scale or any(d != int(d) or not 2 <= d <= 8193 for d in dimensions)
            or any(s <= 0 for s in scale)):
        raise ValueError('Unsupported terrain dimensions, offset or scale')
    return {'bounds': {'left': offset[0], 'bottom': offset[1],
                       'right': offset[0] + (dimensions[0] - 1) * scale[0],
                       'top': offset[1] + (dimensions[1] - 1) * scale[1]},
            'vertexDimensions': [int(v) for v in dimensions], 'offset': offset, 'scale': scale,
            'boundsSource': 'saved t3Terrain.xml heightMap; not playable bounds',
            'regionMappingSupported': offset[:2] == [0, 0] and scale[:2] == [1, 1]}


def placement_records(data):
    root = xml_root(data, 'PlacedObjects')
    records = []
    for element in root.iter():
        if element is root or not element.tag.startswith('Object'):
            continue
        # Containers are not placements. Retain unlocated placements explicitly.
        if not any(key in element.attrib for key in ('Id', 'Position', 'UnitType', 'Type')):
            continue
        if len(records) >= 500000:
            raise ValueError('Saved object count exceeds 500000')
        tag = element.tag
        kind = {'ObjectUnit': 'unit', 'ObjectDoodad': 'doodad', 'ObjectPoint': 'point',
                'ObjectCamera': 'camera'}.get(tag, 'other')
        position = vector(element.get('Position'), 3)
        raw_owner = element.get('Player')
        owner = int(raw_owner) if raw_owner and re.fullmatch(r'\d{1,3}', raw_owner) else None
        records.append({'objectKey': f'{tag}:{element.get("Id", "unassigned")}:{len(records)}',
                        'id': element.get('Id'), 'kind': kind, 'xmlTag': tag,
                        'type': element.get('UnitType') or element.get('Type'),
                        'name': element.get('Name') or element.findtext('Name') or '',
                        'position': dict(zip(('x', 'y', 'z'), position)) if position else None,
                        'owner': owner, 'rotation': element.get('Rotation'), 'scale': element.get('Scale')})
    return records


def search_records(records, options):
    matched = []
    needle = options['query'].casefold()
    for record in records:
        if record['kind'] not in options['kinds']:
            continue
        if needle and needle not in ' '.join(str(record.get(k) or '') for k in ('id', 'objectKey', 'type', 'name', 'xmlTag')).casefold():
            continue
        if 'owner' in options and record['owner'] != options['owner']:
            continue
        if 'bounds' in options:
            p, b = record['position'], options['bounds']
            if p is None or not (b['left'] <= p['x'] <= b['right'] and b['bottom'] <= p['y'] <= b['top']):
                continue
        matched.append(record)
    start, limit = options['offset'], options['limit']
    return {'objects': matched[start:start + limit], 'totalMatches': len(matched),
            'offset': start, 'limit': limit, 'nextOffset': start + limit if start + limit < len(matched) else None,
            'totalObjects': len(records), 'objectsWithoutPosition': sum(r['position'] is None for r in records)}


def read_components(path, tool, required=('Objects',)):
    def run(*args):
        result = subprocess.run([str(tool), *map(str, args)], capture_output=True, timeout=60,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Cannot read saved map archive: ' + result.stderr[-1000:].decode('utf8', errors='replace'))
        return result.stdout
    names = run('list', path).decode('utf-8-sig').splitlines()
    result = {}
    for component in ('Objects', 't3Terrain.xml'):
        matches = [n for n in names if n.casefold() == component.casefold()]
        if len(matches) > 1:
            raise ValueError('Ambiguous archive component: ' + component)
        if matches:
            result[component] = run('read', matches[0], path)
        elif component in required:
            # An archive listfile may omit known members. Try the exact native
            # member name; failure is not evidence of an empty object list.
            result[component] = run('read', component, path)
    return result
