#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert from Markdown to reST before upload to PyPI."""
import doctest
from logging import DEBUG
from logging import getLogger
from logging import StreamHandler
import os

import pypandoc

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)


def main(src: str, dst: str) -> None:
    """Convert 'src' in Markdown to 'dst' in reST."""
    text = pypandoc.convert(src, "rst")
    logger.debug(text)
    with open(dst, "w+") as f:
        f.write(text)
    os.system("python setup.py sdist upload")
    os.remove(dst)


if __name__ == "__main__":
    doctest.testmod()

    main("README.md", "README.rst")
