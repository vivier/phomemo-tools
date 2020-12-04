NAME = phomemo-tools
VERSION = 1.0

FILES = Makefile
FILES += phomemo-tools.spec
FILES += LICENSE
FILES += README.md
FILES += tools/Makefile
FILES += tools/format-checker.py
FILES += tools/phomemo-filter.py
FILES += cups/Makefile
FILES += cups/README.md
FILES += cups/rastertopm02.py
FILES += cups/drv/phomemo-m02.drv

all:
	make -C cups

install:
	install -Dm 0644 README.md -t $(DESTDIR)/usr/share/phomemo/
	install -Dm 0644 LICENSE -t $(DESTDIR)/usr/share/phomemo/
	make -C tools install
	make -C cups install

dist:
	tar Jcvf $(NAME)-$(VERSION).tar.xz --xform "s/^/$(NAME)-$(VERSION)\//" $(FILES)

clean:
	rm -fr $(NAME)-$(VERSION).tar.xz
	rm -fr cups/ppd

rpm: all dist
	rpmbuild --ta $(NAME)-$(VERSION).tar.xz
