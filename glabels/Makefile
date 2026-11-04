XML=phomemo-q22.xml
PHOMEMO_DIR = $(DESTDIR)/usr/share/phomemo
USER_DIR = ~/.config/libglabels/templates
USER_FILE = phomemo-q22.template

.PHONY: all install uninstall user-install user-uninstall clean

all: $(XML)

$(XML): Phomemo_Q22.template generate.sh
	./generate.sh > $(XML)

install:
	install -Dm 0644 $(XML) $(PHOMEMO_DIR)/$(XML)

uninstall:
	rm -f $(PHOMEMO_DIR)/$(XML)
	if [ -d $(PHOMEMO_DIR) ]; then rmdir --ignore-fail-on-non-empty $(PHOMEMO_DIR); fi

user-install:
	install -Dm 0644 $(XML) $(USER_DIR)/$(USER_FILE)

user-uninstall:
	rm -f $(USER_DIR)/$(USER_FILE)
	if [ -d $(USER_DIR) ]; then rmdir --ignore-fail-on-non-empty $(USER_DIR); fi

clean:
	rm -f $(XML)
