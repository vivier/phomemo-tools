# Phomemo-tools

This package is trying to provide tools to print pictures using
the Phomemo M02, M02 Pro, M02S, M110, M120, M220, T02, M832 and M832D thermal printers
from Linux.

All the information here has been reverse-engineered sniffing
the bluetooth packets emitted by the Android application.

## License

This project is licensed under the GNU General Public License v3.

Some image assets are provided under a separate license.
See images/LICENSE for details.

## 1. Usage

### 1.1. Bluetooth

* connection

```
$ bluetoothctl devices
Device DC:0D:30:90:23:C7 Mr.in_M02
$ bluetoothctl pair DC:0D:30:90:23:C7
Attempting to pair with DC:0D:30:90:23:C7
[CHG] Device DC:0D:30:90:23:C7 Connected: yes
[CHG] Device DC:0D:30:90:23:C7 Bonded: yes
[CHG] Device DC:0D:30:90:23:C7 ServicesResolved: yes
[CHG] Device DC:0D:30:90:23:C7 Paired: yes
Pairing successful
$ sudo rfcomm connect 0 DC:0D:30:90:23:C7
  Connected /dev/rfcomm0 to DC:0D:30:90:23:C7 on channel 1
  Press CTRL-C for hangup
```

The M832D is Bluetooth Low Energy only and has no RFCOMM channel, so `rfcomm`
does not apply to it. Print to it through the CUPS backend in section 2, which
selects the configured printer by the address in the queue URI, chooses the LE
bearer explicitly, and resolves the FF02 and FF03 characteristics by UUID.

* Send the picture to the printer (the python script currently only works with M02 printers):

```
  tools/phomemo-filter.py my_picture.png > /dev/rfcomm0
```

### 1.2. USB

* Plug the USB printer cable

* Check the printer is present:

```
  $ lsusb
  ...
  Bus 003 Device 013: ID 0493:b002 MAG Technology Co., Ltd
  ...
```

You can see the serial port in the dmesg and in /dev:

```
  $ dmesg
  ...
  usb 3-3.7.2: new full-speed USB device number 13 using xhci_hcd
  usb 3-3.7.2: New USB device found, idVendor=0493, idProduct=b002, bcdDevice= 3.00
  usb 3-3.7.2: New USB device strings: Mfr=1, Product=2, SerialNumber=3
  usb 3-3.7.2: Product: USB Virtual COM
  usb 3-3.7.2: Manufacturer: Nuvoton
  usb 3-3.7.2: SerialNumber: A02014090305
  cdc_acm 3-3.7.2:1.0: ttyACM0: USB ACM device
  usblp 3-3.7.2:1.2: usblp0: USB Bidirectional printer dev 13 if 2 alt 0 proto 2 vid 0x0493 pid 0xB002
  $ ls -lrt /dev
  ...
  drwxr-xr-x.  2 root    root         100 Dec  5 17:44 usb
  crw-rw----.  1 root    dialout 166,   0 Dec  5 17:44 ttyACM0
  ...
  $ ls -lrt /dev/usb
  total 0
  crw-------. 1 root root 180, 96 Dec  5 16:46 hiddev0
  crw-------. 1 root root 180, 97 Dec  5 16:46 hiddev1
  crw-rw----. 1 root lp   180,  0 Dec  5 17:44 lp0
```

* Send the picture to the printer (the python script currently only works with M02 printers):

You need to be root or in the lp group

```
  # tools/phomemo-filter.py my_picture.png > /dev/usb/lp0
```

## 2. CUPS

### 2.1. Installation

On Fedora, the `phomemo-tools` RPM is available from COPR:

```
  $ sudo dnf copr enable lvivier/phomemo-tools
  $ sudo dnf install phomemo-tools
```

On Debian you have to install cups:

```
  $ sudo apt-get update
  $ sudo apt-get install cups
```

Next you need to ensure the required dependencies are installed (if this is skipped you will see a 'Filter Failure' error when trying to print):

```
  $ sudo apt-get install python3-pil python3-usb
```

For the M832D Bluetooth Low Energy backend, also install `python3-bleak` and
`python3-dbus-fast`. They are only used for M832D queues, so the other models
work without them.

