# Phomemo-tools

This package is trying to provide tools to print pictures onto
the Phomemo M02 thermal printer from Linux.

All the information here has been reverse-engineered sniffing
the bluetooth packets emitted by the Android application.

## 1. Usage

### 1.1. Bluetooth
* connection

```
$ hcitool scan
Scanning ...
  DC:0D:30:90:23:C7	Mr.in_M02
$ sudo rfcomm connect 0 DC:0D:30:90:23:C7
  Connected /dev/rfcomm0 to DC:0D:30:90:23:C7 on channel 1
  Press CTRL-C for hangup
```
* send the picture to the printer

```
  tools/phomemo-filter.py my_picture.png > /dev/rfcomm0
```

### 1.2. USB

* Plug the USB printer cable

* check the printer is present:

```
  $ lsusb
  ...
  Bus 003 Device 013: ID 0493:b002 MAG Technology Co., Ltd 
  ...
```
You can see the serial port in the dmesg and in /dev:

```
  $ dmesg
  ...
  usb 3-3.7.2: new full-speed USB device number 13 using xhci_hcd
  usb 3-3.7.2: New USB device found, idVendor=0493, idProduct=b002, bcdDevice= 3.00
  usb 3-3.7.2: New USB device strings: Mfr=1, Product=2, SerialNumber=3
  usb 3-3.7.2: Product: USB Virtual COM
  usb 3-3.7.2: Manufacturer: Nuvoton
  usb 3-3.7.2: SerialNumber: A02014090305
  cdc_acm 3-3.7.2:1.0: ttyACM0: USB ACM device
  usblp 3-3.7.2:1.2: usblp0: USB Bidirectional printer dev 13 if 2 alt 0 proto 2 vid 0x0493 pid 0xB002
  $ ls -lrt /dev
  ...
  drwxr-xr-x.  2 root    root         100 Dec  5 17:44 usb
  crw-rw----.  1 root    dialout 166,   0 Dec  5 17:44 ttyACM0
  ...
  $ ls -lrt /dev/usb
  total 0
  crw-------. 1 root root 180, 96 Dec  5 16:46 hiddev0
  crw-------. 1 root root 180, 97 Dec  5 16:46 hiddev1
  crw-rw----. 1 root lp   180,  0 Dec  5 17:44 lp0
```

* send the picture to the printer:

You need to be root or in the lp group

```
  # tools/phomemo-filter.py my_picture.png > /dev/usb/lp0
```
## 2. CUPS

### 2.1. Installation

```
  $ cd cups
  $ make
  $ sudo make install
```

### 2.2. Configuration
#### 2.2.1. Bluetooth

```
  $ sudo lpadmin -p M02 -E -v serial:/dev/rfcomm0 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

Before starting to print, be sure the file /dev/rfcomm0 is present
(run "rfcomm connect" for that)

#### 2.2.2. USB

```
  $ sudo lpadmin -p M02 -E -v serial:/dev/usb/lp0 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

## 3. Protocol

### 3.1. HEADER

```
  0x1b 0x40 0x1b 0x61 0x01 0x1f 0x11 0x02 0x04
```

### 3.2. BLOCK MARKER
```
  0x1d 0x76
  0x30 0x00
  0x30 0x00 -> number of bytes in one line: 48 bytes * 8 bits = 384 points
  0xff 0x00 -> number of lines in the block (255)
```

  Values seem to be 16bit little-endian

  If the picture is not finished, a new block marker must be sent with
  the remaining number of line (max is 255).

### 3.3. FOOTER
```
  0x1b 0x64 0x02 0x1b 0x64 0x02 0x1f 0x11 0x08 0x1f 0x11 0x0e 0x1f 0x11
  0x07 0x1f 0x11 0x09
```
### 3.4. IMAGE

  Each line is 48 bytes long, each bit is a point (384 pt/line).
  size of a line is 48 mm (80 pt/cm or 203,2 dpi, as announced by Phomemo).
  ratio between height and width is 1.
  Don't send the byte "0x0a" to the printer, it breaks the rendering...
