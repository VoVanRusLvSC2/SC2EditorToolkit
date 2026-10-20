"""Crop an original overhead export. Never synthesize or upscale terrain pixels."""
import math
from PIL import Image
from .map_objects import bounds_option
from .map_images import inspect_image


def validate_region(bounds, metadata):
    requested = bounds_option(bounds)
    full = metadata['bounds']
    if not metadata['regionMappingSupported']:
        raise ValueError('Region mapping currently requires terrain XY offset 0,0 and scale 1,1')
    if (requested['left'] < full['left'] or requested['bottom'] < full['bottom'] or
            requested['right'] > full['right'] or requested['top'] > full['top']):
        raise ValueError('Requested bounds lie outside the full terrain bounds; clipping is not implicit')
    return requested


def pixel_bounds(requested, full, width, height):
    dx, dy = full['right'] - full['left'], full['top'] - full['bottom']
    if abs(height - round(width * dy / dx)) > 1:
        raise ValueError('Native image aspect ratio does not match saved full terrain bounds')
    # Map XY origin is bottom-left; decoded image origin is top-left.
    # Round outwards so requested border pixels are included, never stretched.
    return (max(0, math.floor((requested['left'] - full['left']) * width / dx)),
            max(0, math.floor((full['top'] - requested['top']) * height / dy)),
            min(width, math.ceil((requested['right'] - full['left']) * width / dx)),
            min(height, math.ceil((full['top'] - requested['bottom']) * height / dy)))


def crop_region(source, output, preview, bounds, metadata):
    requested = validate_region(bounds, metadata)
    full = metadata['bounds']
    with Image.open(source) as image:
        image.load()
        box = pixel_bounds(requested, full, image.width, image.height)
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError('Requested region has no pixels at this export resolution')
        cropped = image.crop(box).convert('RGB')
        cropped.save(output, format='PNG')
        actual = {'left': full['left'] + box[0] / image.width * (full['right'] - full['left']),
                  'right': full['left'] + box[2] / image.width * (full['right'] - full['left']),
                  'top': full['top'] - box[1] / image.height * (full['top'] - full['bottom']),
                  'bottom': full['top'] - box[3] / image.height * (full['top'] - full['bottom'])}
        source_size = list(image.size)
    return {'requestedBounds': requested, 'coveredBounds': actual, 'sourcePixelBounds': list(box),
            'sourceImageSize': source_size, 'image': inspect_image(output, preview, minimum_size=1),
            'resampled': False, 'mapping': 'full terrain XY, north/up assumed; image origin top-left',
            'coordinateMappingValidated': False,
            'validation': 'EXPERIMENTAL: native full-map render and landmark coordinate calibration pending live test'}
