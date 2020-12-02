#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pkg_resources import parse_requirements
from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

setup(
    name="awscli_saml_sso",
    version="0.1.1",

    author="Benjamin Brabant",
    author_email="benjamin.brabant@octo.com",
    python_requires=">=3.5",
    license="GNU General Public License v3",
    url="https://github.com/octo-technology/awscli-saml-sso",

    packages=find_packages(),
    description="""awscli_saml_sso is a command line tool that aims to get temporary credentials from SAML identity 
    provider in order to authenticate to awscli.""",
    keywords=["awscli", "saml", "sso"],
    long_description=readme,
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],

    include_package_data=True,
    install_requires=[
        "boto3==1.16.26",
        "click==7.1.2",
        "selenium==3.141.0",
        "webdriver-manager==3.2.2",
    ],
    entry_points={
        "console_scripts": [
            "awscli_saml_sso = awscli_saml_sso.__main__:main",
        ],
    },
)
