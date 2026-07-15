#! /usr/bin/env python3

# Phomemo M04S / M04AS raster filter (300 DPI).
#
# The M04 family does not use the plain ESC/POS init the M02/M110 filters use.
# It is driven by a 1F 11 xx command space (reverse-engineered from BTSnoop HCI
# logs, tested on real hardware, see transcriptionstream/phomymo issue #23):
#   1F 11 02 <lvl>  set print density   (0x00-0x0F)
#   1F 11 37 <par>  set heat/speed
#   1F 11 0B        media type: continuous (disables gap detection)
#   1F 11 35 00     compression: raw
# The raster payload is the standard GS v 0 block (16-bit little-endian width and
# line count) and paper feed is ESC d n, so print_raster/print_and_feed are
# identical to the M02/T02 filter.

import sys, os
from collections import namedtuple
from struct import unpack

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'
US  = b'\x1f'

# M04 defaults (host density 6 of 1-8 -> level 0x0b, heat 0xb7)
DENSITY = 0x0b
HEAT    = 0xb7

# The print head sits before the tear bar, so the paper must be advanced after
# each page for the printed area to clear it. The M04 ESC d feed unit is coarse
# (not a single dot-line); 6 units was calibrated on real hardware to land the
# print at the tear bar.
TEAR_OFF_LINES = 6

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

def print_header(file, density = DENSITY, heat = HEAT):
    file.write(US + b'\x11\x02' + density.to_bytes(1, 'little')) # set density
    file.write(US + b'\x11\x37' + heat.to_bytes(1, 'little'))    # set heat/speed
    file.write(US + b'\x11\x0b')                                 # media type: continuous
    file.write(US + b'\x11\x35\x00')                             # compression: raw
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

    if header.cupsNumColors != 1:
        raise ValueError('Invalid color space, only monocolor supported')

    im = Image.frombuffer(mode='L', data=imgdata,
                          size=(header.cupsWidth, header.cupsHeight))
    im = ImageOps.invert(im)
    im = im.convert('1')

    # On a continuous roll the page height is fixed by the media, so text or a
    # short label would otherwise feed (and waste) the whole page. After the
    # invert, printed pixels are the non-zero content, so getbbox() gives the
    # bounding box of the printed area; crop off the trailing blank rows (keep
    # the full width and the top origin) so only the used height is sent.
    bbox = im.getbbox()

    line = 0
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        if bbox:
            im = im.crop((0, 0, im.width, bbox[3]))
            print_header(stdout)
            # The M04 must receive the whole page as a single GS v 0 block: it
            # ignores a raster header that appears mid-stream, so the 255-line
            # chunking used by the M02/M110 filters leaves all but the first
            # chunk unprinted. The GS v 0 line count is 16-bit, so one is enough.
            while line < im.height:
                lines = im.height - line
                if lines > 65535:
                    lines = 65535
                print_raster(stdout, im, line, lines)
                line += lines
        # Always feed, even for a wholly blank page, so a deliberate blank page
        # in a multi-page job still advances the paper instead of vanishing.
        print_and_feed(stdout, TEAR_OFF_LINES)