#### Ubuntu 24.04 LTS

The M832D filters and the CUPS backends have been tested and work on Ubuntu 24.04 LTS.

```
  $ sudo apt-get update
  $ sudo apt-get install cups python3-pil python3-usb python3-bleak python3-dbus-fast
```

Pairing over BLE needs BlueZ experimental mode; see section 2.2.2.1.4 for the
requirement and how to enable it.

#### Debian 13

The M832D filters and the CUPS backends have also been tested and work on Debian 13,
with the same dependencies as Ubuntu 24.04 LTS:

```
  $ sudo apt-get update
  $ sudo apt-get install cups python3-pil python3-usb python3-bleak python3-dbus-fast
```

and the same BlueZ experimental mode, enabled as described in section 2.2.2.1.4.

#### Fedora

The M832D filters and the CUPS backends have also been tested and work on Fedora, with the
same BlueZ experimental mode as Ubuntu 24.04 LTS and Debian 13, and with the Bluetooth
controller set to LE only instead of dual mode (see section 2.2.2.1.4).

What was installed for the test:

```
  $ sudo dnf install python3-pillow python3-usb python3-dbus-fast
  $ pip install bleak
```

`bleak` came from pip, `python3-bleak` being the dnf equivalent. The Debian blocks above
use the Debian spellings of the same packages, `python3-pil` and `python3-pyusb`. The
SELinux note in section 2.2.1.1 applies as before.

Finally once you are in the folder containing your copy of this repository you can build and install phomemo-tools files:

```
  $ cd cups
  $ make
  $ sudo make install
```

To remove the files installed above, run the same commands with `uninstall`
(from the repository root, or from the `cups/` directory if that is where you
installed):

```
  $ sudo make uninstall
```

If the glabels template was installed for your own user with `make user-install`,
remove it with:

```
  $ make user-uninstall
```

Uninstall only removes the files this repository installs; it does not remove the
CUPS printer queues created in section 2.2. Remove a queue with:

```
  $ sudo lpadmin -x M02
```

If phomemo-tools was installed from the COPR RPM, use the package manager instead:

```
  $ sudo dnf remove phomemo-tools
```

### 2.2. Configuration

#### 2.2.1. GUI

##### 2.2.1.1. Pre-requisite

On Fedora, SELinux seems to prevent the backend to create a bluetooth socket.
If you have such error message in your syslog:

```
localhost.localdomain cupsd[2659]: Can\'t open Bluetooth connection: [Errno 13] Permission denied
```

You might need to disable SELinux enforcement to allow the backend to run correctly:

```
  $ sudo semanage permissive -a cupsd_t
```

