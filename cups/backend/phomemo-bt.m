/*
 * phomemo-bt - CUPS backend for Phomemo Bluetooth printers on macOS
 *
 * Compile:
 *   clang -o phomemo-bt phomemo-bt.m -framework Foundation -framework IOBluetooth
 *
 * Install:
 *   sudo cp phomemo-bt /usr/libexec/cups/backend/
 *   sudo chmod 755 /usr/libexec/cups/backend/phomemo-bt
 */

#import <Foundation/Foundation.h>
#import <IOBluetooth/IOBluetooth.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DEBUG(...) fprintf(stderr, "DEBUG: " __VA_ARGS__)

/* RFCOMM Channel Delegate */
@interface RFCOMMDelegate : NSObject <IOBluetoothRFCOMMChannelDelegate>
@property (nonatomic, assign) BOOL isOpen;
@property (nonatomic, assign) BOOL isClosed;
@property (nonatomic, assign) IOReturn lastError;
@end

@implementation RFCOMMDelegate

- (void)rfcommChannelOpenComplete:(IOBluetoothRFCOMMChannel *)channel status:(IOReturn)status {
    if (status == kIOReturnSuccess) {
        self.isOpen = YES;
        DEBUG("Channel opened successfully\n");
    } else {
        self.lastError = status;
        DEBUG("Channel open failed: %d\n", status);
    }
}

- (void)rfcommChannelClosed:(IOBluetoothRFCOMMChannel *)channel {
    self.isClosed = YES;
    self.isOpen = NO;
    DEBUG("Channel closed\n");
}

- (void)rfcommChannelWriteComplete:(IOBluetoothRFCOMMChannel *)channel refcon:(void *)refcon status:(IOReturn)status {
    if (status != kIOReturnSuccess) {
        self.lastError = status;
        DEBUG("Write failed: %d\n", status);
    }
}

@end

/* List paired Phomemo printers */
void list_devices(void) {
    @autoreleasepool {
        NSArray *paired = [IOBluetoothDevice pairedDevices];

        if (!paired || [paired count] == 0) {
            DEBUG("No paired devices found\n");
            return;
        }

        for (IOBluetoothDevice *device in paired) {
            NSString *name = [device name];
            if (!name) continue;

            /* Check if it looks like a Phomemo printer */
            NSString *upperName = [name uppercaseString];
            BOOL isPhomemo = NO;
            NSString *model = @"Phomemo";

            NSArray *patterns = @[@"M02", @"M110", @"M120", @"M220", @"M421", @"T02", @"D30"];
            for (NSString *pattern in patterns) {
                if ([upperName containsString:pattern]) {
                    isPhomemo = YES;
                    model = pattern;
                    break;
                }
            }

            /* Also check for serial number pattern */
            if (!isPhomemo) {
                NSRegularExpression *regex = [NSRegularExpression
                    regularExpressionWithPattern:@"^[A-Z]\\d{3}[A-Z]\\d{2}[A-Z]\\d+$"
                    options:0 error:nil];
                if ([regex numberOfMatchesInString:name options:0
                     range:NSMakeRange(0, [name length])] > 0) {
                    isPhomemo = YES;
                }
            }

            if (isPhomemo) {
                NSString *address = [device addressString];
                /* CUPS device line format:
                 * device-class device-uri "make-model" "info" "device-id" */
                printf("direct phomemo-bt://%s \"%s\" \"%s (%s)\" \"\"\n",
                       [address UTF8String],
                       [model UTF8String],
                       [name UTF8String],
                       [address UTF8String]);
            }
        }
    }
}

/* Send data to printer via Bluetooth */
int print_job(const char *uri, int fd) {
    @autoreleasepool {
        DEBUG("Print job starting, URI: %s\n", uri);

        /* Parse Bluetooth address from URI: phomemo-bt://XX-XX-XX-XX-XX-XX */
        const char *addr_start = strstr(uri, "://");
        if (!addr_start) {
            fprintf(stderr, "ERROR: Invalid URI format\n");
            return 1;
        }
        addr_start += 3;

        NSString *address = [NSString stringWithUTF8String:addr_start];
        DEBUG("Connecting to: %s\n", [address UTF8String]);

        /* Get device */
        IOBluetoothDevice *device = [IOBluetoothDevice deviceWithAddressString:address];
        if (!device) {
            fprintf(stderr, "ERROR: Could not find device %s\n", [address UTF8String]);
            return 1;
        }

        /* Create delegate */
        RFCOMMDelegate *delegate = [[RFCOMMDelegate alloc] init];

        /* Open RFCOMM channel */
        IOBluetoothRFCOMMChannel *channel = nil;
        IOReturn result = [device openRFCOMMChannelSync:&channel
                                          withChannelID:1
                                               delegate:delegate];

        if (result != kIOReturnSuccess) {
            fprintf(stderr, "ERROR: Failed to open RFCOMM channel: %d\n", result);
            return 1;
        }

        /* Wait for channel to open */
        NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:10.0];
        while (!delegate.isOpen && delegate.lastError == 0) {
            [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                     beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
            if ([[NSDate date] compare:deadline] == NSOrderedDescending) {
                fprintf(stderr, "ERROR: Connection timeout\n");
                [channel closeChannel];
                return 1;
            }
        }

        if (!delegate.isOpen) {
            fprintf(stderr, "ERROR: Channel not open\n");
            [channel closeChannel];
            return 1;
        }

        /* Small delay to stabilize connection */
        usleep(500000);

        fprintf(stderr, "STATE: +sending-data\n");

        /* Read and send data in chunks */
        uint8_t buffer[512];
        ssize_t bytes_read;
        size_t total_sent = 0;

        while ((bytes_read = read(fd, buffer, sizeof(buffer))) > 0) {
            result = [channel writeSync:buffer length:(UInt16)bytes_read];
            if (result != kIOReturnSuccess) {
                fprintf(stderr, "ERROR: Write failed: %d\n", result);
                [channel closeChannel];
                return 1;
            }
            total_sent += bytes_read;
            usleep(10000); /* Small delay between chunks */
        }

        DEBUG("Sent %zu bytes\n", total_sent);

        /* Close channel */
        [channel closeChannel];

        fprintf(stderr, "STATE: +cups-waiting-for-job-completed\n");
        DEBUG("Print job complete\n");

        return 0;
    }
}

int main(int argc, char *argv[]) {
    /* No arguments = discovery mode */
    if (argc == 1) {
        list_devices();
        return 0;
    }

    /* With arguments = print job */
    /* CUPS calls: backend job-id user title copies options [file] */
    if (argc < 6) {
        fprintf(stderr, "Usage: %s job-id user title copies options [file]\n", argv[0]);
        return 1;
    }

    const char *device_uri = getenv("DEVICE_URI");
    if (!device_uri) {
        fprintf(stderr, "ERROR: DEVICE_URI not set\n");
        return 1;
    }

    int input_fd = 0; /* stdin */
    if (argc > 6) {
        input_fd = open(argv[6], O_RDONLY);
        if (input_fd < 0) {
            perror("ERROR: Cannot open input file");
            return 1;
        }
    }

    int result = print_job(device_uri, input_fd);

    if (argc > 6) {
        close(input_fd);
    }

    return result;
}
