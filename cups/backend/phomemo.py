#! /usr/bin/python3

import sys
import os
import subprocess
import dbus
import socket
import usb.core
import usb.util

bus = dbus.SystemBus()

device_id = 'CLS:PRINTER;CMD:EPSON;DES:Thermal Printer;MFG:Phomemo;MDL:'
def scan_bluetooth():
    manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                             'org.freedesktop.DBus.ObjectManager')

    objects = manager.GetManagedObjects()

    for path, interfaces in objects.items():
        if 'org.bluez.Device1' not in interfaces.keys():
            continue

        properties = interfaces['org.bluez.Device1']
        name = properties['Name']
        if (name.startswith('Mr.in')):
            model = name[6:]
        elif (name == 'T02'):
            model = name
        else:
            continue

        address = properties['Address']
        device_uri = 'phomemo://' + address[0:2:]+address[3:5:]+address[6:8:]+address[9:11:]+address[12:14:]+address[15:17:]
        device_make_and_model = 'Phomemo ' + model

        print('direct ' + device_uri + ' "' + device_make_and_model + '" "' +
              device_make_and_model + ' bluetooth ' + address + '" "' + device_id + model + ' (BT);"')

class find_class(object):
    def __init__(self, class_):
        self._class = class_
    def __call__(self, device):
        # first, let's check the device
        if device.bDeviceClass == self._class:
            return True
        # ok, transverse all devices to find an
        # interface that matches our class
        for cfg in device:
            # find_descriptor: what's it?
            intf = usb.util.find_descriptor(
                                        cfg,
                                        bInterfaceClass=self._class
                                )
            if intf is not None:
                return True

        return False

def scan_usb():
    printers = usb.core.find(find_all=1, custom_match=find_class(7), idVendor=0x0493)
    for printer in printers:
            for cfg in printer:
                intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
                if intf is None:
                    continue
                Interface = intf.bInterfaceNumber
                break
            if printer.idProduct == 0xb002:
                model = 'M02'
            elif printer.idProduct == 0x8760:
                model = 'M110'
            else:
                model = 'Unknown(0x%04x)' % (printer.idProduct)
            usb.util.get_langids(printer)
            SerialNumber = usb.util.get_string(printer, printer.iSerialNumber)
            device_uri = 'usb://Unknown/Printer?serial=%s&interface=%d' % (SerialNumber, Interface)
            device_make_and_model = 'Phomemo ' + model
            print('direct ' + device_uri + ' "' + device_make_and_model + '" "' +
              device_make_and_model + ' USB ' + SerialNumber + '" "' + device_id + model + ' (USB);"')

if len(sys.argv) == 1:
    scan_bluetooth()
    scan_usb()
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
    sock = socket.socket(socket.AF_BLUETOOTH, proto=socket.BTPROTO_RFCOMM)
    sock.connect((bdaddr, 1))
    print('STATE: +sending-data')
    with os.fdopen(sys.stdin.fileno(), 'rb', closefd=False) as stdin:
        sent = sock.send(stdin.read())
        print('DEBUG: sent %d' % (sent))
except OSError as btErr:
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
