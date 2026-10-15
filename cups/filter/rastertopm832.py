#! /usr/bin/env python3
#
# CUPS filter for the Phomemo M832 (A4 / Letter thermal printer, 300 DPI).
#
# Command stream derived from the vendor driver (QY_Printer 2.1.0.3,
# rastertoM08F, model 77832), following the path it uses for Bluetooth
# connections, which skips all status queries.

import sys, os
from collections import namedtuple
from struct import unpack

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'

MEDIA_CONTINUOUS = 0x0b
MEDIA_BLACK_MARK = 0x26

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

    magic = unpack('@4s', rdata[0:4])[0]
    if magic != b'RaS3' and magic != b'3SaR':
        raise ValueError("This is not in RaS3 format")
    rdata = rdata[4:]
    pages = []

    while rdata:
        struct_data = unpack(
            '@64s 64s 64s 64s I I I I I II IIII I I I II I I I I I I I I II I I I I I I I I I I I I I '
            'I I I f ff ffff IIIIIIIIIIIIIIII ffffffffffffffff 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s '
            '64s 64s 64s 64s 64s 64s 64s 64s 64s',
            rdata[0:1796]
        )
        data = [
            b.decode().rstrip('\x00') if isinstance(b, bytes) else b
            for b in struct_data
        ]
        header = CupsRas3._make(data)

        size = header.cupsWidth * header.cupsHeight * header.cupsBitsPerPixel // 8
        pages.append((header, rdata[1796:1796 + size]))
        rdata = rdata[1796 + size:]

    return pages

def is_sheet(header):
    # CUPS may append a variant suffix, e.g. "Letter.Borderless"
    return header.cupsPageSizeName.split('.')[0] in ('A4', 'Letter')

def media_type(header):
    # Cut sizes only work on continuous paper; the vendor driver forces it.
    if not is_sheet(header):
        return MEDIA_CONTINUOUS
    if header.cupsMediaType == MEDIA_BLACK_MARK:
        return MEDIA_BLACK_MARK
    return MEDIA_CONTINUOUS

def print_header(file, header):
    file.write(b'\x1f\x11' + media_type(header).to_bytes(1, 'little'))
    # PPD cupsInteger0 (zero-based) arrives here as cupsInteger1
    density = header.cupsInteger1
    if density in (1, 2, 4):
        file.write(b'\x1f\x11\x02' + density.to_bytes(1, 'little'))
    file.write(b'\x1f\x11\x35\x00')   # compression off

def to_bitmap(header, imgdata):
    im = Image.frombuffer(mode='L', data=imgdata,
                          size=(header.cupsWidth, header.cupsHeight))

    if header.cupsInteger2 == 1:
        # Black & white: hard threshold, matching the vendor default level.
        return im.point(lambda p: 255 if p <= 128 else 0).convert('1', dither=Image.Dither.NONE)

    return ImageOps.invert(im).convert('1')

def print_raster(file, im):
    file.write(GS + b'v0\x00')
    file.write(((im.width + 7) // 8).to_bytes(2, 'little'))
    file.write(im.height.to_bytes(2, 'little'))
    file.write(im.tobytes())

pages = read_ras3(sys.stdin.buffer.read())
feedAfterJob = False

with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
    for header, imgdata in pages:
        if header.cupsNumColors != 1:
            raise ValueError('Invalid color space, only monocolor supported')

        print_header(stdout, header)
        print_raster(stdout, to_bitmap(header, imgdata))

        if not is_sheet(header):
            stdout.write(ESC + b'd\x01')
            feedAfterJob = True

    if feedAfterJob:
        stdout.write(ESC + b'd\x02')

    stdout.write(b'\x1f\x11\x11')   # paper status query; harmless, ends the job
