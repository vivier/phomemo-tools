#! /usr/bin/python3

import sys
import os
import subprocess
import dbus
from bluetooth import *

bus = dbus.SystemBus()

def scan_bluetooth():
    manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                             'org.freedesktop.DBus.ObjectManager')

    objects = manager.GetManagedObjects()

    for path, interfaces in objects.items():
        if 'org.bluez.Device1' not in interfaces.keys():
            continue

        properties = interfaces['org.bluez.Device1']
        name = properties['Name']
        if (not name.startswith('Mr.in')):
                continue
        model = name[6:]

        address = properties['Address']
        device_uri = 'phomemo://' + address[0:2:]+address[3:5:]+address[6:8:]+address[9:11:]+address[12:14:]+address[15:17:]
        device_make_and_model = 'Phomemo ' + model
        device_id = 'CLS:PRINTER;CMD:EPSON;DES:Thermal Printer;MFG:Phomemo;MDL:' + model + ';'

        print('direct ' + device_uri + ' "' + device_make_and_model + '" "' +
              device_make_and_model + ' bluetooth ' + address + '" "' + device_id + '"')

if len(sys.argv) == 1:
    scan_bluetooth()
    exit(0)

try:
    device_uri = os.environ['DEVICE_URI']
except:
    exit(1)

uri = device_uri.split('://')

if uri[0] != 'phomemo':
    exit(1)

a = uri[1]
bdaddr = a[0:2:] + ':' + a[2:4:] + ':' + a[4:6:] + ':' + a[6:8:] + ':' + a[8:10:] + ':' + a[10:12:]

print('DEBUG: ' + sys.argv[0] +' device ' + bdaddr)

try:
    print('STATE: +connecting-to-device')
    sock = BluetoothSocket(RFCOMM)
    sock.bind(('00:00:00:00:00:00', 0))
    sock.connect((bdaddr, 1))
    print('STATE: +sending-data')
    with os.fdopen(sys.stdin.fileno(), 'rb', closefd=False) as stdin:
        sent = sock.send(stdin.read())
        print('DEBUG: sent %d' % (sent))
except:
    print("ERROR: Can't open Bluetooth connection: " + str(btErr), file=sys.stderr)
    exit(1)
try:
    # we need to wait the printer answer before closing the socket
    # otherwise the print is stopped
    print('STATE: +receiving-data')
    sock.settimeout(8)
    while True:
        received = sock.recv(28)
        print('DEBUG: ' + " 0x".join("%02x" % b for b in received))
except:
    pass
exit(0)
