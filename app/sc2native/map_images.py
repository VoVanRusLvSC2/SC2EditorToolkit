"""Validate original full-map image files and create a bounded MCP preview."""
from pathlib import Path
from PIL import Image

def export_options(request):
    if 'overwrite' in request and type(request['overwrite']) is not bool:raise ValueError('overwrite must be a JSON boolean')
    size=request.get('size',2048)
    if type(size) is not int or size not in (512,1024,2048,4096):raise ValueError('size must be 512, 1024, 2048 or 4096')
    options={'size':size}
    for key in ('include_units','include_doodads'):
        value=request.get(key,True)
        if type(value) is not bool:raise ValueError(key+' must be a JSON boolean')
        options[key]=value
    if 'camera' in request or 'time_ms' in request:raise ValueError('Full-map export uses its original overhead renderer, not a cutscene camera/time')
    return options

def inspect_image(path,preview=None,png_output=None):
    path=Path(path)
    with Image.open(path) as original:
        if original.width<64 or original.height<64 or max(original.size)>8192:raise ValueError('Unexpected original map image dimensions')
        original.load()
        image=original.convert('RGB');gray=image.convert('L');histogram=gray.histogram()
        nonblack=sum(histogram[1:]);bins=sum(bool(v) for v in histogram)
        stats={'width':image.width,'height':image.height,'format':original.format,'nonBlackPixels':nonblack,'luminanceBins':bins,
            'luminanceRange':list(gray.getextrema()),'imageHasDetail':bool(bins>=8 and nonblack>image.width*image.height//1000)}
        if png_output:image.save(png_output,format='PNG')
        if preview:
            image.thumbnail((1280,1280),Image.Resampling.LANCZOS);image.save(preview,format='PNG')
        return stats
