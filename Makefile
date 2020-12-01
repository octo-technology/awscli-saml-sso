SHELL := /bin/bash
.SHELLFLAGS = -e -c
.ONESHELL:
env := dev

.DEFAULT_GOAL: help

.PHONY: help
help:
	@echo "Please use 'make <target>' where <target> is one of"
	@grep -E '^\.PHONY: [a-zA-Z_-]+ .*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = "(: |##)"}; {printf "\033[36m%-30s\033[0m %s\n", $$2, $$3}'


.PHONY: clean ## remove all build and Python artifacts
clean: clean-build clean-pyc

.PHONY: clean-build ## remove build artifacts
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc ## remove Python file artifacts
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: release ## package and upload a release
release: dist
	twine upload dist/*

.PHONY: dist ## builds source and wheel package
dist: clean
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

.PHONY: install ## install the package to the active Python's site-packages
install: clean
	pip install .
