srpm:
	dnf install dnf5-plugins
	dnf builddep phomemo-tools.spec
	make dist
	rpmbuild --ta phomemo-tools-2.3.tar.xz --define "_srcrpmdir $(outdir)"
