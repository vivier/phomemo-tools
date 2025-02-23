all: ppds

ppds:
	LC_ALL=C ppdc -z drv/*

install:
	install -D drv/phomemo-m02_t02.drv -t $(DESTDIR)/usr/share/cups/drv/
	install -D ppd/Phomemo-M02.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -D ppd/Phomemo-T02.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -D ppd/Phomemo-D30.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -D drv/phomemo-m110.drv -t $(DESTDIR)/usr/share/cups/drv/
	install -D drv/phomemo-m220.drv -t $(DESTDIR)/usr/share/cups/drv/
	install -D drv/phomemo-d30.drv -t $(DESTDIR)/usr/share/cups/drv/
	install -D ppd/Phomemo-M110.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -D ppd/Phomemo-M220.ppd.gz -t $(DESTDIR)/usr/share/cups/model/Phomemo
	install -Dm 755 filter/rastertopm02_t02.py $(DESTDIR)/usr/lib/cups/filter/rastertopm02_t02
	install -Dm 755 filter/rastertopm110.py $(DESTDIR)/usr/lib/cups/filter/rastertopm110
	install -Dm 755 filter/rastertopd30.py $(DESTDIR)/usr/lib/cups/filter/rastertopd30
	install -Dm 755 backend/phomemo.py $(DESTDIR)/usr/lib/cups/backend/phomemo
