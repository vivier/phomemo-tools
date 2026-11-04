PHOMEMO_DIR = $(DESTDIR)/usr/share/phomemo

FILES = phomemo-filter.py
FILES += format-checker.py

.PHONY: all install uninstall

all:

install:
	for f in $(FILES); do install -D $$f $(PHOMEMO_DIR)/$$f; done

uninstall:
	for f in $(FILES); do rm -f $(PHOMEMO_DIR)/$$f; done
	if [ -d $(PHOMEMO_DIR) ]; then rmdir --ignore-fail-on-non-empty $(PHOMEMO_DIR); fi
