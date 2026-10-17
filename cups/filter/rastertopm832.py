#! /usr/bin/env python3

# Phomemo M832 raster filter (300 DPI).
#
# The M832 was reverse-engineered by watching the bytes the printer is fed over
# USB (0483:5740, bulk OUT 0x02) and confirmed by printing on real hardware with
# a 110 mm continuous roll.
#
# Like the M04 family it is driven by the 1F 11 xx command space, but it is sent
# no density or heat command and the stream does not simply end with an ESC d
# feed:
#   1F 11 0B                          media type: continuous
#   1F 11 35 00                       compression: raw (the M832 never packs)
#   1D 76 30 00 xL xH yL yH <bitmap>  GS v 0, one block for the whole page,
#                                     MSB first, 1 = black, no inversion
#   1B 64 01                          print and feed, after every page
#   1B 64 02                          print and feed, after the last page
#   1F 11 11                          status query, once at the end of the job;
#                                     the printer prints correctly with no reply
#                                     so nothing is ever read back
# No width is fixed here: the bytes per line are whatever CUPS hands the filter
# for the selected media, 163 bytes (1299 dots) for the 110 mm roll.
#
# A4 and Letter are cut sheets and are treated differently: the raster is padded
# with blank lines to the full sheet length instead of being cropped to the
# printed area, and the two ESC d feeds are not sent. That split was taken from
# the stream produced for those sizes and has never been run on real paper, and
# neither have the 80 mm and 53 mm rolls, which are assumed to behave like the
# 110 mm one.

import sys, os
from collections import namedtuple
from struct import unpack

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'
US  = b'\x1f'

# Cut sheets leave the printer whole, so they are padded to the full sheet
# length and get no tear-off feed.
SHEET_SIZES = ('A4', 'Letter')

# The GS v 0 line count is 16-bit.
MAX_LINES = 65535

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

def print_header(file):
    file.write(US + b'\x11\x0b')     # media type: continuous
    file.write(US + b'\x11\x35\x00') # compression: raw
    return

def print_raster(file, image, line, lines = 0xff, mode = 0):
    file.write(GS + b'v0')   # GS v 0 : print raster bit image
    # 0: normal, 1 double width, 2 double heigh, 3 quadruple
    file.write(mode.to_bytes(1, 'little'))
    # number of bytes / line
    file.write(int((image.width + 7) / 8).to_bytes(2, 'little'))
    # number of lines in this block
    file.write(lines.to_bytes(2, 'little'))
    # bit image
    block = image.crop((0, line, image.width, line + lines))
    file.write(block.tobytes())
    return

def print_and_feed(file, lines = 1):
    file.write(ESC + b'd') # print and feed
    file.write(lines.to_bytes(1, 'little'))
    return

def query_status(file):
    file.write(US + b'\x11\x11') # the answer is never read back
    return

pages = read_ras3(sys.stdin.buffer.read())

sheet = False
with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
    for i, datatuple in enumerate(pages):
        (header, imgdata) = datatuple

        if header.cupsNumColors != 1:
            raise ValueError('Invalid color space, only monocolor supported')

        # Every page of a job shares the media, so the last page decides how the
        # job is ended.
        # read_ras3()'s rstrip('\x00') only trims a trailing run of nulls; CUPS
        # has been observed to leave a stray tail from a previous, longer page
        # name after the null terminator (e.g. b'A4\x00ter', a leftover from
        # 'Letter') when a shorter name is written into the same fixed-size
        # field. Only the part before the first null is the real name.
        page_size_name = header.cupsPageSizeName.split('\x00', 1)[0]
        sheet = page_size_name in SHEET_SIZES

        im = Image.frombuffer(mode='L', data=imgdata,
                              size=(header.cupsWidth, header.cupsHeight))
        im = ImageOps.invert(im)
        im = im.convert('1')

        if sheet:
            # A sheet is ejected whole, so the page is padded to the full sheet
            # length instead of being cropped: crop() past the bottom edge fills
            # with blank lines. The count comes from the page geometry so it
            # follows the PPD (3508 lines for A4 at 300 DPI).
            height = round(header.cupsPageSizeH * header.HWResolutionV / 72)
            im = im.crop((0, 0, im.width, max(height, im.height)))
        else:
            # On a continuous roll the page height is fixed by the media, so
            # text or a short label would otherwise feed (and waste) the whole
            # page. After the invert, printed pixels are the non-zero content,
            # so getbbox() gives the bounding box of the printed area; crop off
            # the trailing blank rows (keep the full width and the top origin).
            bbox = im.getbbox()
            im = im.crop((0, 0, im.width, bbox[3] if bbox else 0))

        if im.height:
            print_header(stdout)
            # The page goes out as a single GS v 0 block; the 16-bit line count
            # only needs splitting past 65535 lines, 5.5 m at 300 DPI.
            line = 0
            while line < im.height:
                lines = im.height - line
                if lines > MAX_LINES:
                    lines = MAX_LINES
                print_raster(stdout, im, line, lines)
                line += lines

        if not sheet:
            # Advance the paper so the printed area clears the tear bar. Sent
            # even for a wholly blank page, so a deliberate blank page in a
            # multi-page job still advances the paper instead of vanishing.
            print_and_feed(stdout, 1)

    if not sheet:
        print_and_feed(stdout, 2)
    query_status(stdout)
