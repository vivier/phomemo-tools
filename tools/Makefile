all:

version:
ifdef PHOMEMO_VERSION
	sed -e "s/@@VERSION@@/$(PHOMEMO_VERSION)/g" -i phomemo-filter.py
endif

install:
	install -D phomemo-filter.py -t $(DESTDIR)/usr/share/phomemo/
	install -D format-checker.py -t $(DESTDIR)/usr/share/phomemo/
