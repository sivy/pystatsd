%if 0%{?rhel} < 6
%define needs_python24_patching 1
%else
%define needs_python24_patching 0
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           pystatsd
Version:        0.1.7
Release:        4%{?dist}
Summary:        Python implementation of the Statsd client/server
Group:          Applications/Internet
License:        Unknown
URL:            http://pypi.python.org/pypi/pystatsd/
Source0         http://pypi.python.org/packages/source/p/pystatsd/pystatsd-%{version}.tar.gz
Patch0:         pystatsd-python2.4.patch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python-devel
%if 0%{?fedora} && 0%{?fedora} < 13
BuildRequires:  python-setuptools-devel
%else
BuildRequires:  python-setuptools
%endif

Requires: python-argparse >= 1.2

%description
pystatsd is a client and server implementation of Etsy's brilliant statsd
server, a front end/proxy for the Graphite stats collection and graphing server.

* Graphite
    - http://graphite.wikidot.com
* Statsd
    - code: https://github.com/etsy/statsd
    - blog post: http://codeascraft.etsy.com/2011/02/15/measure-anything-measure-everything/

%prep
%setup -q

%if %{needs_python24_patching}
%patch0 -p1
%endif

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
mkdir -p %{buildroot}/etc/init.d
install -m0755 init/pystatsd.init  %{buildroot}/etc/init.d/pystatsd
mkdir -p %{buildroot}/etc/default
install -m0644 init/pystatsd.default  %{buildroot}%{_sysconfdir}/default/pystatsd

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README.md
%config %{_sysconfdir}/default/pystatsd
%{python_sitelib}/*
/usr/bin/pystatsd-server
/etc/init.d/pystatsd

%changelog
* Mon Apr 07 2014 Stefan Richter <stefan@02strich.de> - 0.1.7-4
- update to 4a60cbb2d8152925fa0d18b1666be3bad2e2884b
- also use/install /etc/default/pystatsd
* Wed Aug 15 2012 Bruno Clermont <bruno.clermont@gmail.com> - 0.1.7-3
- update to 36a59d3b126ded4658aff25bce94e844a1c6413e
- Fix path to README file
* Fri Mar 02 2012 Justin Burnham <jburnham@mediatemple.net> - 0.1.7-2
- Add python-argparse requires.
- Add init file to MANIFEST.in for setup.py sdist.
* Thu Oct 07 2011 Sharif Nassar <sharif@mediatemple.net> - 0.1.7-1
- Initial package
