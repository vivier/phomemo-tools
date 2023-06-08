Name: phomemo-tools
Version: 1.0
Release: 1%{?dist}
Summary: A set of tools to use Phomemo printers on Linux
License: GPLv3

Source: %{name}-%{version}.tar.xz
BuildArch: noarch
BuildRequires: cups

Requires: cups
Requires: python3
Requires: python3-pillow
Requires: python3-pybluez
Requires: python3-pyusb

%description
This packages provides tools to send images to print on Phomemo
Thermal printers.
It also installs a CUPS driver for the printer into the system.

%prep
%setup -q

%build

make all

%install

make DESTDIR=%{buildroot} install

%files
/usr/share/phomemo/LICENSE
/usr/share/phomemo/README.md
/usr/share/phomemo/phomemo-q22.xml
/usr/share/phomemo/phomemo-filter-m02.py
/usr/share/phomemo/phomemo-filter-m02s.py
/usr/share/phomemo/format-checker.py
/usr/share/cups/model/Phomemo/Phomemo-M02.ppd.gz
/usr/share/cups/model/Phomemo/Phomemo-M02S.ppd.gz
/usr/share/cups/model/Phomemo/Phomemo-M110.ppd.gz
/usr/share/cups/model/Phomemo/Phomemo-M120.ppd.gz
/usr/share/cups/drv/phomemo-m02.drv
/usr/share/cups/drv/phomemo-m110.drv
/usr/lib/cups/filter/rastertopm02
/usr/lib/cups/filter/rastertopm110
/usr/lib/cups/backend/phomemo

%changelog
* Thurs June 8 2023 Taylor Lee <taylorjdlee@gmail.com> - 1.1
- Added packages for the M110, M120 & M02S
* Fri Dec 4 2020 Laurent Vivier <laurent@vivier.eu> - 1.0
- First package
