XML=phomemo-q22.xml

all: $(XML)

$(XML): Phomemo_Q22.template generate.sh
	./generate.sh > $(XML)

install:
	install -Dm 0644 $(XML) -t $(DESTDIR)/usr/share/phomemo/

user-install:
	install -Dm 0644 $(XML) ~/.config/libglabels/templates/phomemo-q22.template

clean:
	rm -f $(XML)
