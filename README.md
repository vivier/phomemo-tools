# Phomemo-tools

This package is trying to provide tools to print pictures onto
the Phomemo M02 thermal printer from Linux.

All the information here has been reverse-engineered sniffing
the bluetooth packets emitted by the Android application.

## 1. Usage

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

## 2. Protocol

### 2.1. HEADER

```
  0x1b 0x40 0x1b 0x61 0x01 0x1f 0x11 0x02 0x04
```

### 2.2. BLOCK MARKER
```
  0x1d 0x76
  0x30 0x00
  0x30 0x00 -> number of bytes in one line: 48 bytes * 8 bits = 384 points
  0xff 0x00 -> number of lines in the block (255)
```

  Values seem to be 16bit little-endian

  If the picture is not finished, a new block marker must be sent with
  the remaining number of line (max is 255).

### 2.3. FOOTER
```
  0x1b 0x64 0x02 0x1b 0x64 0x02 0x1f 0x11 0x08 0x1f 0x11 0x0e 0x1f 0x11
  0x07 0x1f 0x11 0x09
```
### 2.4. IMAGE

  Each line is 48 bytes long, each bit is a point (384 pt/line).
  size of a line is 48 mm (80 pt/cm or 203,2 dpi, as announced by Phomemo).
  ratio between height and width is 1.
  Don't send the byte "0x0a" to the printer, it breaks the rendering...
