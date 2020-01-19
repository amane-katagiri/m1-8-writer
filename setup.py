#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup file for Distutils."""

from logging import DEBUG
from logging import getLogger
from logging import StreamHandler
import os

import app

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)

try:
    from setuptools import find_packages
    from setuptools import setup
except ImportError:
    logger.critical("Please install setuptools.")


def main() -> None:
    """Setup package after read meta information from files."""
    long_description = "USB writer for M1-8 matrix LED name badge."
    if os.path.exists("README.rst"):
        with open("README.rst") as f:
            long_description = f.read()

    install_requires = []
    if os.path.exists("requirements.txt"):
        with open("requirements.txt") as f:
            install_requires = f.read().split()

    setup(name="m1-8-writer",
          version=app.__version__,
          description="LED name badge writer.",
          long_description=long_description,
          license=app.__license__,
          author=app.__author__,
          author_email=app.__contact__,
          url="https://github.com/amane-katagiri/m1-8-writer",
          keywords="led badge usb serial m1-8",
          install_requires=[
          ] + install_requires,
          classifiers=[
              "Development Status :: 3 - Alpha",
              "License :: OSI Approved :: MIT License",
              "Programming Language :: Python :: 3.7",
          ],
          packages=find_packages(),
          entry_points="""
          [console_scripts]
          m18write = app.writer:main
          """, )


if __name__ == "__main__":
    main()
