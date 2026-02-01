/*
 * rastertopm110.c - CUPS filter for Phomemo M110/M220 thermal printers
 *
 * Compile: gcc -o rastertopm110 rastertopm110.c -lcups -lcupsimage
 * Install: sudo cp rastertopm110 /usr/libexec/cups/filter/
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <cups/cups.h>
#include <cups/raster.h>

/* Printer command bytes */
#define ESC 0x1b
#define GS  0x1d

/* Debug logging to stderr (captured by CUPS) */
#define DEBUG(...) fprintf(stderr, "DEBUG: " __VA_ARGS__)

/*
 * Send printer initialization commands
 */
static void
send_header(int media_type)
{
    unsigned char cmd[4];

    /* Set speed: ESC N 0x0d <speed> */
    cmd[0] = ESC;
    cmd[1] = 0x4e;
    cmd[2] = 0x0d;
    cmd[3] = 5;  /* speed = 5 */
    fwrite(cmd, 1, 4, stdout);

    /* Set density: ESC N 0x04 <density> */
    cmd[0] = ESC;
    cmd[1] = 0x4e;
    cmd[2] = 0x04;
    cmd[3] = 10;  /* density = 10 */
    fwrite(cmd, 1, 4, stdout);

    /* Set media type: 0x1f 0x11 <type> */
    cmd[0] = 0x1f;
    cmd[1] = 0x11;
    cmd[2] = (unsigned char)media_type;
    fwrite(cmd, 1, 3, stdout);
}

/*
 * Send raster image data
 */
static void
send_raster(unsigned char *data, int width, int height)
{
    unsigned char cmd[6];
    int width_bytes = (width + 7) / 8;

    /* GS v 0 <mode> <width_lo> <width_hi> <height_lo> <height_hi> */
    cmd[0] = GS;
    cmd[1] = 'v';
    cmd[2] = '0';
    cmd[3] = 0;  /* mode = 0 (normal) */
    fwrite(cmd, 1, 4, stdout);

    /* Width in bytes (little-endian) */
    cmd[0] = width_bytes & 0xff;
    cmd[1] = (width_bytes >> 8) & 0xff;
    fwrite(cmd, 1, 2, stdout);

    /* Height in lines (little-endian) */
    cmd[0] = height & 0xff;
    cmd[1] = (height >> 8) & 0xff;
    fwrite(cmd, 1, 2, stdout);

    /* Send image data */
    fwrite(data, 1, width_bytes * height, stdout);
}

/*
 * Send footer commands
 */
static void
send_footer(void)
{
    unsigned char cmd[4];

    cmd[0] = 0x1f;
    cmd[1] = 0xf0;
    cmd[2] = 0x05;
    cmd[3] = 0x00;
    fwrite(cmd, 1, 4, stdout);

    cmd[0] = 0x1f;
    cmd[1] = 0xf0;
    cmd[2] = 0x03;
    cmd[3] = 0x00;
    fwrite(cmd, 1, 4, stdout);
}

/*
 * Convert 8-bit grayscale line to 1-bit (inverted for thermal printer)
 */
static void
convert_line_to_1bit(unsigned char *src, unsigned char *dst, int width)
{
    int x, byte_idx, bit_idx;
    int width_bytes = (width + 7) / 8;

    memset(dst, 0, width_bytes);

    for (x = 0; x < width; x++) {
        byte_idx = x / 8;
        bit_idx = 7 - (x % 8);

        /* Invert: dark pixels (low value) become 1 (print), light pixels become 0 */
        if (src[x] < 128) {
            dst[byte_idx] |= (1 << bit_idx);
        }
    }
}

/*
 * Main filter function
 */
int
main(int argc, char *argv[])
{
    cups_raster_t *ras;
    cups_page_header2_t header;
    unsigned char *line_in = NULL;
    unsigned char *line_out = NULL;
    unsigned char *page_data = NULL;
    int page = 0;
    int y;
    int width_bytes;
    int fd;

    DEBUG("rastertopm110 filter starting\n");
    DEBUG("argc=%d\n", argc);

    /* Check arguments */
    if (argc < 6 || argc > 7) {
        fprintf(stderr, "Usage: %s job user title copies options [file]\n", argv[0]);
        return 1;
    }

    /* Open raster stream */
    if (argc == 7) {
        /* Read from file */
        if ((fd = open(argv[6], O_RDONLY)) < 0) {
            perror("ERROR: Unable to open input file");
            return 1;
        }
        ras = cupsRasterOpen(fd, CUPS_RASTER_READ);
    } else {
        /* Read from stdin */
        ras = cupsRasterOpen(0, CUPS_RASTER_READ);
    }

    if (!ras) {
        fprintf(stderr, "ERROR: Unable to open raster stream\n");
        return 1;
    }

    DEBUG("Raster stream opened\n");

    /* Process pages */
    while (cupsRasterReadHeader2(ras, &header)) {
        page++;
        DEBUG("Page %d: %dx%d pixels, %d bpp, colorspace=%d, mediatype=%d\n",
              page, header.cupsWidth, header.cupsHeight,
              header.cupsBitsPerPixel, header.cupsColorSpace,
              header.cupsMediaType);

        if (header.cupsWidth == 0 || header.cupsHeight == 0) {
            DEBUG("Empty page, skipping\n");
            continue;
        }

        /* Allocate buffers */
        width_bytes = (header.cupsWidth + 7) / 8;
        line_in = malloc(header.cupsBytesPerLine);
        line_out = malloc(width_bytes);
        page_data = malloc(width_bytes * header.cupsHeight);

        if (!line_in || !line_out || !page_data) {
            fprintf(stderr, "ERROR: Unable to allocate memory\n");
            return 1;
        }

        /* Read and convert each line */
        for (y = 0; y < header.cupsHeight; y++) {
            if (cupsRasterReadPixels(ras, line_in, header.cupsBytesPerLine) == 0) {
                DEBUG("Error reading line %d\n", y);
                break;
            }

            /* Convert to 1-bit */
            convert_line_to_1bit(line_in, line_out, header.cupsWidth);

            /* Copy to page buffer */
            memcpy(page_data + (y * width_bytes), line_out, width_bytes);
        }

        DEBUG("Read %d lines, sending to printer\n", y);

        /* Send to printer */
        send_header(header.cupsMediaType ? header.cupsMediaType : 10);
        send_raster(page_data, header.cupsWidth, header.cupsHeight);
        send_footer();

        fflush(stdout);

        DEBUG("Page %d sent\n", page);

        /* Free buffers */
        free(line_in);
        free(line_out);
        free(page_data);
        line_in = line_out = page_data = NULL;
    }

    cupsRasterClose(ras);

    DEBUG("Filter complete, processed %d pages\n", page);

    return 0;
}
