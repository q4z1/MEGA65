#!/bin/sh
# Installs the Python modules with compiled parts - Pillow, numpy - at fixed
# versions for the python3 that runs it, into tools/python/<version> (a
# module built for one Python version does not load in another: the VS Code
# Flatpak and the host can have different ones), and prints that directory.
#
#   PYTHONPATH="$(toolchain/tools/python-modules.sh)"
#
# Installs only what is missing; the first run needs the network. Without
# a pip of its own (Arch's python without python-pip) pip's zipapp does it.

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
DL="$(dirname "$HERE")/downloads"
PIP_PYZ=pip-25.2.pyz
DIR="$HERE/python/$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

pip() {
    if python3 -m pip --version > /dev/null 2>&1; then
        python3 -m pip "$@"
    else
        if [ ! -f "$DL/$PIP_PYZ" ]; then
            mkdir -p "$DL"
            curl -sL --fail -o "$DL/$PIP_PYZ" "https://bootstrap.pypa.io/pip/zipapp/$PIP_PYZ"
        fi
        python3 "$DL/$PIP_PYZ" "$@"
    fi
}

if [ ! -f "$DIR/PIL/__init__.py" ]; then
    pip install -q --disable-pip-version-check --target "$DIR" Pillow==12.3.0 >&2
fi

if [ ! -f "$DIR/numpy/__init__.py" ]; then
    pip install -q --disable-pip-version-check --target "$DIR" numpy==2.3.4 >&2
fi

echo "$DIR"
