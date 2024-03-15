import os
import sys

# print(os.path.realpath(__file__))
# print(sys.path)
sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), '..'))

import subprocess
import logging
from datetime import datetime
from plugin.source import Source, SourceFile
import traceback
from adb_shell.adb_device import AdbDeviceTcp, AdbDeviceUsb
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.exceptions import AdbConnectionError, UsbDeviceNotFoundError, TcpTimeoutException

# logger = logging.getLogger(__name__)
# #logger.setLevel(logging.DEBUG)
# sh = logging.StreamHandler()
# #sh.setLevel(logging.DEBUG)
# f = logging.Formatter('%(message)s')
# sh.setFormatter(f)
# if logger.hasHandlers():
#     print("clearing handlers")
#     logger.handlers.clear()
# logger.addHandler(sh)

#print(logger.handlers)

adb_shell_logger = logging.getLogger('adb_shell')
adb_shell_logger.setLevel(logging._nameToLevel['INFO'])
logger = logging.getLogger('Android')

class Android(Source):

    device = None
    search_paths = []
    adb_key_path = None
    ip_address = None 

    def sigint_handler(self):
        return self._sigint_handler()
    
    def _get_device(self):
        if not self.device:
            logger.info("Reading ADB key at %s" % self.adb_key_path)
            with open(self.adb_key_path) as f:
                priv = f.read()
            with open(self.adb_key_path + '.pub') as f:
                pub = f.read()
            signer = PythonRSASigner(pub, priv)
            
            try:     
                if self.ip_address:
                    logger.info(f'Found IP address configured for this device: {self.ip_address}')
                    logger.info("Attempting TCP device connection at %s.." % self.ip_address)
                    try:
                        self.device = AdbDeviceTcp(host=self.ip_address, port=5037, default_transport_timeout_s=9.0)
                        # print("AdbDeviceTcp..")
                        # print(dir(self.device))
                        # logger.info("available..")
                        # print(self.device.available)
                        # logger.info("close..")
                        # self.device.close()
                        # logger.info("available..")
                        # print(self.device.available)
                        # logger.info("connect..")
                        self.device.connect(rsa_keys=[signer], auth_timeout_s=5.0)
                    except ConnectionRefusedError as cre:
                        logger.error("Connection Refused")
                        logger.error(cre)
                        logger.error(sys.exc_info()[1])
                    except TcpTimeoutException as tte:
                        logger.error("TCP Timeout")
                        logger.error(tte)
                    except:
                        logger.error("Failed TCP connection..")
                        logger.error(sys.exc_info()[0])
                        logger.error(sys.exc_info()[1])
                else:
                    logger.warn(f'No IP address configured for this device')
                
                if not self.device or not self.device.available:
                    print(f'Attempting USB connection.. (device={self.device}, available={self.device.available if self.device else "n/a"})')
                    try:
                        self.device = AdbDeviceUsb()
                        print("AdbDeviceUsb..")
                        if self.device:
                            print(dir(self.device))
                            # print(self.device.pull('/tmp', '/tmp'))
                            #logger.info("close..")
                            #self.device.close()
                            # logger.info("connect..")
                            self.device.connect(rsa_keys=[signer])
                        else:
                            print("No device object")
                        
                    except UsbDeviceNotFoundError as udnfe:
                        logger.error(udnfe)
                    except: # usb1.USBErrorBusy as b:
                        logger.error("Failed USB connection..")
                        logger.error(sys.exc_info()[0])
                        logger.error(sys.exc_info()[1])
                    #logger.info("available: %s" % self.device.available)
                    #self.device.list('/mnt/sdcard')
                    #self.device.shell('ls')
                    #self.device.stat()
                    # 
                    # 
                    
                    if self.device.available:
                        logger.info("Android device is available")
                # else:
                #     print(dir(self.device))
            except:
                logger.error(sys.exc_info()[0])
                logger.error(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
        #import pdb; pdb.set_trace();
                
        return self.device
    
    def test(self):
        device = self._get_device()
        return device

    # -- abstract
    def verify(self):                
        device = self._get_device()
        if not device.available:
            logger.error("Device is not available. Cannot verify.")
            return False
        ctime_filter = ''
        if self.from_date:
            delta = datetime.now() - self.from_date
            ctime_filter = ' -ctime -%s' % delta.days
        device_attempts = 0
        device_success = False 
        any_files = False
        self.files = {}
        while not device_success and device_attempts < 3:
            try:
                logger.info("Examining filepaths..")                
                for path in self.search_paths:
                    logger.info(" - %s:" % path)
                    #  -name \"%s\"
                    cmd_find = 'find \"%s\" -type f%s' % (path, ctime_filter)
                    raw_files = device.shell(cmd_find) 
                    filtered_files = self._filter(raw_files.split('\n'))
                    logger.info(" - %s: %s files" % (path, len(filtered_files)))
                    if len(filtered_files) > 0:
                        self.files[path] = filtered_files
                        any_files = True
                        logger.info(" - added")
                    else:
                        logger.info(" - no files, skipped")
                device_success = True 
            except AdbConnectionError as ace:
                logger.error(str(sys.exc_info()[1]))
                break
            except:
                device_attempts += 1
                logger.warn("Device attempt %s failed" % device_attempts)
                logger.error(str(sys.exc_info()[0]))
                logger.error(str(sys.exc_info()[1]))
                traceback.print_tb(sys.exc_info()[2])
                
        logger.warn("Files {}found. Device {} scanning all source paths.".format("" if any_files else "not", "succeeded" if device_success else "failed"))
        return any_files and device_success

    # -- abstract
    def paths(self):
        logger.info("source locations: %s" % ",".join(self.files.keys()))
        device = self._get_device()
        for path in self.files:
            logger.info("location %s:" % path)
            for filepath in self.files[path]:
                if self._is_processed(filepath):
                    logger.info(" - %s found as processed, skipping.." % filepath)
                    continue
                filename = filepath.rpartition('/')[-1]
                if filename.strip() == '':
                    logger.info(" - stripped filename is empty, skipping..")
                    continue
                size_bytes_output = device.shell("stat \"%s\" | grep Size | cut -d \" \" -f 4" % filepath)
                mb_contents = int(size_bytes_output)*1.0/(1024*1024)
                targetfilepath = os.path.join('/tmp', filename)
                logger.info(" - %s (%.2f MB) -> %s" % (filepath, mb_contents, targetfilepath))
                device.pull(filepath, targetfilepath)
                yield SourceFile(filepath, targetfilepath)
                logger.info(" - file yielded to loop, deleting %s.." % targetfilepath)
                if os.path.exists(targetfilepath):
                    os.remove(targetfilepath)

if __name__ == "__main__":
    config = {
        'ip_address': '192.168.1.25',
        'adb_key_path': '/home/debian/tpalko/.android/adbkey'
    }
    a = Android(**config)
    device = a.test()
    device.shell('ls')
   
