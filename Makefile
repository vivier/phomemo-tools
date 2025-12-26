NAME = phomemo-tools
VERSION = 2.3

FILES = Makefile
FILES += phomemo-tools.spec
FILES += LICENSE
FILES += README.md
FILES += images
FILES += tools/Makefile
FILES += tools/format-checker.py
FILES += tools/phomemo-filter.py
FILES += cups/Makefile
FILES += cups/README.md
FILES += cups/filter/rastertopm02_t02.py
FILES += cups/filter/rastertopm110.py
FILES += cups/filter/rastertopd30.py
FILES += cups/backend/phomemo.py
FILES += cups/drv/phomemo-m02_t02.drv
FILES += cups/drv/phomemo-m02pro.drv
FILES += cups/drv/phomemo-m110.drv
FILES += cups/drv/phomemo-d30.drv
FILES += cups/drv/phomemo-m220.drv
FILES += cups/drv/phomemo-m421.drv
FILES += glabels/generate.sh
FILES += glabels/Makefile
FILES += glabels/Phomemo_Q22.template

all:
	make -C cups
	make -C glabels

install:
	install -Dm 0644 README.md -t $(DESTDIR)/usr/share/phomemo/
	install -Dm 0644 LICENSE -t $(DESTDIR)/usr/share/phomemo/
	cp -a images $(DESTDIR)/usr/share/phomemo/
	make -C tools install
	make -C cups install
	make -C glabels install

dist:
	tar Jcvf $(NAME)-$(VERSION).tar.xz --xform "s/^/$(NAME)-$(VERSION)\//" $(FILES)

clean:
	rm -fr $(NAME)-$(VERSION).tar.xz
	rm -fr cups/ppd

rpm: all dist
	rpmbuild --ta $(NAME)-$(VERSION).tar.xz
