# KrakTAK Makefile
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
.POSIX:

PYTHON := python3
REPO_NAME ?= $(shell echo $(wildcard src/*/__init__.py) | awk -F'/' '{print $$2}')
SHELL := /bin/bash
.DEFAULT_GOAL := editable

.PHONY: help editable install install_test_requirements uninstall reinstall \
	test pytest test_cov dist publish clean lint pylint pep8 flake8 black \
	deb_dist deb_custom bdist_deb faux_latest package rpm docker_deb docker_rpm

help:
	@echo "Targets:"
	@echo "  make editable    pip install -e . (default)"
	@echo "  make install     install the package"
	@echo "  make test        editable install + test deps + pytest"
	@echo "  make dist        build sdist + wheel into dist/"
	@echo "  make publish     upload dist/ to PyPI via twine"
	@echo "  make package     build a Debian .deb into deb_dist/"
	@echo "  make rpm         build an RPM into dist/"
	@echo "  make docker_deb  build the .deb-based Docker image"
	@echo "  make docker_rpm  build the .rpm-based Docker image"
	@echo "  make clean       remove build/dist/egg-info/caches"

editable:
	$(PYTHON) -m pip install -e .

install:
	$(PYTHON) -m pip install .

install_test_requirements:
	$(PYTHON) -m pip install -e '.[test]'

uninstall:
	$(PYTHON) -m pip uninstall -y $(REPO_NAME)

reinstall: uninstall install

pytest:
	$(PYTHON) -m pytest

test: editable install_test_requirements pytest

test_cov:
	$(PYTHON) -m pytest --cov=$(REPO_NAME) --cov-report term-missing

dist:
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

publish: dist
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine upload dist/*

# --- OS packages ---------------------------------------------------------

deb_dist:
	$(PYTHON) setup.py --command-packages=stdeb.command sdist_dsc

deb_custom:
	cp debian/$(REPO_NAME).postinst $(wildcard deb_dist/*/debian)/$(REPO_NAME).postinst
	cp debian/$(REPO_NAME).service $(wildcard deb_dist/*/debian)/$(REPO_NAME).service
	cp debian/$(REPO_NAME).conf $(wildcard deb_dist/*/debian)/$(REPO_NAME).default

bdist_deb: deb_dist deb_custom
	cd deb_dist/$(REPO_NAME)-*/ && dpkg-buildpackage -rfakeroot -uc -us

faux_latest:
	cp deb_dist/$(REPO_NAME)_*-1_all.deb deb_dist/$(REPO_NAME)_latest_all.deb
	cp deb_dist/$(REPO_NAME)_*-1_all.deb deb_dist/python3-$(REPO_NAME)_latest_all.deb

package: bdist_deb faux_latest

rpm:
	$(PYTHON) setup.py bdist_rpm --python=/usr/bin/python3

docker_deb: package
	mkdir -p dist
	cp deb_dist/$(REPO_NAME)_*-1_all.deb dist/
	docker build -f Dockerfile.deb -t $(REPO_NAME)-deb:local .

docker_rpm: rpm
	docker build -f Dockerfile.rpm -t $(REPO_NAME)-rpm:local .

# --- lint / style --------------------------------------------------------

pep8:
	flake8 --max-line-length=88 --extend-ignore=E203 --exit-zero src/$(REPO_NAME)/*.py

flake8: pep8

lint:
	pylint --max-line-length=88 -r n src/$(REPO_NAME)/*.py || exit 0

pylint: lint

black:
	black .

clean:
	@rm -rf *.egg* build dist deb_dist *.py[oc] */*.py[co] cover doctest_pypi.cfg \
		nosetests.xml pylint.log output.xml flake8.log tests.log \
		test-result.xml htmlcov fab.log .coverage __pycache__ \
		*/__pycache__ src/*.egg-info .mypy_cache .pytest_cache
