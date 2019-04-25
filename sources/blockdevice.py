import os
import sys
import subprocess
import logging
sys.path.append("..")
from source import Source

logger = logging.getLogger(__name__)

def classdef():
    return BlockDevice

BLOCK_MOUNT_VERIFICATION_SUBFOLDER = "DCIM"

class BlockDevice(Source):

    uuid = None
    block_label = None

    def _attempt_mount(self):
        ps_mount = subprocess.Popen(['mount', 'UUID=%s' % self.uuid, self.mountpoint])
        logger.info("Attempting to mount device..")
        (mountout, mounterr) = ps_mount.communicate(None)
        if mounterr:
            logger.error(mounterr)
            return False
        if mountout:
            logger.debug(mountout)
        return True

    def _attempt_umount(self):
        ps_umount = subprocess.Popen(['umount', self.mountpoint])
        logger.info("Attempting to umount device..")
        (umountout, umounterr) = ps_umount.communicate(None)
        if umounterr:
            logger.error(umounterr)
            return False
        if umountout:
            logger.debug(umountout)
        return True

    def _check_attached_device(self):
        uuid = None
        ps_blkid = subprocess.Popen(['blkid'], stdout=subprocess.PIPE)
        ps_grepblkid = subprocess.Popen(['grep', self.block_label], stdin=ps_blkid.stdout, stdout=subprocess.PIPE)
        (blkout, blkerr) = ps_grepblkid.communicate(None)
        if blkout and len(blkout.strip()) > 0:
            uuid = blkout.split(' ')[2].split('=')[1].strip('"')
        else:
            logger.info("Ain't got no device attached!")
        return uuid

    def _check_mountpoint(self, mountpoint):
        if os.path.exists(mountpoint):
            logger.info("Device appears to be attached and mounted!")
            return True
        else:
            logger.info("Device is attached, but it ain't mounted!")
            return False

    def _check_mountpoint_folder(self, mountpoint):
        if not os.path.isdir(mountpoint):
            logger.info("Creating mount folder..")
            os.makedirs(mountpoint)

    # def _sigint_handler(sig, frame, what):
    #     self._attempt_umount()

    def sigint_handler(self):
        def sigint_umount(sig, frame):
            ps_umount = subprocess.Popen(['umount', self.mountpoint])
            logger.info("Attempting to umount device..")
            (umountout, umounterr) = ps_umount.communicate(None)
            if umounterr:
                logger.error(umounterr)
                return False
            if umountout:
                logger.debug(umountout)
            return True
        return sigint_umount

    def verify(self):
        mounted = False
        self.uuid = self._check_attached_device()
        if self.uuid:
            mount_attempts = 0
            MAX_ATTEMPTS = 3
            mounted = self._check_mountpoint(os.path.join(self.mountpoint, BLOCK_MOUNT_VERIFICATION_SUBFOLDER))
            while not mounted:
                self._check_mountpoint_folder(self.mountpoint)
                self._attempt_mount()
                mounted = self._check_mountpoint(os.path.join(self.mountpoint, BLOCK_MOUNT_VERIFICATION_SUBFOLDER))
                if not mounted:
                    mount_attempts += 1
                    if mount_attempts >= MAX_ATTEMPTS:
                        break
                    os.sleep(3)
        notempty = False
        if mounted:
            notempty = self._is_not_empty()
            self._attempt_umount()
        return notempty

    def paths(self):
        self._attempt_mount()
        for p in self._paths():
            yield p
        self._attempt_umount()
