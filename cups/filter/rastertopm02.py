#! /usr/bin/env python3

import sys, os
from collections import namedtuple
from struct import unpack

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'

CupsRas3 = namedtuple(
    # Documentation at https://www.cups.org/doc/spec-raster.html
    'CupsRas3',
    'MediaClass MediaColor MediaType OutputType AdvanceDistance AdvanceMedia Collate CutMedia Duplex HWResolutionH '
    'HWResolutionV ImagingBoundingBoxL ImagingBoundingBoxB ImagingBoundingBoxR ImagingBoundingBoxT '
    'InsertSheet Jog LeadingEdge MarginsL MarginsB ManualFeed MediaPosition MediaWeight MirrorPrint '
    'NegativePrint NumCopies Orientation OutputFaceUp PageSizeW PageSizeH Separations TraySwitch Tumble cupsWidth '
    'cupsHeight cupsMediaType cupsBitsPerColor cupsBitsPerPixel cupsBitsPerLine cupsColorOrder cupsColorSpace '
    'cupsCompression cupsRowCount cupsRowFeed cupsRowStep cupsNumColors cupsBorderlessScalingFactor cupsPageSizeW '
    'cupsPageSizeH cupsImagingBBoxL cupsImagingBBoxB cupsImagingBBoxR cupsImagingBBoxT cupsInteger1 cupsInteger2 '
    'cupsInteger3 cupsInteger4 cupsInteger5 cupsInteger6 cupsInteger7 cupsInteger8 cupsInteger9 cupsInteger10 '
    'cupsInteger11 cupsInteger12 cupsInteger13 cupsInteger14 cupsInteger15 cupsInteger16 cupsReal1 cupsReal2 '
    'cupsReal3 cupsReal4 cupsReal5 cupsReal6 cupsReal7 cupsReal8 cupsReal9 cupsReal10 cupsReal11 cupsReal12 '
    'cupsReal13 cupsReal14 cupsReal15 cupsReal16 cupsString1 cupsString2 cupsString3 cupsString4 cupsString5 '
    'cupsString6 cupsString7 cupsString8 cupsString9 cupsString10 cupsString11 cupsString12 cupsString13 cupsString14 '
    'cupsString15 cupsString16 cupsMarkerType cupsRenderingIntent cupsPageSizeName'
)

def read_ras3(rdata):
    if not rdata:
        raise ValueError('No data received')

    # Check for magic word (either big-endian or little-endian)
    magic = unpack('@4s', rdata[0:4])[0]
    if magic != b'RaS3' and magic != b'3SaR':
        raise ValueError("This is not in RaS3 format")
    rdata = rdata[4:]  # Strip magic word
    pages = []

    while rdata:  # Loop over all pages
        struct_data = unpack(
            '@64s 64s 64s 64s I I I I I II IIII I I I II I I I I I I I I II I I I I I I I I I I I I I '
            'I I I f ff ffff IIIIIIIIIIIIIIII ffffffffffffffff 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s '
            '64s 64s 64s 64s 64s 64s 64s 64s 64s',
            rdata[0:1796]
        )
        data = [
            # Strip trailing null-bytes of strings
            b.decode().rstrip('\x00') if isinstance(b, bytes) else b
            for b in struct_data
        ]
        header = CupsRas3._make(data)

        # Read image data of this page into a bytearray
        imgdata = rdata[1796:1796 + (header.cupsWidth * header.cupsHeight * header.cupsBitsPerPixel // 8)]
        pages.append((header, imgdata))

        # Remove this page from the data stream, continue with the next page
        rdata = rdata[1796 + (header.cupsWidth * header.cupsHeight * header.cupsBitsPerPixel // 8):]

    return pages

def printer_init(file):
    file.write(ESC + b'@') # initialize printer
    return

def select_justification(file, justification = 1):
    file.write(ESC + b'a') # select justification
    file.write(justification.to_bytes(1, 'little'))
    return

def print_header(file):
    printer_init(file)
    select_justification(file, 1)
    return

def print_raster(file, image, line, lines = 0xff, mode = 0):
    file.write(GS + b'v0')   # GS v 0 : print raster bit image
    # 0: normal, 1 double width, 2 double heigh, 3 quadruple
    file.write(mode.to_bytes(1, 'little'))
    # number of bytes / line
    file.write(int((image.width + 7) / 8).to_bytes(2, 'little'))
    # nulber of lines in the image
    file.write(lines.to_bytes(2, 'little'))
    # bit image
    block = image.crop((0, line, image.width, line + lines))
    stdout.write(block.tobytes())
    return

def print_and_feed(file, lines = 1):
    file.write(ESC + b'd') # print and feed
    file.write(lines.to_bytes(1, 'little'))

pages = read_ras3(sys.stdin.buffer.read())

for i, datatuple in enumerate(pages):
    (header, imgdata) = datatuple

    if header.cupsColorSpace != 0 or header.cupsNumColors != 1:
        raise ValueError('Invalid color space, only monocolor supported')

    im = Image.frombuffer(mode='L', data=imgdata,
                          size=(header.cupsWidth, header.cupsHeight))
    im = ImageOps.invert(im)
    im = im.convert('1')

    line = 0
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        print_header(stdout)
        while line < im.height:
            lines = im.height - line
            if lines > 255:
                lines = 255
            print_raster(stdout, im, line, lines)
            line += lines
        print_and_feed(stdout, 2)