I didn't find a way to define correctly the SELinux rules to allow the backend
to use bluetooth socket without to change the enforcement mode
(the couple ausearch/audit2allow doesn't fix the problem).

##### 2.2.1.2. Pair the printer

1. Switch on the printer
2. Open the "Settings" window:

![Settings Menu](Pictures/Menu.png)

3. Select the "Bluetooth" Panel:

![Bluetooth Panel](Pictures/Bluetooth-1.png)

4. Select your bluetooth printer (here "Mr.in_M02"):

![Bluetooth Printer](Pictures/Bluetooth-2.png)

5. Your printer must be paired but not connected ("Disconnected"):

![Bluetooth Printer](Pictures/Bluetooth-3.png)

6. Select the "Printers" Panel:

![Printers Panel](Pictures/Printers-1.png)

You'll probably need to unlock it to be able to add a new printer.

Click on "Add a Printer...".

8. Select your printer and click on "Add":

![Printers Panel](Pictures/Printers-2.png)

9. Your printer will appear in the printers list:

![Printers Panel](Pictures/Printers-3.png)

10. Click on the settings menu of the printer and select "Printing Options":

![Printers Panel](Pictures/Printers-4.png)

11. Select "Media Size Label 50mmx70mm" and click on "Test Page":

![Printers Panel](Pictures/Printers-5.png)

12. Check the result:

![Printers Panel](Pictures/Printers-6.jpg)

#### 2.2.2. CLI

##### 2.2.2.1. Bluetooth

This definition will use the "phomemo" backend to connect to the printer:

###### 2.2.2.1.1 M02, M02 Pro, M02S

Use "Phomemo-M02.ppd.gz" for M02, "Phomemo-M02Pro.ppd.gz" for M02 Pro, and "Phomemo-M02S.ppd.gz" for M02S (same driver as M02 Pro).

```
  $ sudo lpadmin -p M02 -E -v phomemo://DC0D309023C7 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

```
  $ sudo lpadmin -p M02Pro -E -v phomemo://DC0D309023C7 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02Pro.ppd.gz
```

```
  $ sudo lpadmin -p M02S -E -v phomemo://DC0D309023C7 \
                          -P /usr/share/cups/model/Phomemo/Phomemo-M02S.ppd.gz
```

###### 2.2.2.1.2 M110, M120, M220

Use "Phomemo-M110.ppd.gz" for M110, "Phomemo-M120.ppd.gz" for M120, and "Phomemo-M220.ppd.gz" for M220 (same driver, M220 exposes w70h80).
The -p option defines the printer name. It should be changed according to the printer used.

```
  $ sudo lpadmin -p M110 -E -v phomemo://DC0D309023C7 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M110.ppd.gz
```

###### 2.2.2.1.3 M832

The M832 advertises itself as "M832" and is found by the backend's Bluetooth
discovery. Options: `MediaType` (Continuous, BLine), `Darkness` (Default, Light,
Medium, Dark) and `PrintMode` (Grayscale, BlackWhite).

```
  $ sudo lpadmin -p M832 -E -v phomemo://DC0D309023C7 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M832.ppd.gz
```

###### 2.2.2.1.4 M832D

The M832D is a Bluetooth Low Energy printer with no RFCOMM channel. BlueZ
experimental mode is required for it on Ubuntu, Debian and Fedora, because the BLE
backend needs the experimental D-Bus interfaces (the LE bearer, PreferredBearer and
ConnectDevice) to pair and connect the printer.

Set it in /etc/bluetooth/main.conf under [General]:

```
  Experimental = true
```

and restart the daemon before pairing the printer:

```
  $ sudo systemctl restart bluetooth
```

The deprecated equivalent is running bluetoothd with `--experimental`
(`/usr/libexec/bluetooth/bluetoothd` on Fedora, `/usr/lib/bluetooth/bluetoothd` on
Ubuntu): one of the two is enough, and main.conf is the persistent form. The
`experimental on` command inside bluetoothctl only affects the client and not the
daemon, so it is not sufficient on its own.

A bond created before experimental mode was enabled may have no LE bearer, so a
printer that was paired earlier has to be paired again.

In testing on Fedora, the controller needed to be set to LE only rather than dual mode. 
The backend chooses the LE bearer explicitly and never falls back to Classic Bluetooth, 
so a printer that BlueZ resolves over BR/EDR is rejected as having no LE address type. 
The bearer is chosen with ConnectDevice, or with PreferredBearer, which BlueZ only 
provisions for a public-address device. If the machine has more than one controller, 
name the LE one in the queue URI, `phomemo://DC0D309023C7?adapter=hci0`; a printer 
discovered through another adapter is refused.

Then pair the printer and define the queue with the same "phomemo" backend:

```
  $ sudo bluetoothctl pair DC:0D:30:90:23:C7
  $ sudo lpadmin -p M832D -E -v phomemo://DC0D309023C7 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M832D.ppd.gz
```

Options: `MediaType` (Continuous, BLine), `M832DDarkness` (Default, Fine, Medium,
Thick), `M832DPrintMode` (Grayscale, BlackWhite), `M832DRendering` (FloydSteinberg,
Atkinson), `M832DThreshold` (the Black and White cut-off), `M832DRotation`,
`M832DOffsetX`, `M832DOffsetY` and `M832DPagePause`. The dithering choice applies only
to Grayscale and the threshold value only to Black and White.

The backend reads the ModelName from the PPD of the job and only routes queues
whose model is in the BLE whitelist to the phomemo-ble backend; every other model
keeps the RFCOMM path unchanged. Add a model to `BLE_MODELS` in
`cups/backend/phomemo.py` to extend the whitelist. The backend can also be reached
directly with the `phomemo-ble://` scheme, and an M832D queue on a
`serial:/dev/usb/lp0` device uses the same filter over USB.

Throughput on Bluetooth is limited by the transport, not by the printer. The backend
writes in acknowledged chunks, and 182 bytes is the tested ceiling for one write (section
6.1), so every chunk waits for its ATT acknowledgement and a page costs roughly one round
trip per chunk. Time therefore grows with the amount of raster in the page, and the
effective rate falls as the media gets larger: a small label finishes in seconds while
a full page, or a cut sheet such as A4 or Letter, takes minutes. Media widths of
110 mm and less are the practical ones over Bluetooth; the same filter on a USB queue
does not have this limit.

The SELinux note above covers the RFCOMM socket. The BLE backend reaches BlueZ
over D-Bus instead, which may need a different policy; the permissive setting is
not sufficient on its own.

A successful backend exit and an ATT acknowledgement confirm that the host
delivered bytes, not that the printer physically finished the page. The backend
does not retry once data may have reached the printer.

How those bytes reach the printer, in broad strokes, is section 6.1.

##### 2.2.2.2. USB

This definition will use the /dev/usb/lp0 device to connect to the printer:

###### 2.2.2.2.1 M02, M02 Pro, M02S

Use "Phomemo-M02.ppd.gz" for M02, "Phomemo-M02Pro.ppd.gz" for M02 Pro, and "Phomemo-M02S.ppd.gz" for M02S (same driver as M02 Pro).

```
  $ sudo lpadmin -p M02 -E -v serial:/dev/usb/lp0 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
```

```
  $ sudo lpadmin -p M02Pro -E -v serial:/dev/usb/lp0 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M02Pro.ppd.gz
```

```
  $ sudo lpadmin -p M02S -E -v serial:/dev/usb/lp0 \
                          -P /usr/share/cups/model/Phomemo/Phomemo-M02S.ppd.gz
```

###### 2.2.2.2.2 M110, M120, M220

Use "Phomemo-M110.ppd.gz" for M110, "Phomemo-M120.ppd.gz" for M120, and "Phomemo-M220.ppd.gz" for M220 (same driver, M220 exposes w70h80).
The -p option defines the printer name. It should be changed according to the printer used.

```
  $ sudo lpadmin -p M110 -E -v serial:/dev/usb/lp0 \
                           -P /usr/share/cups/model/Phomemo/Phomemo-M110.ppd.gz
```

##### 2.2.2.3. Check printer options

You can use the following command to check the options for your printer which will list the printer defaults with a "*":

```
  $ lpoptions -d M02 -l
```

##### 2.2.2.4. Printing

You can use the following command to print text using CUPS:

```
  $ echo "This is test"  | lp -d M02 -o media=w50h60 -
```

You can use the following command to print an image using CUPS:

```
  $ lp -d M02 -o media=w50h60 my_picture.png
```

The M110, M120 & M220 printers have support for LabelWithGaps, Continuous and LabelWithMarks media types which can be specified as follows:

```
  $ echo "This is test"  | lp -d M110 -o media=w30h20 -o MediaType=Continuous
```

## 3. Image samples to use with the printer

They are AI generated.

They may be used, copied, modified, and redistributed freely, including for commercial purposes.

They are not claimed to be public domain and are not licensed under the GPL.

They do not have a human author in the sense of copyright law.

<img title="" src="Pictures/Stickers.jpg" alt="Stickers.jpg" data-align="center" width="401">

### 3.1. Animals

| <img src="images/animals/Penguin.png" title="" alt="" width="192">                | <img title="" src="images/animals/Cat.png" alt="Cat.png" data-align="inline" width="172"> | <img title="" src="images/animals/Dog.png" alt="Dog.png" width="172">                     |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| <img src="images/animals/Cat&Dog.png" title="" alt="Cat&Dog.png" width="202">     | <img src="images/animals/Sheep.png" title="" alt="Sheep.png" width="199">                 | <img src="images/animals/Giraffe.png" title="" alt="Giraffe.png" width="195">             |
| <img src="images/animals/Clownfish.png" title="" alt="Clownfish.png" width="192"> | <img src="images/animals/Dolphin.png" title="" alt="Dolphin.png" width="192">             | <img src="images/animals/Dog with ball.png" title="" alt="Dog with ball.png" width="192"> |
| <img src="images/animals/Hamster.png" title="" alt="Hamster.png" width="192">     | <img src="images/animals/Hedgehog.png" title="" alt="Hedgehog.png" width="192">           | <img src="images/animals/Moonfish.png" title="" alt="Moonfish.png" width="192">           |
| <img src="images/animals/Narwhal.png" title="" alt="Narwhal.png" width="192">     | <img src="images/animals/Octopus.png" title="" alt="Octopus.png" width="192">             | <img src="images/animals/Rabbit.png" title="" alt="Rabbit.png" width="192">               |
| <img src="images/animals/Red Panda.png" title="" alt="Red Panda.png" width="192"> | <img src="images/animals/Sloth.png" title="" alt="Sloth.png" width="192">                 | <img src="images/animals/Tortoise.png" title="" alt="Tortoise.png" width="192">           |

### 3.2. Astronomy

| <img src="images/astronomy/Astronaut.png" title="" alt="Astronaut.png" width="150"> | <img src="images/astronomy/Moon.png" title="" alt="Moon.png" width="150">           | <img src="images/astronomy/Observatory.png" title="" alt="Observatory.png" width="150"> | <img src="images/astronomy/Planet.png" title="" alt="Planet.png" width="150"> |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| <img src="images/astronomy/Rocket.png" title="" alt="Rocket.png" width="150">       | <img src="images/astronomy/Satellite.png" title="" alt="Satellite.png" width="150"> | <img src="images/astronomy/Telescope.png" title="" alt="Telescope.png" width="150">     | <img src="images/astronomy/UFO.png" title="" alt="UFO.png" width="150">       |

### 3.3. Birthday

<img title="" src="images/birthday/Birthday5.png" alt="Birthday5.png" width="350" data-align="center">

| <img src="images/birthday/Birthday1.png" title="" alt="Birthday1.png" width="334"> | <img src="images/birthday/Birthday2.png" title="" alt="Birthday2.png" width="340"> |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| <img src="images/birthday/Birthday3.png" title="" alt="Birthday3.png" width="341"> | <img src="images/birthday/Birthday4.png" title="" alt="Birthday4.png" width="346"> |

### 3.4. Christmas

| <img title="" src="images/christmas/Christmas1.png" alt="Christmas1.png" width="250"> | <img src="images/christmas/Christmas3.png" title="" alt="Christmas3.png" width="305"> | <img title="" src="images/christmas/Christmas5.png" alt="Christmas5.png" width="312"> |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |

| <img src="images/christmas/Christmas2.png" title="" alt="Christmas2.png" width="303"> | <img src="images/christmas/Christmas4.png" title="" alt="Christmas4.png" width="309"> |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |

| <img src="images/christmas/Christmas tree.png" title="" alt="Christmas tree.png" width="260">   | <img src="images/christmas/Elf.png" title="" alt="Elf.png" width="260">                 | <img src="images/christmas/Reindeer.png" title="" alt="Reindeer.png" width="260">             |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| <img src="images/christmas/Santa Claus.png" title="" alt="Santa Claus.png" width="260">         | <img src="images/christmas/Santa's bag.png" title="" alt="Santa's bag.png" width="260"> | <img src="images/christmas/Santa’s sleigh.png" title="" alt="Santa’s sleigh.png" width="260"> |
| <img src="images/christmas/Santa’s sleigh2.png" title="" alt="Santa’s sleigh2.png" width="260"> | <img src="images/christmas/Snowflake.png" title="" alt="Snowflake.png" width="260">     |                                                                                               |

### 3.5. Everyday

| <img src="images/everyday/Alarm Clock.png" title="" alt="Alarm Clock.png" width="180">       | <img src="images/everyday/Cleaning Tools.png" title="" alt="Cleaning Tools.png" width="180"> | <img src="images/everyday/Coffee.png" title="" alt="Coffee.png" width="180">                   |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| <img src="images/everyday/Folded Clothes.png" title="" alt="Folded Clothes.png" width="180"> | <img src="images/everyday/Gamepad.png" title="" alt="Gamepad.png" width="180">               | <img src="images/everyday/Headphone.png" title="" alt="Headphone.png" width="180">             |
| <img src="images/everyday/Iron.png" title="" alt="Iron.png" width="180">                     | <img src="images/everyday/Keys.png" title="" alt="Keys.png" width="180">                     | <img src="images/everyday/Notebook.png" title="" alt="Notebook.png" width="180">               |
| <img src="images/everyday/Shopping Cart.png" title="" alt="Shopping Cart.png" width="180">   | <img src="images/everyday/Smartphone.png" title="" alt="Smartphone.png" width="180">         | <img src="images/everyday/Toothbrush.png" title="" alt="Toothbrush.png" width="180">           |
| <img src="images/everyday/Towels.png" title="" alt="Towels.png" width="180">                 | <img src="images/everyday/Vacuum Cleaner.png" title="" alt="Vacuum Cleaner.png" width="180"> | <img src="images/everyday/Washing Machine.png" title="" alt="Washing Machine.png" width="180"> |

### 3.6. Flowers

<img title="" src="images/flowers/Bouquet.png" alt="Bouquet.png" width="300" data-align="center">

| <img src="images/flowers/Daisy.png" title="" alt="Daisy.png" width="180"> | <img src="images/flowers/Lily.png" title="" alt="Lily.png" width="180">           | <img src="images/flowers/Lily of the Valley.png" title="" alt="Lily of the Valley.png" width="180"> |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| <img src="images/flowers/Rose.png" title="" alt="Rose.png" width="180">   | <img src="images/flowers/Sunflower.png" title="" alt="Sunflower.png" width="180"> | <img src="images/flowers/Tulip.png" title="" alt="Tulip.png" width="180">                           |

### 3.7. Landscape

| <img src="images/landscape/Beach.png" title="" alt="Beach.png" width="200">       | <img src="images/landscape/Countryside.png" title="" alt="Countryside.png" width="200"> | <img src="images/landscape/Lakeside.png" title="" alt="Lakeside.png" width="200"> |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| <img src="images/landscape/Mountain.png" title="" alt="Mountain.png" width="200"> | <img src="images/landscape/River.png" title="" alt="River.png" width="200">             | <img src="images/landscape/Seascape.png" title="" alt="Seascape.png" width="200"> |

### 3.8. Objects

| <img src="images/objects/Airplane.png" title="" alt="Airplane.png" width="170"> | <img src="images/objects/Bus.png" title="" alt="Bus.png" width="170">         | <img src="images/objects/Car.png" title="" alt="Car.png" width="170">     |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| <img src="images/objects/Rocket.png" title="" alt="Rocket.png" width="170">     | <img src="images/objects/Tractor.png" title="" alt="Tractor.png" width="170"> | <img src="images/objects/Truck.png" title="" alt="Truck.png" width="170"> |

### 3.9. People

| <img src="images/people/Astronaut.png" title="" alt="Astronaut.png" width="170"> | <img src="images/people/Baker.png" title="" alt="Baker.png" width="170">       | <img src="images/people/Explorer.png" title="" alt="Explorer.png" width="170">     |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| <img src="images/people/Florist.png" title="" alt="Florist.png" width="170">     | <img src="images/people/Knight.png" title="" alt="Knight.png" width="170">     | <img src="images/people/Mechanic.png" title="" alt="Mechanic.png" width="170">     |
| <img src="images/people/Pirate.png" title="" alt="Pirate.png" width="170">       | <img src="images/people/Princess.png" title="" alt="Princess.png" width="170"> | <img src="images/people/Programmer.png" title="" alt="Programmer.png" width="170"> |
| <img src="images/people/Robot.png" title="" alt="Robot.png" width="170">         | <img src="images/people/Witch.png" title="" alt="Witch.png" width="170">       |                                                                                    |

### 3.10. Pictograms

| <img src="images/pictograms/Car.png" title="" alt="Car.png" width="120"> | <img src="images/pictograms/First Aid.png" title="" alt="First Aid.png" width="120"> | <img src="images/pictograms/Food.png" title="" alt="Food.png" width="120">         | <img src="images/pictograms/Home.png" title="" alt="Home.png" width="120">   | <img src="images/pictograms/People.png" title="" alt="People.png" width="120"> |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| <img src="images/pictograms/Pet.png" title="" alt="Pet.png" width="120"> | <img src="images/pictograms/Recycle.png" title="" alt="Recycle.png" width="120">     | <img src="images/pictograms/Shopping.png" title="" alt="Shopping.png" width="120"> | <img src="images/pictograms/Train.png" title="" alt="Train.png" width="120"> | <img src="images/pictograms/WiFi.png" title="" alt="WiFi.png" width="120">     |

### 3.11. School-Office

| <img src="images/school-office/Backpack.png" title="" alt="Backpack.png" width="170">   | <img src="images/school-office/Books.png" title="" alt="Books.png" width="170">         | <img src="images/school-office/Calendar.png" title="" alt="Calendar.png" width="170">           |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| <img src="images/school-office/Clipboard.png" title="" alt="Clipboard.png" width="170"> | <img src="images/school-office/Desk Lamp.png" title="" alt="Desk Lamp.png" width="170"> | <img src="images/school-office/Desktop PC.png" title="" alt="Desktop PC.png" width="170">       |
| <img src="images/school-office/Laptop.png" title="" alt="Laptop.png" width="170">       | <img src="images/school-office/Notebook.png" title="" alt="Notebook.png" width="170">   | <img src="images/school-office/Pencil Holder.png" title="" alt="Pencil Holder.png" width="170"> |

### 3.12. To Do

| <img src="images/todo/ToDo1.png" title="" alt="ToDo1.png" width="114"> | <img src="images/todo/ToDo2.png" title="" alt="ToDo2.png" width="114"> | <img src="images/todo/ToDo3.png" title="" alt="ToDo3.png" width="116"> | <img title="" src="images/todo/ToDo4.png" alt="ToDo4.png" width="115"> |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |

### 3.13. Tools

| <img src="images/tools/Drill.png" title="" alt="Drill.png" width="150"> | <img src="images/tools/Hammer&Wrench.png" title="" alt="Hammer&Wrench.png" width="150"> | <img src="images/tools/Painting.png" title="" alt="Painting.png" width="150"> | <img src="images/tools/Saw.png" title="" alt="Saw.png" width="150"> |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------- |

### 3.14 Frames

<img src="images/frames/Frame1.png" title="" alt="Frame1.png" data-align="center">

| ![Frame2.png](images/frames/Frame2.png) | ![Frame3.png](images/frames/Frame3.png) |
| --------------------------------------- | --------------------------------------- |
| ![Frame4.png](images/frames/Frame4.png) | ![Frame5.png](images/frames/Frame5.png) |
| ![Frame6.png](images/frames/Frame6.png) | ![Frame7.png](images/frames/Frame7.png) |

| ![Frame8.png](images/frames/Frame8.png)   | ![Frame9.png](images/frames/Frame9.png)   | ![Frame10.png](images/frames/Frame10.png) |
| ----------------------------------------- | ----------------------------------------- | ----------------------------------------- |
| ![Frame11.png](images/frames/Frame11.png) | ![Frame12.png](images/frames/Frame12.png) | ![Frame13.png](images/frames/Frame13.png) |

# 4. Protocol for M02

After dumpping bluetooth packets, it appears to be EPSON ESC/POS Commands.

### 4.1. HEADER

```
  0x1b 0x40      -> command ESC @: initialize printer
  0x1b 0x61      -> command ESC a: select justification
  0x01           range: 0 (left-justification), 1 centered,
                        2 (right justification)
  0x1f 0x11 0x02 0x04
```

### 4.2. BLOCK MARKER

```
  0x1d 0x76 0x30 -> command GS v 0 : print raster bit image
  0x00              mode: 0 (normal), 1 (double width),
                          2 (double-height), 3 (quadruple)
  0x30 0x00         16bit, little-endian: number of bytes / line (48)
  0xff 0x00         16bit, little-endian: number of lines in the image (255)
```

  Values seem to be 16bit little-endian

  If the picture is not finished, a new block marker must be sent with
  the remaining number of line (max is 255).

### 4.3. FOOTER

```
  0x1b 0x64      -> command ESC d : print and feed n lines
  0x02           number of line to feed
  0x1b 0x64      -> command ESC d : print and feed n lines
  0x02           number of line to feed
  0x1f 0x11 0x08
  0x1f 0x11 0x0e
  0x1f 0x11 0x07
  0x1f 0x11 0x09
```

### 4.4. IMAGE

  Each line is 48 bytes long, each bit is a point (384 pt/line).
  size of a line is 48 mm (80 pt/cm or 203,2 dpi, as announced by Phomemo).
  ratio between height and width is 1.

### 4.5. Printer message

```
1a 04 5a
1a 09 0c
1a 07 01 00 00
1a 08
51 30 30 31 45 30 XX XX XX XX XX XX XX XX XX -> Serial Numer: E05C0XXXXXX
```

## 5. Protocol for M110/M120/M220

Dumpping USB packets.

### 5.1. HEADER

```
  0x1b 0x4e 0x0d  -> Print Speed
  0x05            range: 0x01 (Slow) -  0x05 (Fast)
  0x1b 0x4e 0x04  -> Print Density
  0x0f            range: 01 - 0f
  0x1f  0x11      -> Media Type
  0x0a            Mode: 0a="Label With Gaps" 0b="Continuas" 26="Label With Marks"
```

### 5.2. BLOCK MARKER

```
  0x1d 0x76 0x30 -> command GS v 0 : print raster bit image
  0x00              mode: 0 (normal), 1 (double width),
                          2 (double-height), 3 (quadruple)
  0x2b 0x00         16bit, little-endian: number of bytes / line (43)
  0xf0 0x00         16bit, little-endian: number of lines in the image (240)
```

### 5.3. FOOTER

```
  0x1f 0xf0 0x05 0x00
  0x1f 0xf0 0x03 0x00
```

# 6. Protocol for M832D

The M832D uses the same GS v 0 raster block and ESC d feed as the M04 family, but its
setup block is a fixed sequence that sends the readiness query up front, where the M02
protocol in section 4.3 only sends it at the end of the job.

```
  0x1f 0x11 0x08      -> readiness query, answered by 0x1a 0x04 on the back channel
  0x1f 0x11 0x37 0x37 -> heat, fixed at 0x37
  0xaa 0xab 0xac 0x02 -> vendor triple, meaning unexplained
  0x1f 0x11 0x02      -> print density, default 0x02
  0x1f 0x11 0x0b      -> media type: continuous, or 0x26 for black mark
  0x1f 0x11 0x35 0x00 -> compression: raw
```

The image is sent as one GS v 0 block per page, with 16-bit little-endian byte
width and line count. The inter-page feed is ESC d 2 and the job footer is two
ESC d 2 commands.

The filter has two print modes. Grayscale uses PIL's Floyd-Steinberg by default, the
same dithering the other filters use, with Atkinson as an explicit choice; Black and
White is a hard threshold with no dithering, and the threshold value applies only to
that mode.

### 6.1. Bluetooth Low Energy backend

The filter performs no transport I/O: `cups/filter/rastertopm832d.py` writes the
command stream described above on stdout, and `cups/backend/phomemo-ble.py` carries
it byte-for-byte and in order to the printer. The `phomemo` backend reads ModelName
from the PPD and hands a queue in the BLE whitelist to that script with the same
arguments, environment and CUPS descriptors.

The printer is selected by the address in the queue URI, never by its advertised
name, and the LE bearer is chosen explicitly rather than by falling back to Classic
Bluetooth, as described in section 2.2.2.1.4. Pairing runs once automatically, only
when no bond exists and only for Just Works, so PIN and passkey entry are refused.

Characteristics are resolved by UUID rather than by captured ATT handles: FF02 must
support acknowledged writes and FF03 must support notifications, and both are required
before any job byte is accepted. Output goes to FF02 in chunks of at most 182 bytes,
each awaiting its ATT response, so one chunk costs one round trip. FF03 values are
forwarded raw and in callback order to the CUPS back channel (fd 3), where the filter
looks only for the `1a 04` answer to its readiness query before sending the rest of the
setup, and the side channel (fd 4) answers the page-pause drain only after every byte
produced before that request has been acknowledged. An acknowledgement proves transport
acceptance rather than a printed page, so the backend does not retry once bytes may have
reached the printer.
