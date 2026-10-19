#!/usr/bin/env python3
"""Holt die eingebetteten CAB-Archive aus einem Windows-Installer (.msi).

Ein MSI ist eine OLE-Verbunddatei; die eigentlichen Dateien stecken in
CAB-Archiven, die als Streams darin liegen. Diese Streams werden hier
anhand der CAB-Signatur "MSCF" erkannt und als <name>.cab abgelegt;
auspacken lassen sie sich danach mit bsdtar oder cabextract.

Braucht olefile (liegt unter toolchain/tools/python).

Aufruf: msi-extract-cabs.py <datei.msi> <zielverzeichnis>
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python"))
import olefile  # noqa: E402


def main():
    if len(sys.argv) != 3:
        sys.exit("Aufruf: msi-extract-cabs.py <datei.msi> <zielverzeichnis>")
    msi, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    ole = olefile.OleFileIO(msi)
    found = 0
    for entry in ole.listdir(streams=True, storages=False):
        with ole.openstream(entry) as s:
            if s.read(4) != b"MSCF":
                continue
        data = ole.openstream(entry).read()
        # MSI kodiert Stream-Namen; fuer den Dateinamen reicht ASCII
        name = re.sub(r"[^A-Za-z0-9._-]", "_", "_".join(entry)).strip("_")
        out = os.path.join(outdir, (name or "stream%d" % found) + ".cab")
        with open(out, "wb") as f:
            f.write(data)
        print(out)
        found += 1
    if not found:
        sys.exit("keine CAB-Archive in %s gefunden" % msi)


if __name__ == "__main__":
    main()
