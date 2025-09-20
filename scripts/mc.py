#!/bin/env python3

"""
A general purpose util for getting and deobfuscating Minecraft
jar files.

Copyright (C) 2025 - PsychedelicPalimpsest


This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os, sys, json
import gzip
import platform
import subprocess
import re
from urllib3 import request
import xml.etree.ElementTree as ET


import hashlib

MIN_JAVA_VERSION = 16
CFR_URL = "https://www.benf.org/other/cfr/cfr-0.152.jar"
REMAPPER_URL = "https://maven.fabricmc.net/net/fabricmc/tiny-remapper/0.11.2/tiny-remapper-0.11.2-fat.jar" 

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"


YARN_FABRIC_BASE = "https://maven.fabricmc.net/net/fabricmc/yarn/"
YARN_LEGACY_BASE = "https://repo.legacyfabric.net/legacyfabric/net/legacyfabric/yarn/"



def get_storage_dir() -> str:
    os_name = platform.system()

    # Highest priority: explicit override
    if "GRYLA_HOME" in os.environ:
        return os.path.expanduser(os.environ["GRYLA_HOME"])

    if os_name == "Linux":
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        return os.path.join(base, "gryla")

    if os_name == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Caches/gryla")

    if os_name == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata is not None:
            return os.path.join(local_appdata, "gryla", "Cache")

    # Fallback if unknown system
    raise RuntimeError(f"Cannot determine cache directory on {os_name}")

def get_java_major_version():
    try:
        result = subprocess.run(
            ["java", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError("Java not installed or not in PATH")

    first_line = result.stdout.splitlines()[0].strip()

    # Find something like "21.0.1" or "1.8.0_371"
    m = re.search(r'(\d+)(?:\.(\d+))?', first_line)
    if not m:
        raise RuntimeError("Could not parse Java version from: " + first_line)

    major = int(m.group(1))
    minor = m.group(2)

    # Handle the legacy "1.x" versions (Java <= 8)
    if major == 1 and minor is not None:
        major = int(minor)

    return major
def verify_java() -> bool:
    return get_java_major_version() > MIN_JAVA_VERSION

def sizeof_fmt(num, suffix="B"):
    # http://stackoverflow.com/questions/1094841/ddg#1094933
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def download_file(url : str, outpath : str, output=True):
    resp = request("GET", url, preload_content=False, decode_content=False)
    if resp.status != 200:
        raise ConnectionError(f"ERROR: cannot fetch {url}")

    total = resp.headers.get("Content-Length")
    if total is not None:
        total = sizeof_fmt(int(total))

    ending = ("/" + total) if total is not None else " downloaded"
        
    last_write = ""

    if output:
        sys.stdout.write(last_write := "0" + ending)

    cnt = 0

    with open(outpath, "wb") as f:
        for chunk in resp.stream():
            cnt += len(chunk)
            if output:
                s = "\r" + sizeof_fmt(cnt) + ending
                if len(last_write) > len(s):
                    s += " " * (len(last_write) - len(s))
                last_write = s
                sys.stdout.write(s)
            f.write(chunk)
    if output:
        s = "\rDownload completed!"
        if len(last_write) > len(s):
            s += " " * (len(last_write) - len(s))
        sys.stdout.write(s + "\n")
    resp.close()
        

STORAGE_DIR = get_storage_dir()
os.makedirs(STORAGE_DIR, exist_ok=True)

CFR = os.path.join(STORAGE_DIR, "cfr.jar")
REMAPPER = os.path.join(STORAGE_DIR, "tinyremapper.jar")

MAPPINGIO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deps", "mapping-io-cli-0.3.0-all.jar")

MODERN_YARN_CACHE = os.path.join(STORAGE_DIR, "modern_yarn.json")
LEGACY_YARN_CACHE = os.path.join(STORAGE_DIR, "lagacy_yarn.json")

VERSION_MANIFEST_CACHE = os.path.join(STORAGE_DIR, "version_manifest.json")

def _get_yarn_versions(url : str):
    resp = request("GET", url)
    root = ET.fromstring(resp.data)
    versions = root[2][2]

    return [v.text for v in versions]


def get_modern_yarn_versions_web():
    return _get_yarn_versions(YARN_FABRIC_BASE + "maven-metadata.xml")

def get_legacy_yarn_versions_web():
    return _get_yarn_versions(YARN_LEGACY_BASE + "maven-metadata.xml")


def get_modern_yarn_versions_cached():
    if os.path.exists(MODERN_YARN_CACHE):
        with open(MODERN_YARN_CACHE, "r") as f:
            return json.load(f)

    vers = get_modern_yarn_versions_web()
    with open(MODERN_YARN_CACHE, "w") as f:
        json.dump(vers, f, indent=1)
    return vers

def get_legacy_yarn_versions_cached():
    if os.path.exists(LEGACY_YARN_CACHE):
        with open(LEGACY_YARN_CACHE, "r") as f:
            return json.load(f)

    vers = get_legacy_yarn_versions_web()
    with open(LEGACY_YARN_CACHE, "w") as f:
        json.dump(vers, f, indent=1)
    return vers

def get_manifest_cache():
    assert os.path.exists(VERSION_MANIFEST_CACHE)
    with open(VERSION_MANIFEST_CACHE, "r") as f:
        return json.load(f)

def download_mojang_file(versions_id : str, target : str, output : str | None, do_log=True):
    vers = get_manifest_cache()["versions"]
    version = None
    for v in vers:
        if v["id"] == versions_id:
            version = v
            break
    if version is None:
        print(f"Unknown version: {versions_id}")
        exit(1)
    resp = request("GET", version["url"])
    assert resp.status == 200, "Mojang server error"

    target = target


    downloads = json.loads(resp.data)["downloads"]
    if not target in downloads:
        print(f"ERROR: cannot download '{target}', the valid options for this version are: {', '.join(downloads.keys())}")
        exit(1)
    download_json = downloads[target]

    output : str = output if output is not None else download_json["url"].split("/")[-1] 

    if do_log:
        print(f"Downloading {output}")

    download_file(download_json["url"], output, output=do_log)

    if do_log:
        print("Verifying")

    hobj = hashlib.new("sha1")
    with open(output, "rb") as f:
        while len(b := f.read(2**16)):
            hobj.update(b)

    digest = hobj.hexdigest()
    if digest != download_json["sha1"]:
        print("ERROR: Unable to verify file! Digests do not match")
        print(f"Expected: {download_json['sha1']}")
        print(f"Recived: {digest}")
        exit(1)
    else:
        if do_log:
            print("Verified!")

def _get_most_recent_yarn(version_id : str):
    modern = sorted([v for v in get_modern_yarn_versions_cached() if v.startswith(version_id + "+build")], key=lambda x: x.split(".")[-1].zfill(3))
    if len(modern):
        ver = modern[-1] 
        return f"{YARN_FABRIC_BASE}{ver}/yarn-{ver}-tiny.gz"
    legacy = sorted([v for v in get_legacy_yarn_versions_cached() if v.startswith(version_id + "+build")], key=lambda x: x.split(".")[-1].zfill(3))
    if len(legacy):
        ver = legacy[-1] 
        return f"{YARN_LEGACY_BASE}{ver}/yarn-{ver}-tiny.gz"
    print(f"ERROR: unable to get yarn for version {version_id}")
    exit(1)

def get_yarn_tiny(version_id : str):
    output = os.path.join(STORAGE_DIR, f"yarn.{version_id}.tiny")
    if os.path.exists(output):
        return output

    resp = request("GET", _get_most_recent_yarn(version_id), decode_content=False)
    with open(output, "wb") as f:
        f.write(gzip.decompress(resp.data))
    return output

    


def get_mapped_jar(version_id : str, target : str, mapping : str, output : str, fromMapping = "official", toMapping = "named"):
    assert target in ["server", "client"]

    
    temp_raw = target + ".raw.jar"
    download_mojang_file(version_id, target, temp_raw)

    tiny = get_yarn_tiny(version_id)

    print("Remapping")
    
    resp = subprocess.Popen(["java", "-jar", REMAPPER,
                             temp_raw, output, tiny, fromMapping, toMapping]) 

    resp.wait()


def get_mojang_txt(version_id : str, target : str) -> str:
    assert target in ["client", "server"]

    mojmap = os.path.join(STORAGE_DIR, f"mojmap.{version_id}.{target}.txt")

    download_mojang_file(version_id, target+"_mappings", mojmap)


    return mojmap

def get_mojang_tiny(version_id : str, target : str) -> str:
    out = os.path.join(STORAGE_DIR, f"mojmap.{version_id}.{target}.tiny")
    if os.path.exists(out):
        return out

    mojmap = get_mojang_txt(version_id, target)


    p = subprocess.Popen([
        "java", "-jar", MAPPINGIO,
        "convert", mojmap, out, "TINY_2", 
    ], stdout=subprocess.PIPE)
    if p.wait() != 0:
        exit(1)
    return out

def print_help():
    print("""usage: python mc.py [mode] [operands]
