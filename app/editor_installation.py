"""Portable installation discovery and explicit, fail-closed Editor selection."""
import hashlib
import os
import shutil
import struct
from pathlib import Path

SUPPORTED_VERSION = (5, 0, 17, 98310)
SUPPORTED_SHA256 = 'e561d76903221bdcd4585b9496bba1d2b9c5ae13b8fbe8c8469d213f22823d91'
EDITOR_NAME = 'SC2Editor_x64.exe'


def editor_candidate(value):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise ValueError('editor_path must be a nonempty executable or installation-directory path')
    path = Path(os.path.expandvars(str(value))).expanduser()
    if path.is_dir():
        path = path / EDITOR_NAME if (path / EDITOR_NAME).is_file() else path / 'Support64' / EDITOR_NAME
    path = path.resolve(strict=True)
    if not path.is_file() or path.name.casefold() != EDITOR_NAME.casefold():
        raise ValueError('Select the original x64 SC2Editor_x64.exe, not a game or launcher')
    return path


def registry_locations():
    if os.name != 'nt':
        return []
    import winreg
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for key in (r'SOFTWARE\Blizzard Entertainment\StarCraft II', r'SOFTWARE\Blizzard Entertainment\StarCraftII'):
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                        for name in ('InstallPath', 'InstallLocation'):
                            try: found.append(winreg.QueryValueEx(handle, name)[0])
                            except OSError: pass
                except OSError: pass
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as parent:
                    for index in range(min(winreg.QueryInfoKey(parent)[0], 10000)):
                        try:
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as handle:
                                label = winreg.QueryValueEx(handle, 'DisplayName')[0]
                                if 'starcraft' in label.casefold() and ('ii' in label.casefold() or '2' in label):
                                    found.append(winreg.QueryValueEx(handle, 'InstallLocation')[0])
                        except (OSError, TypeError): pass
            except OSError: pass
    return found


def discovery_locations():
    found = registry_locations()
    for key in ('ProgramFiles(x86)', 'ProgramFiles', 'ProgramW6432'):
        if os.environ.get(key):
            found.append(Path(os.environ[key]) / 'StarCraft II')
    on_path = shutil.which(EDITOR_NAME)
    if on_path: found.append(on_path)
    return found


def resolve_editor(value=None):
    explicit = value if value is not None else os.environ.get('SC2_EDITOR_PATH')
    if explicit is not None:
        return editor_candidate(explicit)
    candidates = {}
    for location in discovery_locations():
        try:
            path = editor_candidate(location)
            candidates[os.path.normcase(str(path))] = path
        except (ValueError, OSError, RuntimeError): pass
    if len(candidates) == 1: return next(iter(candidates.values()))
    if candidates: raise ValueError('Multiple Editor installations found; select editor_path or set SC2_EDITOR_PATH explicitly')
    raise FileNotFoundError('SC2 Editor not found; set SC2_EDITOR_PATH or supply editor_path to its x64 EXE or installation directory')


def validate_editor(path):
    path = editor_candidate(path)
    with path.open('rb') as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ': raise ValueError('Editor is not a Windows executable')
        stream.seek(struct.unpack_from('<I', dos, 60)[0])
        pe = stream.read(6)
        if pe != b'PE\0\0\x64\x86': raise ValueError('Editor must be a Windows AMD64 executable')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SUPPORTED_SHA256:
        raise ValueError('Unsupported Editor binary: this UI adapter is verified for original 5.0.17.98310 x64; no Editor was launched. Select a supported installation; other builds need adapter validation')
    return {'path': str(path), 'version': '.'.join(map(str, SUPPORTED_VERSION)), 'sha256': digest,
            'adapter': 'sc2-editor-5.0.17.98310-ui-v1', 'originalBinaryVerified': True}
