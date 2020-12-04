all: ppds

ppds:
	LC_ALL=C ppdc -z drv/*

install:
	install -D drv/phomemo-m02.drv -t $(DESTDIR)/usr/share/cups/drv/
	install -D ppd/Phomemo-M02.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -Dm 755 rastertopm02.py $(DESTDIR)/usr/lib/cups/filter/rastertopm02
