import argparse
import io
import json
import os
import pathlib
import re
import sys
import zipfile
from urllib.request import urlopen

DEFAULT_TAG = "cp{0}{1}-cp{0}{1}-{2}".format(
    sys.version_info[0],
    sys.version_info[1],
    {"": "win_amd64", "32": "win32", "-arm64": "win_arm64"}.get(sys.winver.partition("-")[2]),
)

parser = argparse.ArgumentParser()
parser.add_argument("-o", metavar="PATH", type=pathlib.Path, default=".", required=False, help="Output directory")
parser.add_argument("--nuget", action="store_true", help="Acquire from Nuget")
parser.add_argument("--embed", action="store_true", help="Acquire embeddable from python.org")
parser.add_argument("--tag", default=DEFAULT_TAG, required=False, help="Specific wheel tag")
parser.add_argument("--platform", required=False, help="Override platform (win32, win_amd64, win_arm64)")
parser.add_argument("--version", required=False, help="Override version")
parser.add_argument("--dry-run", action="store_true", help="Do not write files to disk")
args = parser.parse_args()

m = re.match(r"(cp|py)(\d)(\d+)-.+?-(win_?.+)", args.tag)
if not m:
    print("ERROR: Unsupported tag", args.tag, file=sys.stderr)
    sys.exit(1)
if not args.version:
    args.version = f"{m.group(1)}.{m.group(2)}"
if not args.platform:
    args.platform = m.group(3)


def ver_key(v):
    i = next((c for c in v if c not in ".0123456789"), None)
    if i:
        ver, _, suff = v.partition(i)
        if suff and i != '-':
            suff = i + suff
    else:
        ver = v
        suff = None
    k = [int(b) for b in ver.split(".")]
    while len(k) < 4:
        k.append(0)
    if suff:
        k.append({"a": 1, "b": 2, "c": 3, "r": 3}[suff[0]])
        k.append(int(suff.lstrip("abrc")))
    else:
        k.append(10)
    return tuple(k)


def from_nuget(version, platform):
    package = {
        "win32": "pythonx86",
        "win_amd64": "python",
        "win_arm64": "pythonarm64",
    }[platform]

    print("Finding download for", package, version)

    url = os.getenv("PYMSBUILD_NUGET_FEED") or "https://api.nuget.org/v3/index.json"

    with urlopen(url) as u:
        service = [s for s in json.load(u).get('resources', ())
                   if s.get('@type') == 'PackageBaseAddress/3.0.0']

    if not service:
        raise Exception("ERROR: Specified feed does not appear to be a Nuget feed")

    url = f"{service[0]['@id']}{package.lower()}/index.json"
    with urlopen(url) as u:
        versions = json.load(u).get('versions')

    if not versions:
        raise Exception(f"ERROR: No versions found for package {package}")

    if version not in versions:
        prereleased = [v for v in versions if v.startswith(f"{version}.")]
        released = [v for v in prereleased if "-" not in v]
        if released:
            version = max(released, key=ver_key)
        elif prereleased:
            version = max(prereleased, key=ver_key)
        else:
            raise Exception(f"ERROR: No matching versions found for package {package}")

    print("Selected version", version)
    url = f"{service[0]['@id']}{package.lower()}/{version}/{package.lower()}.{version}.nupkg"
    print("Downloading from", url)
    buffer = io.BytesIO()
    with urlopen(url) as r:
        buffer.write(r.read())
    buffer.seek(0)
    with zipfile.ZipFile(buffer, "r") as zf:
        for n in zf.namelist():
            if not n.startswith("tools/") or ".." in n:
                continue
            yield n.partition("/")[2], zf.read(n)


def from_embed(version, platform):
    #https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-win32.zip
    url = "https://www.python.org/ftp/python/"

    package = {
        "win32": "python-VERSION-embed-win32.zip",
        "win_amd64": "python-VERSION-embed-amd64.zip",
        "win_arm64": "python-VERSION-embed-arm64.zip",
    }[platform]

    with urlopen(url) as r:
        versions = [s.decode() for s in re.findall(rb'<a\s+href="(\d+\.\d+\.\d+)', r.read())]

    if version not in versions:
        released = [v for v in versions if v.startswith(f"{version}.")]
        if released:
            version = max(released, key=ver_key)
        else:
            raise Exception(f"ERROR: No matching versions found for package {package}")

    print("Selected", version)
    url = f"{url}{version}/"

    pattern = re.escape(package).replace("VERSION", "(.+?)")
    pattern = f'a href="({pattern})"'
    with urlopen(url) as r:
        files = [(i[1].decode(), i[0].decode()) for i in re.findall(pattern.encode(), r.read())]

    files = sorted(files, key=lambda i: ver_key(i[0]), reverse=True)
    if not files:
        raise Exception(f"ERROR: No matching versions found for {version}")
    url += files[0][1]
    print("Downloading from", url)
    buffer = io.BytesIO()
    with urlopen(url) as r:
        buffer.write(r.read())
    buffer.seek(0)
    with zipfile.ZipFile(buffer, "r") as zf:
        for n in zf.namelist():
            if ".." in n:
                continue
            yield n, zf.read(n)


try:
    func = from_nuget if args.nuget else from_embed if args.embed else None
    if not func:
        raise Exception("ERROR: No source specified (pass --nuget or --embed)")
    for name, content in func(args.version, args.platform):
        if args.dry_run:
            print("Write", name, len(content), "bytes")
        else:
            dest = args.o / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(content)

except Exception as ex:
    print(ex, file=sys.stderr)
    sys.exit(1)
