"""Portable installation discovery and explicit, fail-closed Editor selection."""
import hashlib
import os
import shutil
import struct
import json
import subprocess
import sys
from pathlib import Path
from editor_profiles import PROFILES

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


def inspect_editor(path):
    """Identify an x64 Editor without launching it or assuming adapter compatibility."""
    path = editor_candidate(path)
    with path.open('rb') as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ': raise ValueError('Editor is not a Windows executable')
        stream.seek(struct.unpack_from('<I', dos, 60)[0])
        pe = stream.read(6)
        if pe != b'PE\0\0\x64\x86': raise ValueError('Editor must be a Windows AMD64 executable')
        stream.seek(0)
        fingerprint = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            fingerprint.update(chunk)
    return {'path': str(path), 'sha256': fingerprint.hexdigest()}


def validate_editor(path):
    identity = inspect_editor(path)
    digest = identity['sha256']
    # Retain the original public identity constants and the already-started
    # streaming inspect_editor helper; profile matching now covers more builds.
    profile=next((p for p in PROFILES if p['sha256']==digest),None)
    if digest==SUPPORTED_SHA256:profile=next(p for p in PROFILES if p['version']=='.'.join(map(str,SUPPORTED_VERSION)))
    if profile:
        native={'version':profile['version'],'adapter':profile['id'],
                'nativeOffsets':profile['nativeOffsets'],'verificationMethod':'pinned-sha256'}
    else:
        native=inspect_trusted_editor(identity)
    offsets=bool(native['nativeOffsets'])
    return {**identity,'version':native['version'],'adapter':native['adapter'],
            'originalBinaryVerified':True,'verificationMethod':native['verificationMethod'],
            'compatibility':'verified-offset-profile' if offsets else 'portable-ui',
            'nativeOffsetsVerified':offsets,'liveUiProbeRequired':not offsets,
            'capabilities':{'hiddenStartup':True,'portableGui':True,'dataAudit':offsets,'terrainObjectFilters':offsets}}


def inspect_trusted_editor(identity):
    """Ask the matching native host to verify role and Blizzard Authenticode.

    This mode does not create an Editor process or a desktop. Unlisted signed
    builds can use portable UI operations; no internal-offset profile is inferred.
    """
    resources=Path(getattr(sys,'_MEIPASS',os.environ.get('SC2_NATIVE_BIN',str(Path(__file__).resolve().parent.parent/'bin-release'))))
    helper=resources/'HiddenEditorHost.exe'
    reason='Matching native identity inspector is missing'
    if helper.is_file():
        try:
            run=subprocess.run([str(helper),'--inspect-portable-editor',identity['path']],capture_output=True,timeout=30,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            native=json.loads(run.stdout.decode('utf8'))
            if run.returncode==0 and native.get('trusted') is True and native.get('editorLaunched') is False and native.get('sha256')==identity['sha256']:
                if inspect_editor(identity['path'])!=identity:raise ValueError('Editor changed during identity verification')
                # An unlisted file can never acquire native offsets from the
                # generic inspector, even if its version string matches a profile.
                return {**native,'nativeOffsets':False,'adapter':'portable-editor-ui'}
            reason='Editor role or trusted Blizzard signature was not confirmed'
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:reason=str(error)
    raise ValueError(f"Unsupported Editor binary: {identity['path']} (SHA-256 {identity['sha256']}). {reason}; no Editor was launched")


class EditorCapabilityUnavailable(RuntimeError):
    def __init__(self,identity,capability):
        message=f"Native capability {capability} is unavailable for Editor {identity.get('version','unknown')} ({identity.get('sha256','unknown')}); portable startup and GUI operations remain available"
        super().__init__(message)
        self.error_info={'code':'NATIVE_ADAPTER_UNAVAILABLE','message':message,'automaticRetry':False,
            'nextStep':'Use a verified native-offset profile for this operation; inspect doctor for available capabilities.',
            'editorVersion':identity.get('version'),'editorSha256':identity.get('sha256'),'capability':capability}


def require_editor_capability(identity,capability):
    if not identity.get('capabilities',{}).get(capability,False):raise EditorCapabilityUnavailable(identity,capability)
