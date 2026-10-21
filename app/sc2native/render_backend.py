"""Per-owned-process rendering selection; never changes the parent environment."""
import hashlib
import os
from pathlib import Path

DXVK_VERSION='3.1.1'
DXVK_SHA256='c126316f7478eaff1ad8087702eda5930f2400187b9c8b3592219c34f6632780'
BACKENDS=('auto','legacy','vulkan')

def requested_backend(value=None):
    selected=os.environ.get('SC2EDITOR_RENDER_BACKEND','auto') if value is None else value
    if selected not in BACKENDS:raise ValueError('render_backend must be auto, legacy or vulkan')
    return selected

def select_backend(binaries,requested=None):
    requested=requested_backend(requested)
    library=Path(binaries)/'renderers/dxvk/d3d9.dll'
    selected=('vulkan' if library.exists() else 'legacy') if requested=='auto' else requested
    if selected=='vulkan':
        if not library.is_file() or hashlib.sha256(library.read_bytes()).hexdigest()!=DXVK_SHA256:
            raise ValueError('Pinned DXVK 3.1.1 x64 renderer missing or SHA-256 mismatched; no Editor was launched')
    return selected

def render_environment(selected,directory):
    if selected not in ('legacy','vulkan'):raise ValueError('A concrete render backend is required')
    environment=dict(os.environ)
    environment['SC2EDITOR_RENDER_BACKEND']=selected
    if selected=='vulkan':
        logs=Path(directory)/'renderer-logs';cache=Path(directory)/'renderer-cache'
        logs.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
        config=Path(directory)/'renderer.conf';config.write_text('# Private owned Editor renderer; DXVK defaults.\n',encoding='ascii')
        environment.pop('DXVK_CONFIG',None)
        environment.update(DXVK_LOG_PATH=str(logs),DXVK_STATE_CACHE_PATH=str(cache),DXVK_SHADER_CACHE_PATH=str(cache),DXVK_HUD='',DXVK_CONFIG_FILE=str(config))
    return environment
