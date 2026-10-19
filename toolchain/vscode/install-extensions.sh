#!/bin/sh
# Installs the VS Code extensions this project's editor setup relies on:
#
#   clangd       C/C++ language server front end; the server itself is
#                llvm-mos's clangd (see .vscode/settings.json)
#   mega65-asm   45GS02 assembly highlighting from mega65-asm/, packed into
#                build/mega65-asm.vsix here (not in the marketplace)
#
# Usage: toolchain/vscode/install-extensions.sh
#   CODE=<command>  the VS Code command line (default: code, or the Flatpak)

set -e

HERE=$(cd "$(dirname "$0")" && pwd)

if [ -z "$CODE" ]; then
    if command -v code >/dev/null 2>&1; then
        CODE=code
    elif flatpak info com.visualstudio.code >/dev/null 2>&1; then
        CODE="flatpak run com.visualstudio.code"
    else
        echo "Error: VS Code not found (set CODE=...)." >&2
        exit 1
    fi
fi

# A .vsix is a zip: the extension under extension/ plus two manifests
VERSION=$(sed -n 's/^ *"version": "\(.*\)",$/\1/p' "$HERE/mega65-asm/package.json")
mkdir -p "$HERE/build"
python3 - "$HERE/mega65-asm" "$HERE/build/mega65-asm.vsix" "$VERSION" <<'EOF'
import os, sys, zipfile

src, out, version = sys.argv[1:]
content_types = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension=".json" ContentType="application/json"/>
<Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
"""
manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
<Metadata>
<Identity Language="en-US" Id="mega65-asm" Version="{version}" Publisher="local"/>
<DisplayName>MEGA65 Assembly (45GS02)</DisplayName>
<Description xml:space="preserve">Syntax highlighting for 45GS02 assembly in llvm-mos (GNU as) syntax</Description>
<Categories>Programming Languages</Categories>
<Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.60.0"/></Properties>
</Metadata>
<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
<Dependencies/>
<Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>
"""
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("extension.vsixmanifest", manifest)
    for root, _, files in os.walk(src):
        for name in files:
            path = os.path.join(root, name)
            z.write(path, "extension/" + os.path.relpath(path, src))
EOF

$CODE --install-extension llvm-vs-code-extensions.vscode-clangd
$CODE --install-extension "$HERE/build/mega65-asm.vsix" --force
echo "Done. Reload the VS Code window (Developer: Reload Window)."
