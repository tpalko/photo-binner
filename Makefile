PACKAGE_NAME := photobinner
SHELL := /bin/bash
INVENV := $(if $(VIRTUAL_ENV),1,0)
PYTHONINT := $(shell which python3)
PYTHON_VERSION := 3.11
WORKON_HOME := ~/.virtualenv
VENV_WRAPPER := /usr/share/virtualenvwrapper/virtualenvwrapper.sh
#LATEST_VERSION := $(shell git tag | grep -E "^v[[:digit:]]+.[[:digit:]]+.[[:digit:]]+$$" | sort -n | tail -n 1)

#PATH_TO_COWPY ?= $(PWD)/../cowpy
#PATH_TO_FRANK_COMMON ?= $(PWD)/../../projects/frank-common

BRANCH := $(shell git branch --show-current)
CHANGES := $(strip $(shell git status -s -- src/$(PACKAGE_NAME) | wc -l))
HEAD_VERSION_TAG := $(shell git tag --contains | head -n 1 | grep -E "^v[[:digit:]]+.[[:digit:]]+.[[:digit:]]+$$")
HEAD_TAGGED := $(if $(HEAD_VERSION_TAG),1,0)

DRY_RUN_PARAM := $(if $(DRY_RUN),--dry-run,)
TAG_PREFIX := v
PREMAJOR := true
STD_VER_PARAMS := --preMajor $(PREMAJOR) -a --path ./src/frank --tag-prefix $(TAG_PREFIX)
STD_VER_WET_PARAMS := --releaseCommitMessageFormat="release {{currentTag}}" --header "\# Changelog"

define version
	standard-version $(DRY_RUN_PARAM) $(STD_VER_PARAMS) $(STD_VER_WET_PARAMS)
endef 

venv-reset:
	. $(VENV_WRAPPER) \
		&& rmvirtualenv $(PACKAGE_NAME)

dev-reset: venv-reset

venv:	
	. $(VENV_WRAPPER) \
		&& (workon $(PACKAGE_NAME) 2>/dev/null || mkvirtualenv -a . -p $(PYTHONINT) $(PACKAGE_NAME))
	pip install \
		--extra-index-url https://test.pypi.org/simple \
		-t $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages \
		-r src/requirements.txt

#vendor-install:
#	pip install -e \
#		-t $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages \
#		$(PATH_TO_COWPY)
#	pip install -e \
#		-t $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages \
#		$(PATH_TO_FRANK_COMMON)

# ln -svf $(PATH_TO_COWPY)/src/cowpy $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/
# ln -svf $(PATH_TO_FRANK_COMMON)/src/frank $(WORKON_HOME)/$(PACKAGE_NAME)/lib/python$(PYTHON_VERSION)/site-packages/

dev-setup: venv

test: venv vendor-install
	. $(VENV_WRAPPER) \
		&& workon $(PACKAGE_NAME) \
		&& pushd src \
		&& FRANKBACK_RC_FILE=./test/.frankbackrc python -m backup

build-deps:
	@$(PYTHONINT) -m pip install --upgrade pip build twine 

version: NEXT_VERSION := $(shell standard-version --dry-run $(STD_VER_PARAMS) | grep "tagging release" | awk '{ print $$4 }')
version:
ifeq ($(BRANCH), main)
	@echo "OK, on main, continuing.."
ifeq ($(CHANGES), 0)
	@echo "No changes, continuing.."
ifeq ($(HEAD_TAGGED), 0)
	@echo "Head is tagged, versioning $* (DRY_RUN=$(DRY_RUN))"
ifneq ($(DRY_RUN), 1)
	@echo "Not a dry run, updating project files.."
	sed -i "s/^version = .*/version = \"$(NEXT_VERSION)\"/" pyproject.toml \
		&& printf "[metadata]\nversion = $(NEXT_VERSION)\n" > setup.cfg \
		&& git diff \
		&& git add pyproject.toml setup.cfg
endif		
	@echo "Actually versioning.."
	pushd src/$(PACKAGE_NAME) \
		&& $(call version)
else # head tagged 
	@echo "No versioning today (commit already tagged $(HEAD_VERSION_TAG))"	
endif # head not tagged 
else # changes 
	@echo "No versioning today (%=$* BRANCH=$(BRANCH) CHANGES=$(CHANGES) HEAD_VERSION_TAG=$(HEAD_VERSION_TAG) HEAD_TAGGED=$(HEAD_TAGGED) DRY_RUN_PARAM=$(DRY_RUN_PARAM)). Stash or commit your changes."
	exit 1
endif # no changes 
else # not on main 
	@echo "Will not version outside main"
	exit 1
endif # on main 

.PHONY: build 

ifeq ($(INVENV), 0)
ifeq ($(HEAD_TAGGED), 1)
build: build-deps
	python3 -m build
else 
build:
	@echo "Will not build unversioned"
	exit 1
endif 
else 
build:
	@echo "Cannot build while in virtualenv (in virtualenv $(VIRTUAL_ENV))"
	exit 1	
endif 

publish-test: build 
ifneq ($(DRY_RUN), 1)
	python3 -m twine upload --repository testpypi dist/*
else 
	python3 -m twine check --repository testpypi dist/*
endif 

publish: build 
ifneq ($(DRY_RUN), 1)
	python3 -m twine upload dist/*
else 
	python3 -m twine check dist/*
endif 

install-test:
	pip install -i https://test.pypi.org/simple/ $(PACKAGE_NAME)

install-link:
	ln -svf ${PWD}/src/photobinner/photobinner.py /usr/local/bin/pb \
		|| (@echo "maybe no permissions for /usr/local/bin, trying home folder.." \
		&& ln -svf $(PWD)/src/photobinner/photobinner.py ~/.local/bin/pb)
	
install:
ifeq ($(HEAD_TAGGED), 1)
	pip install .
else 
	@echo "Will not install unversioned"
	exit 1
endif 

uninstall:
	pip uninstall $(PACKAGE_NAME)

clean:
	rm -rf build 
	rm -rf dist 
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ | xargs rm -rvf 
	find . -type f -name *.pyc | xargs rm -vf
