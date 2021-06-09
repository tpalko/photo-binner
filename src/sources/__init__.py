from .android import Android
from .blockdevice import BlockDevice
from .folder import Folder

def sources():
    return [Android, BlockDevice, Folder]
