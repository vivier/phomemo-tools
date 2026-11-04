#! /usr/bin/env python3

# Phomemo M832D raster filter (300 DPI).
#
# The M832D shares the GS v 0 raster block and the ESC d feed with the M04
# family, but its setup block is a fixed sequence that also carries the
# readiness query (1F 11 08) and the vendor triple AA AB AC 02, which no other
# Phomemo model understands. Only queues using the Phomemo-M832D PPD reach this
# filter, so the model gate lives in the PPD Filter line and in the backend,
# not here.
#
# Print mode is Grayscale or Black and White, the same split the M832 driver
# offers. Grayscale uses PIL's Floyd-Steinberg by default, with Atkinson as an
# explicit choice; Black and White is a hard threshold with no dithering, and the
# threshold option applies only to that mode.
#
# Media type is Continuous by default and Black Mark (B-Line) when the PPD
# selects it, which is reported as 1F 11 26 instead of 1F 11 0B.
#
# The filter performs no Bluetooth or USB I/O: it writes the command stream on
# stdout and uses the CUPS back channel (fd 3) for the readiness reply and the
# side channel (fd 4) for the inter-page drain.

import ctypes
import ctypes.util
import os
import select
import sys
import time
from collections import namedtuple
from struct import unpack

from PIL import Image, ImageOps

ESC = b'\x1b'
GS  = b'\x1d'
US  = b'\x1f'

# M832D defaults (Darkness Default -> level 0x02, heat fixed at 0x37)
DENSITY = 0x02
HEAT = 0x37
THRESHOLD = 160

# The confirmed job/page terminator is two ESC d 2 feed commands.
READY_QUERY = US + b'\x11\x08'
FOOTER = ESC + b'd\x02' + ESC + b'd\x02'

RASTER_DPI = 300
# CUPS drain can precede mechanical output, so on USB the page-pause timer adds
# an empirical paper-settling allowance (300 dpi, 8 mm/s). This is not completion
# detection; BLE uses only the configured pause.
USB_SETTLE_MM_PER_SECOND = 8.0
USB_SETTLE_MAX_SECONDS = 60.0

DRAIN_OUTPUT = 2
SIDE_CHANNEL_OK = 1

