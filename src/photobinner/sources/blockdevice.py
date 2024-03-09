import os
import time
import sys
import subprocess
import logging
from plugin.source import Source, SourceFile

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BLOCK_MOUNT_VERIFICATION_SUBFOLDER = "DCIM"

class BlockDevice(Source):

    uuid = None
    block_label = None

    def _attempt_mount(self):
        if not os.path.exists(self.mountpoint):
            logger.debug(" - creating %s" % self.mountpoint)
            os.makedirs(self.mountpoint)
        ps_mount = subprocess.Popen(['mount', 'UUID=%s' % self.uuid, self.mountpoint])
        logger.info("Attempting to mount device at %s.." % self.mountpoint)
        (mountout, mounterr) = ps_mount.communicate(None)
        if mounterr:
            logger.error(mounterr)
        if mountout:
            logger.debug(mountout)
        return ps_mount.returncode == 0

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
        try:
            # -- we have the block device label, with which we may want to verify a UUID association
            # -- however UUID doesn't survive an SD card format 
            # -- the device label really needs to be unique
            #ps_grep_uuid = subprocess.Popen('blkid | grep %s')
            ps_blkid = subprocess.Popen(['blkid'], stdout=subprocess.PIPE)
            ps_grepblkid = subprocess.Popen(['grep', self.block_label], stdin=ps_blkid.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (blkout, blkerr) = ps_grepblkid.communicate(None)
            if blkout and len(blkout.strip()) > 0:
                uuid = str(blkout).split(' ')[2].split('=')[1].strip('"')
            else:
                logger.info("Ain't got no device attached!")
        except OSError as oe:
            logger.error("'blkid' failed -- try sudo")
        return uuid

    # def _sigint_handler(sig, frame, what):
    #     self._attempt_umount()

    def sigint_handler(self):
        return self._sigint_handler(callback=self._attempt_umount)

    def verify(self):
        mounted = False
        if not self.uuid:
            self.uuid = self._check_attached_device()
        logger.debug(" - UUID=%s" % self.uuid)
        if not self.uuid:
            logger.warn(" - no UUID found")
        else:
            mount_count = 1
            MAX_ATTEMPTS = 1
            verify_folder = os.path.join(self.mountpoint, BLOCK_MOUNT_VERIFICATION_SUBFOLDER)
            mounted = os.path.exists(verify_folder)
            while not mounted:
                mounted = self._attempt_mount()
                if mounted or not mount_count < MAX_ATTEMPTS:
                    logger.debug(" - quitting mount loop (mounted: %s, attempts made: %s)" % (mounted, mount_count))
                    break 
                mount_count += 1
                logger.debug(" - sleeping 3 before next mount attempt")
                time.sleep(3)
        notempty = False
        if mounted:
            logger.debug(" - mounted, checking if source not empty..")
            notempty = self._is_not_empty()
            self._attempt_umount()
        else:
            logger.warn(" - not able to mount the device")
        return notempty

    def paths(self):
        self._attempt_mount()
        for filepath in self._paths():
            # -- convention is to yield the original filepath and the modified/accessible filepath (if modified)
            yield SourceFile(filepath)
        #self._attempt_umount()
