all: ppds

ppds:
	LC_ALL=C ppdc -z drv/*

install:
	mkdir -p /usr/share/cups/model/Phomemo
	cp -pr drv/* /usr/share/cups/drv/
	cp -pr ppd/* /usr/share/cups/model/Phomemo
	install -Dm 755 rastertopm02.py /usr/lib/cups/filter/rastertopm02
