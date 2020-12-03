#! /usr/bin/python3

import sys, os
from PIL import Image

image = Image.new('1', (384, 2048))

with os.fdopen(sys.stdin.fileno(), "rb", closefd=False) as stdin:
    # HEADER
    assert stdin.read(1) == b'\x1b'
    assert stdin.read(1) == b'\x40'
    assert stdin.read(1) == b'\x1b'
    assert stdin.read(1) == b'\x61'
    assert stdin.read(1) == b'\x01'
    assert stdin.read(1) == b'\x1f'
    assert stdin.read(1) == b'\x11'
    assert stdin.read(1) == b'\x02'
    assert stdin.read(1) == b'\x04'

    block = 0
    line=0
    while 1:
        tag = stdin.read(1)
        if tag == b'\x1b' or tag == b'':
            break
        assert tag == b'\x1d'
        assert stdin.read(1) == b'\x76'
        assert int.from_bytes(stdin.read(2), "little") == 0x0030
        assert int.from_bytes(stdin.read(2), "little") == 0x0030
        lines = int.from_bytes(stdin.read(2), "little") + 1
        assert lines != 0
        print("Block %d has %d lines" %(block, lines))
        while lines:
            for bytes in range(48):
                byte = int.from_bytes(stdin.read(1), 'little');
                assert byte != 0x0a
                for bit in range(8):
                    value = (1 - (byte >> (7 - bit) & 1)) * 255
                    image.putpixel((bytes * 8 + bit, line), value)
            lines -= 1
            line += 1
            if line >= image.height:
                break;
        if line >= image.height:
            break;
        block += 1
    
    # footer
    if tag == b'\x1b':
        assert stdin.read(1) == b'\x64'
        assert stdin.read(1) == b'\x02'

        assert stdin.read(1) == b'\x1b'
        assert stdin.read(1) == b'\x64'
        assert stdin.read(1) == b'\x02'

        assert stdin.read(1) == b'\x1f'
        assert stdin.read(1) == b'\x11'
        assert stdin.read(1) == b'\x08'

        assert stdin.read(1) == b'\x1f'
        assert stdin.read(1) == b'\x11'
        assert stdin.read(1) == b'\x0e'

        assert stdin.read(1) == b'\x1f'
        assert stdin.read(1) == b'\x11'
        assert stdin.read(1) == b'\x07'

        assert stdin.read(1) == b'\x1f'
        assert stdin.read(1) == b'\x11'
        assert stdin.read(1) == b'\x09'

image = image.crop((0, 0, image.width, line))
image.save('image-checker.png')
image.show()
