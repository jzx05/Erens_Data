#!/usr/bin/env python3
"""Download and install the official portable Node 24 tarball."""

from __future__ import annotations

import tarfile
import urllib.request

VERSION = "24.22.0"
URL = f"https://nodejs.org/dist/v{VERSION}/node-v{VERSION}-linux-x64.tar.xz"
ARCHIVE = "/tmp/node.tar.xz"
PREFIX = f"node-v{VERSION}-linux-x64/"

urllib.request.urlretrieve(URL, ARCHIVE)
with tarfile.open(ARCHIVE, "r:xz") as archive:
    for member in archive.getmembers():
        if not member.name.startswith(PREFIX):
            continue
        member.name = member.name[len(PREFIX):]
        if member.name:
            archive.extract(member, "/usr/local", filter="data")

print("installed node", VERSION)
