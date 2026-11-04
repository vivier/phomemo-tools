CUPS_DATADIR = $(DESTDIR)/usr/share/cups
CUPS_LIBDIR = $(DESTDIR)/usr/lib/cups

DRVFILES = phomemo-m02_t02.drv
DRVFILES += phomemo-m02pro.drv
DRVFILES += phomemo-m110.drv
DRVFILES += phomemo-d30.drv
DRVFILES += phomemo-m421.drv
DRVFILES += phomemo-m04.drv
DRVFILES += phomemo-m832.drv
DRVFILES += phomemo-m832d.drv

PPDFILES = Phomemo-M02.ppd.gz
PPDFILES += Phomemo-M02Pro.ppd.gz
PPDFILES += Phomemo-M02S.ppd.gz
PPDFILES += Phomemo-T02.ppd.gz
PPDFILES += Phomemo-D30.ppd.gz
PPDFILES += Phomemo-M04S.ppd.gz
PPDFILES += Phomemo-M04AS.ppd.gz
PPDFILES += Phomemo-M832.ppd.gz
PPDFILES += Phomemo-M832D.ppd.gz
PPDFILES += Phomemo-M110.ppd.gz
PPDFILES += Phomemo-M120.ppd.gz
PPDFILES += Phomemo-M220.ppd.gz
PPDFILES += Phomemo-M421.ppd.gz

FILTERS = rastertopm02_t02
FILTERS += rastertopm110
FILTERS += rastertopd30
FILTERS += rastertopm04
FILTERS += rastertopm832
FILTERS += rastertopm832d

BACKENDS = phomemo
BACKENDS += phomemo-ble

.PHONY: all ppds install uninstall

all: ppds

ppds:
	LC_ALL=C ppdc -z drv/*

install:
	for f in $(DRVFILES); do install -D drv/$$f $(CUPS_DATADIR)/drv/$$f; done
	for f in $(PPDFILES); do install -D ppd/$$f $(CUPS_DATADIR)/model/Phomemo/$$f; done
	for f in $(FILTERS); do install -Dm 755 filter/$$f.py $(CUPS_LIBDIR)/filter/$$f; done
	for f in $(BACKENDS); do install -Dm 755 backend/$$f.py $(CUPS_LIBDIR)/backend/$$f; done

uninstall:
	for f in $(DRVFILES); do rm -f $(CUPS_DATADIR)/drv/$$f; done
	for f in $(PPDFILES); do rm -f $(CUPS_DATADIR)/model/Phomemo/$$f; done
	for f in $(FILTERS); do rm -f $(CUPS_LIBDIR)/filter/$$f; done
	for f in $(BACKENDS); do rm -f $(CUPS_LIBDIR)/backend/$$f; done
	if [ -d $(CUPS_DATADIR)/model/Phomemo ]; then rmdir --ignore-fail-on-non-empty $(CUPS_DATADIR)/model/Phomemo; fi
