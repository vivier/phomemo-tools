#! /usr/bin/python3

import getopt
import os
import sys

from PIL import Image


def log(line):
    sys.stderr.write(line + "\n")


def write(data):
    wrote = sys.stdout.buffer.write(data)
    if wrote != len(data):
        log(f"ERROR writing {data}")


def print_header():
    write(b'\x1b\x40\x1b\x61\x01\x1f\x11\x02\x04')


def print_marker(lines=0x100):
    write(0x761d.to_bytes(2, 'little'))
    write(0x0030.to_bytes(2, 'little'))
    write(0x0030.to_bytes(2, 'little'))
    write((lines - 1).to_bytes(2, 'little'))


def print_footer():
    write(b'\x1b\x64\x02')
    write(b'\x1b\x64\x02')
    write(b'\x1f\x11\x08')
    write(b'\x1f\x11\x0e')
    write(b'\x1f\x11\x07')
    write(b'\x1f\x11\x09')


def print_line(image, line):
    data = bytearray()
    for x in range(int(image.width / 8)):
        byte = 0
        for bit in range(8):
            if image.getpixel((x * 8 + bit, line)) == 0:
                byte |= 1 << (7 - bit)
        # 0x0a breaks the rendering
        # 0x0a alone is processed like LineFeed by the printer
        if byte == 0x0a:
            byte = 0x14
        data.append(byte)
    write(data)


def usage():
    print("%s [-h|--help] filename" % (sys.argv[0]))
    return

try:
    opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
except getopt.error as err:
    print(str(err))
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

log(f"Opened image of size {image.width}×{image.height}")

# width 384 dots
image = image.resize(size=(384, int(image.height * 384 / image.width)))

log(f"Resized the image is {image.width}×{image.height}.")

# black&white printer: dithering
image = image.convert(mode='1')
image.save("out.png")

remaining = image.height
line=0
log("Sending header")
print_header()
while remaining > 0:
    lines = remaining
    if lines > 256:
        lines = 256
    log(f"Sending {lines} lines...")
    print_marker(lines)
    remaining -= lines
    while lines > 0:
        print_line(image, line)
        lines -= 1
        line += 1
print_footer()
