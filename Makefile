NAME = phomemo-tools
VERSION = 2.3

PHOMEMO_DIR = $(DESTDIR)/usr/share/phomemo

PHOMEMO_FILES = README.md
PHOMEMO_FILES += LICENSE

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
FILES += cups/filter/rastertopm04.py
FILES += cups/filter/rastertopm832.py
FILES += cups/filter/rastertopm832d.py
FILES += cups/backend/phomemo.py
FILES += cups/backend/phomemo-ble.py
FILES += cups/drv/phomemo-m02_t02.drv
FILES += cups/drv/phomemo-m02pro.drv
FILES += cups/drv/phomemo-m110.drv
FILES += cups/drv/phomemo-d30.drv
FILES += cups/drv/phomemo-m421.drv
FILES += cups/drv/phomemo-m04.drv
FILES += cups/drv/phomemo-m832.drv
FILES += cups/drv/phomemo-m832d.drv
FILES += glabels/generate.sh
FILES += glabels/Makefile
FILES += glabels/Phomemo_Q22.template

.PHONY: all install uninstall clean dist rpm

all:
	make -C cups
	make -C glabels

install:
	for f in $(PHOMEMO_FILES); do install -Dm 0644 $$f $(PHOMEMO_DIR)/$$f; done
	cp -a images $(PHOMEMO_DIR)/
	make -C tools install
	make -C cups install
	make -C glabels install

uninstall:
	for f in $(PHOMEMO_FILES); do rm -f $(PHOMEMO_DIR)/$$f; done
	rm -rf $(PHOMEMO_DIR)/images
	make -C tools uninstall
	make -C cups uninstall
	make -C glabels uninstall
	if [ -d $(PHOMEMO_DIR) ]; then rmdir --ignore-fail-on-non-empty $(PHOMEMO_DIR); fi
	@echo "Note: existing CUPS queues are not removed; use 'sudo lpadmin -x <name>'."
	@echo "Note: RPM installs should use 'sudo dnf remove phomemo-tools'."

dist:
	tar Jcvf $(NAME)-$(VERSION).tar.xz --xform "s/^/$(NAME)-$(VERSION)\//" $(FILES)

clean:
	rm -fr $(NAME)-$(VERSION).tar.xz
	rm -fr cups/ppd

rpm: all dist
	rpmbuild --ta $(NAME)-$(VERSION).tar.xz