CupsRas3 = namedtuple(
    # Documentation at https://www.cups.org/doc/spec-raster.html
    'CupsRas3',
    'MediaClass MediaColor MediaType OutputType AdvanceDistance AdvanceMedia Collate CutMedia Duplex HWResolutionH '
    'HWResolutionV ImagingBoundingBoxL ImagingBoundingBoxB ImagingBoundingBoxR ImagingBoundingBoxT '
    'InsertSheet Jog LeadingEdge MarginsL MarginsB ManualFeed MediaPosition MediaWeight MirrorPrint '
    'NegativePrint NumCopies Orientation OutputFaceUp PageSizeW PageSizeH Separations TraySwitch Tumble cupsWidth '
    'cupsHeight cupsMediaType cupsBitsPerColor cupsBitsPerPixel cupsBytesPerLine cupsColorOrder cupsColorSpace '
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
        if len(rdata) < 1796:
            raise ValueError('Truncated CUPS raster header')

        struct_data = unpack(
            '@64s 64s 64s 64s I I I I I II IIII I I I II I I I I I I I I II I I I I I I I I I I I I I '
            'I I I f ff ffff IIIIIIIIIIIIIIII ffffffffffffffff 64s 64s 64s 64s 64s 64s 64s 64s 64s 64s '
            '64s 64s 64s 64s 64s 64s 64s 64s 64s',
            rdata[0:1796]
        )
        data = [
            # Strip trailing null-bytes of strings. Header string fields are C
            # strings and may carry non-UTF-8 bytes; they are never used by this
            # filter, so decode them without raising.
            b.decode(errors='replace').rstrip('\x00') if isinstance(b, bytes) else b
            for b in struct_data
        ]
        header = CupsRas3._make(data)

        # Read image data of this page into a bytearray. cupsBytesPerLine is the
        # real row stride in the raster data stream (cupsRowStep is a driver-
        # specific value, not the data stride), so a padded row is stripped
        # rather than silently shifting every following row.
        stride = header.cupsBytesPerLine
        packed = (header.cupsWidth * header.cupsBitsPerPixel + 7) // 8
        size = stride * header.cupsHeight
        if len(rdata) < 1796 + size:
            raise ValueError('Truncated raster page')
        imgdata = rdata[1796:1796 + size]
        if stride != packed:
            imgdata = b''.join(imgdata[y * stride:y + packed]
                               for y in range(header.cupsHeight))
        pages.append((header, imgdata))

        # Remove this page from the data stream, continue with the next page
        rdata = rdata[1796 + size:]

    return pages

def parse_options(raw):
    options = {
        'density': DENSITY,
        'threshold': THRESHOLD,
        'print_mode': 'grayscale',
        'rendering': 'floyd-steinberg',
        'rotation': 0,
        'offset_x': 0,
        'offset_y': 0,
        'page_pause': 0,
    }
    values = dict(item.split('=', 1) for item in raw.split() if '=' in item)
    aliases = {'M832DDarkness': 'density', 'M832DDensity': 'density',
               'M832DThreshold': 'threshold', 'M832DPrintMode': 'print_mode',
               'M832DRendering': 'rendering',
               'M832DRotation': 'rotation', 'M832DOffsetX': 'offset_x',
               'M832DOffsetY': 'offset_y', 'M832DPagePause': 'page_pause'}
    for key, name in aliases.items():
        if key not in values:
            continue
        named = {
            ('density', 'Default'): 2, ('density', 'Fine'): 1,
            ('density', 'Medium'): 2, ('density', 'Thick'): 4,
            ('print_mode', 'Grayscale'): 'grayscale',
            ('print_mode', 'BlackWhite'): 'blackwhite',
            ('rendering', 'FloydSteinberg'): 'floyd-steinberg',
            ('rendering', 'Atkinson'): 'atkinson',
        }.get((name, values[key]))
        if named is not None:
            options[name] = named
            continue
        try:
            options[name] = int(values[key], 0)
        except ValueError:
            raise ValueError('invalid %s' % key)

    if not 0 <= options['density'] <= 15:
        raise ValueError('darkness is outside its supported range')
    if not 0 <= options['threshold'] <= 255:
        raise ValueError('threshold is outside its supported range')
    if options['print_mode'] not in ('grayscale', 'blackwhite'):
        raise ValueError('print mode must be Grayscale or BlackWhite')
    if options['rendering'] not in ('floyd-steinberg', 'atkinson'):
        raise ValueError('rendering must be FloydSteinberg or Atkinson')
    if options['rotation'] not in (0, 90, 180, 270):
        raise ValueError('rotation must be 0, 90, 180, or 270')
    if options['page_pause'] not in (0, 5, 10, 20, 30):
        raise ValueError('page pause must be 0, 5, 10, 20, or 30 seconds')
    return options

# Atkinson is the only renderer implemented here; Floyd-Steinberg comes from PIL.
# Deterministic integer error diffusion keeps Atkinson reproducible across
# platforms. Diffusion uses a fixed luminance midpoint; the configurable
# threshold applies only to the Black and White print mode, which is not dithered.
SCALE = 4096
MIDPOINT = 128 * SCALE

def round_division(value, divisor):
    # Round to nearest, with half values rounded away from zero
    if value >= 0:
        return (value + divisor // 2) // divisor
    return -((-value + divisor // 2) // divisor)

def diffuse(rows):
    # Serpentine traversal with mirrored horizontal weights
    width = len(rows[0]) if rows else 0
    current = [0] * width
    next_row = [0] * width
    next_next_row = [0] * width
    rendered = []
    for y, source in enumerate(rows):
        output = bytearray(width)
        reverse = y % 2 == 1
        positions = range(width - 1, -1, -1) if reverse else range(width)
        for x in positions:
            adjusted = source[x] * SCALE + current[x]
            black = adjusted < MIDPOINT
            output[x] = 1 if black else 0
            error = adjusted - (0 if black else 255 * SCALE)
            # Atkinson carries error two rows ahead; odd rows mirror horizontal
            # offsets.
            direction = -1 if reverse else 1
            neighbors = ((x + direction, 2), (x + 2 * direction, 2),
                         (x - direction, 2), (x, 2),
                         (x + direction, 2), (x, 2))
            targets = (current, current, next_row, next_row, next_row,
                       next_next_row)
            for target, (neighbor, weight) in zip(targets, neighbors):
                if 0 <= neighbor < width:
                    target[neighbor] += round_division(error * weight, 16)
        rendered.append(output)
        current, next_row = next_row, [0] * width
        next_row, next_next_row = next_next_row, [0] * width
    return rendered

def render(im, options):
    # Return the page as a mode '1' image where a set bit means a printed dot.
    if options['print_mode'] == 'grayscale' and \
            options['rendering'] == 'floyd-steinberg':
        return ImageOps.invert(im).convert('1')

    raw = im.tobytes()
    rows = [raw[y * im.width:(y + 1) * im.width] for y in range(im.height)]
    if options['print_mode'] == 'blackwhite':
        # Black and White is a hard threshold, like the M832 path; the
        # dithering choice does not apply to it.
        flags = [bytearray(value < options['threshold'] for value in row) for row in rows]
    else:
        flags = diffuse(rows)

    packed = bytearray()
    for row in flags:
        line = bytearray((im.width + 7) // 8)
        for x, black in enumerate(row):
            if black:
                line[x // 8] |= 0x80 >> (x % 8)
        packed.extend(line)
    return Image.frombytes('1', (im.width, im.height), bytes(packed))

def transform(im, options):
    # Positive X/Y offsets prepend unprinted pixels/rows, negative Y crops
    # leading rows. The rotation mapping matches the established M832D
    # orientation (90 clockwise). Transform runs after rendering so error
    # diffusion sees the same pixel order as the established M832D path.
    if options['offset_x'] > 0 or options['offset_y'] > 0:
        im = ImageOps.expand(im, (max(0, options['offset_x']), max(0, options['offset_y']), 0, 0), fill=0)
    if options['offset_y'] < 0:
        im = im.crop((0, -options['offset_y'], im.width, im.height))
    if options['rotation'] == 90:
        im = im.transpose(Image.Transpose.ROTATE_270)
    elif options['rotation'] == 180:
        im = im.transpose(Image.Transpose.ROTATE_180)
    elif options['rotation'] == 270:
        im = im.transpose(Image.Transpose.ROTATE_90)
    return im

MEDIA_CONTINUOUS = 0x0b
MEDIA_BLACK_MARK = 0x26

def media_type(header):
    # B-Line is the black mark stock, selected by the PPD MediaType option and
    # delivered as cupsMediaType. Rolls with no marks are reported as continuous.
    if header.cupsMediaType == MEDIA_BLACK_MARK:
        return MEDIA_BLACK_MARK
    return MEDIA_CONTINUOUS

def print_header(file, media, density = DENSITY, gate = False):
    file.write(READY_QUERY)                                     # readiness query
    if gate:
        # On BLE the query is answered on the back channel before the rest of the
        # setup is emitted. The reply only gates transmission; it does not prove
        # health or completion.
        file.flush()
        wait_ready()
    file.write(US + b'\x11\x37' + HEAT.to_bytes(1, 'little'))  # set heat/speed
    file.write(b'\xaa\xab\xac\x02')                            # vendor triple
    file.write(US + b'\x11\x02' + density.to_bytes(1, 'little'))  # set density
    file.write(US + b'\x11' + media.to_bytes(1, 'little'))    # media type
    file.write(US + b'\x11\x35\x00')                           # compression: raw
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

def print_footer(file):
    file.write(FOOTER)

def drain_output(timeout = 65.0):
    # Success means the active backend completed its output-drain operation, not
    # that paper output completed. Any other CUPS status is fatal.
    try:
        os.fstat(4)
    except OSError:
        raise RuntimeError('CUPS output drain is unavailable')
    name = ctypes.util.find_library('cups')
    if not name:
        raise RuntimeError('libcups is required for page pauses')
    lib = ctypes.CDLL(name, use_errno=True)
    lib.cupsSideChannelDoRequest.argtypes = [
        ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_double,
    ]
    lib.cupsSideChannelDoRequest.restype = ctypes.c_int
    capacity = ctypes.c_int(2048)
    buffer = ctypes.create_string_buffer(capacity.value)
    status = lib.cupsSideChannelDoRequest(DRAIN_OUTPUT, buffer, ctypes.byref(capacity), timeout)
    if status != SIDE_CHANNEL_OK:
        raise RuntimeError('CUPS output drain failed with status %d' % status)

def wait_ready(timeout = 3.0):
    # The opaque back-channel stream is searched for the observed 1a 04 response.
    # This is the bounded response currently used to gate transmission; its
    # broader status meaning is not established and it does not prove health or
    # completion.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([3], [], [], remaining)
        if not ready:
            break
        data = os.read(3, 4096)
        if not data:
            break
        if b'\x1a\x04' in data:
            return
    raise RuntimeError('M832D BLE readiness query received no 1a 04 reply')

def usb_pause_seconds(rows, page_pause):
    millimetres = rows * 25.4 / RASTER_DPI
    settling = min(USB_SETTLE_MAX_SECONDS, millimetres / USB_SETTLE_MM_PER_SECOND)
    return page_pause + settling

source = sys.stdin.buffer
if len(sys.argv) > 6 and sys.argv[-1] != '-':
    source = open(sys.argv[-1], 'rb')

pages = read_ras3(source.read())

options = parse_options(sys.argv[5] if len(sys.argv) > 5 else '')
uri = os.environ.get('DEVICE_URI', '')
# The filter performs no transport I/O, but the page-pause boundary differs: BLE
# uses only the configured pause, USB adds the empirical settling allowance.
ble = uri.split('://')[0] in ('phomemo', 'phomemo-ble')
usb = not ble

try:
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
        for i, datatuple in enumerate(pages):
            (header, imgdata) = datatuple

            if header.cupsNumColors != 1:
                raise ValueError('Invalid color space, only monocolor supported')

            mode = {1: '1', 8: 'L', 24: 'RGB', 32: 'RGBA'}.get(header.cupsBitsPerPixel)
            if mode is None:
                raise ValueError('Unsupported raster bit depth')

            im = Image.frombuffer(mode, (header.cupsWidth, header.cupsHeight), imgdata,
                                  'raw', mode, 0, 1)
            im = im.convert('L')
            im = transform(render(im, options), options)

            print_header(stdout, media_type(header), options['density'],
                         gate = (ble and i == 0))
            # The M832D takes the whole page as one GS v 0 block; the 16-bit line
            # count is the only reason to split.
            line = 0
            while line < im.height:
                lines = im.height - line
                if lines > 65535:
                    lines = 65535
                print_raster(stdout, im, line, lines)
                line += lines

            if i + 1 < len(pages):
                # A paused page terminates with the complete footer so the backend
                # can drain before the timer starts; an unpaused page gets only the
                # fixed inter-page feed.
                if options['page_pause']:
                    print_footer(stdout)
                else:
                    print_and_feed(stdout, 2)
                stdout.flush()
                if options['page_pause']:
                    drain_output()
                    pause = usb_pause_seconds(im.height, options['page_pause']) if usb \
                        else options['page_pause']
                    time.sleep(pause)

        print_footer(stdout)
except (OSError, RuntimeError, ValueError) as err:
    print('rastertom832d: %s' % err, file=sys.stderr)
    exit(1)
finally:
    if source is not sys.stdin.buffer:
        source.close()
