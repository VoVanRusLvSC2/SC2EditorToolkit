"""Remove only the exact owned worker's private, volatile Recent Files key."""
import uuid
import winreg


def worker_key(instance):
    if not isinstance(instance,str):return None
    try:identifier=uuid.UUID(instance)
    except (ValueError,AttributeError):return None
    if instance.lower()!='{'+str(identifier)+'}':return None
    return 'Software\\SC2EditorToolkit\\Workers\\'+instance


def remove_worker_history(instance):
    path=worker_key(instance)
    if path is None:return False
    def remove(key_path):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path,0,winreg.KEY_READ|winreg.KEY_WRITE) as key:
            while True:
                try:child=winreg.EnumKey(key,0)
                except OSError as error:
                    if error.winerror==259:break
                    raise
                remove(key_path+'\\'+child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key_path)
    try:remove(path);return True
    except FileNotFoundError:return True
    except OSError:return False  # Volatile key can expire with the user hive.
