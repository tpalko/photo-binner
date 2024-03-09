#!/usr/bin/env python3

from adb_shell.adb_device import AdbDeviceTcp, AdbDeviceUsb
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.exceptions import TcpTimeoutException, UsbDeviceNotFoundError
import sys

# Load the public and private keys
adbkey = '/home/debian/tpalko/.android/adbkey'
priv = None 
pub = None 
with open(adbkey) as f:
    priv = f.read()
with open(adbkey + '.pub') as f:
    pub = f.read()

if not priv:
    print(f'NO PRIV')

if not pub:
    print(f'NO PUB')

signer = PythonRSASigner(pub, priv)

# Connect
try:
    print(f'Creating AdbDeviceTcp with 192.168.1.37')
    device_tcp = AdbDeviceTcp('192.168.1.37', 5037, default_transport_timeout_s=9.)
    
    print(f'Connecting to ADB TCP device..')
    device_tcp.connect(rsa_keys=[signer], auth_timeout_s=5.)
    
    print(f'Success??')
    
except TcpTimeoutException as tte:
    # print(sys.exc_info()[0])
    print(sys.exc_info()[1])

# Connect via USB (package must be installed via `pip install adb-shell[usb])`
# try:
#     print(f'Creating AdbDeviceUsb..')
#     device_usb = AdbDeviceUsb()
# 
#     print(f'Connecting to ADB USB device..')
#     device_usb.connect(rsa_keys=[signer], auth_timeout_s=0.1)
# except UsbDeviceNotFoundError as udnfe:
#     print(sys.exc_info()[0])
#     print(sys.exc_info()[1])
# Send a shell command
response1 = device_tcp.shell('echo TEST1')
# response2 = device_usb.shell('echo TEST2')