Valid modes:
    help - Display this screen
    clear_cache - Remove all the cache for: Modern yarn, Legacy yarn, cfr.java, tiny remapper, and the minecraft version manifest.
    versions - List all the versions of minecraft
            Usage: python mc.py getjar list_versions [version types...]
            Where `version types` is a comma seperated version types you wish to see. 
            The valid types are: snapshot, release, old_beta, and old_alpha

            Ex: python mc.py release, old_beta

    get_jar - Download a jar file from Mojang
            Usage: python mc.py get_jar version [client/server/windows_server] [output]

    get_mapped_jar - Download and remap a jar from mojang
            Usage: python mc.py get_mapped_jar client/server [mapping] [output] 

            Mapping: Use either mojang, yarn, or mcp. 

    get_source_jar - Download and decompile a jar
            Usage: python mc.py get_source_jar client/server [mapping] [output] 

            Mapping: Use either mojang, yarn, or mcp. 


    """)
    
def main():
    if len(sys.argv) == 1 or sys.argv[1] in ["-h", "--help", "help"]:
        print_help()
        exit(0)
    if not verify_java():
        print(f"Error: please install java {MIN_JAVA_VERSION} or later!")
        exit(1)
    if not os.path.exists(CFR):
        print("Downloading cfr!")
        download_file(CFR_URL, CFR)
    if not os.path.exists(REMAPPER):
        print("Downloader tiny remapper!")
        download_file(REMAPPER_URL, REMAPPER)


    if not os.path.exists(MODERN_YARN_CACHE):
        print("Building yarn cache")
        _ = get_modern_yarn_versions_cached()
        _ = get_legacy_yarn_versions_cached()

    if not os.path.exists(VERSION_MANIFEST_CACHE):
        print("Downloading minecraft version manifest")
        download_file(VERSION_MANIFEST_URL, VERSION_MANIFEST_CACHE)

    if sys.argv[1] in ["cache", "clear_cache"]:
        for p in os.listdir(STORAGE_DIR):
            print(f"Removing {p}")
            os.remove(os.path.join(STORAGE_DIR, p))
    elif sys.argv[1] in ["list_versions", "versions"]:
        types = " ".join(sys.argv[2:]).strip().split(",")
        types = [t.strip() for t in types if len(t.strip())]
        if len(types) == 0:
            types = ["release"]
        for t in types:
            if t not in ["snapshot", "release", "old_beta", "old_alpha"]:
                print(f"Unknown version type '{t}'")
                exit(1)
        versions = get_manifest_cache()["versions"]
        versions = [v for v in versions if v["type"] in types]
        for v in versions:
            print(v["id"])
    elif sys.argv[1] == "get_jar":
        if len(sys.argv) == 2:
            print("Missing argument: version")
            exit(1)

        download_mojang_file(sys.argv[2], "client" if len(sys.argv) == 3 else sys.argv[3], None if sys.argv != 5 else sys.argv[4])

    elif sys.argv[1] == "cfr":
        subprocess.run(["java", "-jar", CFR, *sys.argv[2:]])

    elif sys.argv[1] == "get_mapped_jar":

        print(get_mojang_tiny("1.21.3", "client"))
        pass
#        get_mapped_jar("1.8.5", "client", "yarn", "mapped.jar")
   


                

    else:
        print(f"Unknown mode '{sys.argv[1]}'")
        print_help()
        exit(1)

    

if __name__ == "__main__":
    main()








