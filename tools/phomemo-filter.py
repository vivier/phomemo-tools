#! /usr/bin/python3

import getopt, sys, os

from PIL import Image

def print_header():
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1b\x40\x1b\x61\x01\x1f\x11\x02\x04')
    return

def print_marker(lines=0x100):
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(0x761d.to_bytes(2, 'little'))
        stdout.write(0x0030.to_bytes(2, 'little'))
        stdout.write(0x0030.to_bytes(2, 'little'))
        stdout.write((lines - 1).to_bytes(2, 'little'))
    return

def print_footer():
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        stdout.write(b'\x1b\x64\x02')
        stdout.write(b'\x1b\x64\x02')
        stdout.write(b'\x1f\x11\x08')
        stdout.write(b'\x1f\x11\x0e')
        stdout.write(b'\x1f\x11\x07')
        stdout.write(b'\x1f\x11\x09')
    return

def print_line(image, line):
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        for x in range(int(image.width / 8)):
            byte = 0
            for bit in range(8):
                if image.getpixel((x * 8 + bit, line)) == 0:
                    byte |= 1 << (7 - bit)
            # 0x0a breaks the rendering
            # 0x0a alone is processed like LineFeed by the printe
            if byte == 0x0a:
                byte = 0x14
            stdout.write(byte.to_bytes(1, 'little'))
    return

def usage():
    print("%s [-h|--help] filename" % (sys.argv[0]))
    return

try:
    opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
except getopt.error as err:
    print (str(err))
    usage()
    sys.exit(1)

for opt, arg in opts:
    if opt in ("-h", "--help"):
        usage()
        sys.exit()

try:
    name = sys.argv[1]
except:
    print("Missing filename")
    usage()
    sys.exit(1)

try:
    image = Image.open(name)
except:
    print("Cannot open file %s" % (name))
    usage()
    sys.exit(2)

if image.width > image.height:
    image = image.transpose(Image.ROTATE_90)

# width 384 dots
image = image.resize(size=(384, int(image.height * 384 / image.width)))

# black&white printer: dithering
image = image.convert(mode='1')

remaining = image.height
line=0
print_header()
while remaining > 0:
    lines = remaining
    if lines > 256:
        lines = 256
    print_marker(lines)
    remaining -= lines
    while lines > 0:
        print_line(image, line)
        lines -= 1
        line += 1
print_footer()
