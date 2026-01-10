#!/bin/env python3
"""
A general purpose util for getting and deobfuscating Minecraft
jar files.

Copyright (C) 2025 - 2026 - PsychedelicPalimpsest


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

from hashlib import sha1
import json
import subprocess
from zipfile import ZipFile
from typing import cast
from urllib3 import request
from os.path import dirname, exists, join
import xml.etree.ElementTree as ET
import os, shutil, sys
import platform


from tempfile import mktemp

CFR_URL = "https://www.benf.org/other/cfr/cfr-0.152.jar"
REMAPPER_URL = "https://maven.fabricmc.net/net/fabricmc/tiny-remapper/0.11.2/tiny-remapper-0.11.2-fat.jar"
SPECIAL_SOURCE2_URL = "https://hub.spigotmc.org/stash/projects/SPIGOT/repos/builddata/raw/bin/SpecialSource-2.jar?at=refs%2Fheads%2Fmaster"

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
# Has more than the regular mojang manifest
OMNI_VERSION_MANIFEST_URL = "https://meta.omniarchive.uk/v1/manifest.json"


YARN_FABRIC_BASE = "https://maven.fabricmc.net/net/fabricmc/yarn/"
YARN_LEGACY_BASE = "https://repo.legacyfabric.net/legacyfabric/net/legacyfabric/yarn/"


MAPPINGIO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "deps",
    "mapping-io-cli-0.3.0-all.jar",
)


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


STORAGE_DIR = get_storage_dir()
os.makedirs(STORAGE_DIR, exist_ok=True)


def get_spigot_build_data_path() -> str:
    data_path = join(STORAGE_DIR, "spigot_build_data")
    inner_path = join(data_path, "BuildData")

    if not exists(inner_path):
        os.makedirs(data_path)

        subprocess.check_call(
            [
                "git",
                "clone",
                "https://hub.spigotmc.org/stash/scm/spigot/builddata.git",
                inner_path,
            ]
        )
    return inner_path


def set_build_data(commit: str):
    data = get_spigot_build_data_path()
    subprocess.check_call(
        ["git", "checkout", commit],
        cwd=data,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return data


def sizeof_fmt(num, suffix="B"):
    # http://stackoverflow.com/questions/1094841/ddg#1094933
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def download_file(url: str, outpath: str, output=True):
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


def get_cached_file(cache_key: str) -> None | str:
    cache_dir = join(STORAGE_DIR, cache_key)
    if exists(cache_dir):
        listing = os.listdir(cache_dir)
        if len(listing) == 0:
            return None

        return join(cache_dir, listing[0])
    return None


def make_cache_file(cache_key: str, name: str) -> str:
    cache_dir = join(STORAGE_DIR, cache_key)

    assert not exists(cache_dir) or len(os.listdir(cache_dir)) == 0

    if not exists(cache_dir):
        os.mkdir(cache_dir)

    return join(cache_dir, name)


def download_cached(url: str, file_name: str) -> str:
    cache_key = sha1(url.encode("utf-8")).hexdigest()

    if path := get_cached_file(cache_key):
        return path
    path = make_cache_file(cache_key, file_name)

    print(f"Downloading: {file_name}")
    download_file(url, path)
    return path


CRF = download_cached(CFR_URL, "cfr.jar")
REMAPPER = download_cached(REMAPPER_URL, "remapper.jar")
VERSION_MANIFEST = download_cached(VERSION_MANIFEST_URL, "version_manifest.json")
OMNI_VERSION_MANIFEST = download_cached(
    OMNI_VERSION_MANIFEST_URL, "omni_version_manifest.json"
)

SPECIAL_SOURCE2 = download_cached(SPECIAL_SOURCE2_URL, "SpecialSource-2.jar")


def _get_yarn_versions(url: str) -> list[str]:
    cache_key = sha1(url.encode("utf-8")).hexdigest()

    if path := get_cached_file(cache_key):
        return json.load(open(path))

    resp = request("GET", url)
    root = ET.fromstring(resp.data)
    versions = root[2][2]

    ret = [v.text for v in versions]

    with open(make_cache_file(cache_key, "maven-metadata.xml"), "w") as f:
        json.dump(ret, f)

    return cast(list[str], ret)


def get_modern_yarn_versions() -> list[str]:
    return _get_yarn_versions(YARN_FABRIC_BASE + "maven-metadata.xml")


def get_legacy_yarn_versions() -> list[str]:
    return _get_yarn_versions(YARN_LEGACY_BASE + "maven-metadata.xml")


def get_piston_json_path(version_id: str):
    cache_key = sha1(f"PISTON MANIFEST: '{version_id}'".encode("utf-8")).hexdigest()
    if path := get_cached_file(cache_key):
        return path

    is_omni = False
    if version_id.startswith("@omni@"):
        is_omni = True
        version_id = version_id[len("@omni@") :]

    versions = json.load(open(OMNI_VERSION_MANIFEST if is_omni else VERSION_MANIFEST))[
        "versions"
    ]
    version = None
    for v in versions:
        if v["id"] == version_id:
            version = v
            break
    if version is None:
        raise IndexError("Unable to find version: " + version_id)

    resp = request("GET", version["url"])
    assert resp.status == 200, "Piston server error"

    path = make_cache_file(cache_key, "client.json")
    with open(path, "wb") as f:
        f.write(resp.data)

    return path


def get_piston_file(version_id: str, target: str) -> str:
    cache_key = sha1(f"PISTON: '{version_id}' : {target}".encode("utf-8")).hexdigest()
    if path := get_cached_file(cache_key):
        return path

    with open(get_piston_json_path(version_id)) as f:
        downloads = json.load(f)["downloads"]

    if target.startswith("@omni@"):
        target = target[len("@omni@") :]
    if not target in downloads:
        raise IndexError(f"Unable to find '{target}' in {', '.join(downloads.keys())}")
    url = downloads[target]["url"]

    path = make_cache_file(cache_key, url.split("/")[-1])
    download_file(url, path)
    return path


def _yarn_search(versions: list[str], version_id: str) -> list[str]:
    return sorted(
        [v for v in versions if v.startswith(version_id + "+build")],
        key=lambda x: x.split(".")[-1].zfill(3),
    )


def get_most_recent_yarn_url(version_id: str) -> None | str:
    modern = _yarn_search(get_modern_yarn_versions(), version_id)
    if len(modern):
        ver = modern[-1]
        return f"{YARN_FABRIC_BASE}{ver}/yarn-{ver}-tiny.gz"

    legacy = _yarn_search(get_legacy_yarn_versions(), version_id)
    if len(legacy):
        ver = legacy[-1]
        return f"{YARN_LEGACY_BASE}{ver}/yarn-{ver}-tiny.gz"
    return None


def get_most_recent_yarn(version_id: str) -> None | str:
    key = sha1(f"YARN MAPPING: {version_id}".encode("utf-8")).hexdigest()

    if path := get_cached_file(key):
        return path
    url = get_most_recent_yarn_url(version_id)
    if url is None:
        return None

    path = make_cache_file(key, url.split("/")[-1])
    download_file(url, path)
    return path


def get_mojang_txt(version_id: str, target: str) -> str:
    return get_piston_file(version_id, target + "_mappings")


def get_mojang_tiny(version_id: str, target: str) -> str:
    key = sha1(f"MOJANG TINY: '{version_id}' : '{target}'".encode("utf-8")).hexdigest()

    if path := get_cached_file(key):
        return path
    path = make_cache_file(key, f"{version_id}-{target}.tiny")
    mojmap = get_mojang_txt(version_id, target)

    p = subprocess.Popen(
        [
            "java",
            "-jar",
            MAPPINGIO,
            "convert",
            mojmap,
            path,
            "TINY_2",
        ],
        stdout=subprocess.PIPE,
    )

    # Errors will go to stderr
    if p.wait() != 0:
        exit(1)
    return path


def map_jar_with_tiny(
    dst_jar_file_name: str,
    src_jar: str,
    mapping: str,
    from_ns="official",
    to_ns="named",
    ignore_conflicts=False,
):
    key = sha1(
        f"MAP_TINY: {(dst_jar_file_name, src_jar, mapping, from_ns, to_ns)}".encode(
            "utf-8"
        )
    ).hexdigest()

    if path := get_cached_file(key):
        return path
    dst_out = make_cache_file(key, dst_jar_file_name)

    p = subprocess.Popen(
        ["java", "-jar", REMAPPER, src_jar, dst_out, mapping, from_ns, to_ns]
        + ([] if not ignore_conflicts else ["--ignoreconflicts"]),
    )
    if p.wait() != 0:
        exit(1)
    return dst_out


def map_ss_jar(
    input_jar: str,
    input_mappings: str,
    dst_jar: str,
    exclude: None | str = None,
    auto_lvt: bool = False,
):

    subprocess.check_call(
        ["java", "-jar", SPECIAL_SOURCE2, "map"]
        + (["--auto-lvt", "BASIC"] if auto_lvt else [])
        + (["-e", exclude] if exclude is not None else [])
        + ["-i", input_jar, "-m", input_mappings, "-o", dst_jar],
    )

    return dst_jar


# This function is EVIL. Theoretically this should be run in a container, but I don't really care
def run_spigot_map_command(data_dir, cmd, *args):
    # Attempt to sanatize command
    assert cmd.startswith("java -jar BuildData/bin/SpecialSource")

    cmd = cmd.strip().replace("  ", " ").split(" ")
    cmd = [seg if not seg[0] == "{" else args[int(seg[1])] for seg in cmd]

    print("Running map command:", " ".join(cmd))

    subprocess.check_call(cmd, cwd=dirname(data_dir))


def map_mojang(version_id: str, target: str):
    return map_jar_with_tiny(
        f"{version_id}-{target}-moj-mapped.jar",
        get_piston_file(version_id, target),
        get_mojang_tiny(version_id, target),
        # Not sure why, but mojang has these two in the wrong order?
        "target",
        "source",
    )


def map_yarn(version_id: str, target: str):
    tiny = get_most_recent_yarn(version_id)
    if tiny is None:
        raise RuntimeError("Could not find yarn for version: " + version_id)

    return map_jar_with_tiny(
        f"{version_id}-{target}-yarn-mapped.jar",
        get_piston_file(version_id, target),
        tiny,
    )


# Returns {VERSION.json: URL, ...}
def get_spigot_versions() -> dict[str, str]:
    spigot = download_cached(
        "https://hub.spigotmc.org/versions/", "spigot_versions.htm"
    )
    with open(spigot, "r") as f:
        lines = f.read().splitlines()

    files = [
        # Ex: <a href="1.10.2.json">1.10.2.json</a>
        line.split('"')[1]
        for line in lines
        if line.startswith("<a ")
    ]

    return {
        version: "https://hub.spigotmc.org/versions/" + version for version in files
    }


def map_spigot(spigot_version_id: str, force_piston_server_file: bool = False):
    key = sha1(
        f"MAP SPIGOT: {(spigot_version_id, force_piston_server_file)}".encode("utf-8")
    ).hexdigest()

    if out_path := get_cached_file(key):
        return out_path
    out_path = make_cache_file(key, "spigot_mapped.jar")

    versions = get_spigot_versions()

    assert spigot_version_id + ".json" in versions, "Invalid spigot version"

    initial_json_name = spigot_version_id + ".json"
    url = versions[initial_json_name]

    with open(download_cached(url, initial_json_name), "r") as f:
        ref = json.load(f)["refs"]["BuildData"]

    data_path = set_build_data(ref)

    with open(join(data_path, "info.json")) as f:
        info_json = json.load(f)

    if "serverUrl" in info_json and not force_piston_server_file:
        server_jar = download_cached(info_json["serverUrl"], "server.jar")
    else:
        server_jar = get_piston_file(info_json["minecraftVersion"], "server")

    # Until 1.13.2, you must map yourself
    if 84 > info_json.get("toolsVersion", 0):
        class_mapped = map_ss_jar(
            server_jar,
            join(data_path, "mappings", info_json["classMappings"]),
            mktemp(".jar"),
        )
        _ = map_ss_jar(
            class_mapped,
            join(data_path, "mappings", info_json["memberMappings"]),
            out_path,
        )
        os.remove(class_mapped)
        return out_path
    else:
        class_mapped = mktemp(".jar")
        run_spigot_map_command(
            data_path,
            info_json["classMapCommand"],
            server_jar, # In
            join(data_path, "mappings", info_json["classMappings"]),
            class_mapped, # Out
        )

        if "memberMappings" in info_json:
            run_spigot_map_command(
                data_path,
                info_json["memberMapCommand"],
                class_mapped, # In
                join(data_path, "mappings", info_json["memberMappings"]),
                out_path,  # Out
            )
            os.remove(class_mapped)
        else:
            print("Warning: This version lacks member mappings! Meaning fields and methods cannot be remapped!", file=sys.stderr)
            shutil.move(class_mapped, out_path)


        if "finalMapCommand" in info_json:
            final_mapped = mktemp(".jar")
            run_spigot_map_command(
                data_path,
                info_json["finalMapCommand"],
                out_path, # Ina
                join(data_path, "mappings", info_json["accessTransforms"]),
                join(data_path, "mappings", info_json["classMappings"]),
                final_mapped, # Out
            )
            shutil.move(final_mapped, out_path)
        return out_path


def get_retromcp_versions() -> list[dict]:
    with open(
        download_cached(
            "https://mcphackers.org/versionsV3/versions.json", "versions.json"
        )
    ) as f:
        return json.load(f)


def get_retromcp_version(version_id: str):
    found_version = None
    for version in get_retromcp_versions():
        if version_id == version["id"]:
            found_version = version
            break
    if found_version is None:
        raise IndexError(f"Could not find version {version_id} in RetroMCP")

    return found_version


def get_retromcp_mapping_from_zip(zip_file: str) -> str:
    key = sha1(f"RETROMCP ZIP: {zip_file}".encode("utf-8")).hexdigest()

    if path := get_cached_file(key):
        return path

    with ZipFile(zip_file, "r") as zp:
        mappings = make_cache_file(key, "mappings.tiny")
        zp.extract("mappings.tiny", dirname(mappings))
        return mappings

def get_tiny2_namespaces(tiny_file : str) -> list[str]:
    with open(tiny_file, 'r') as f:
        return [ns.rstrip() for ns in f.readlines()[0].split('\t')[3:]]

def map_retromcp(
    version_id: str,
    target: str,

    from_ns=None,
    to_ns=None,
) -> str:
    found_version = get_retromcp_version(version_id)
    rzip = download_cached(found_version["resources"], "resources.zip")
    version_json = json.load(open(download_cached(found_version["url"], "client.json")))

    if not target in version_json["downloads"]:
        raise IndexError(
            f"Could not find target: '{target}' in {version_id}, options are: {', '.join(version_json['downloads'].keys())}"
        )

    jar_download = version_json["downloads"][target]["url"]
    jar_fname = jar_download.split("/")[-1]
    jar = download_cached(jar_download, jar_fname)
    
    tiny = get_retromcp_mapping_from_zip(rzip)

    namespaces = get_tiny2_namespaces(tiny)

    if from_ns is None:
        from_ns = "official" if 'official' in namespaces else target
    if not from_ns in namespaces:
        raise ValueError(f"Namespace '{from_ns}' not found, options: {', '.join(namespaces)}")

    if to_ns is None:
        to_ns = "named"
    if not to_ns in namespaces:
        raise ValueError(f"Namespace '{to_ns}' not found, options: {', '.join(namespaces)}")


    return map_jar_with_tiny(
        "mapped-" + jar_fname,
        jar,
        tiny,
        from_ns=from_ns,
        to_ns=to_ns,
        ignore_conflicts=True,
    )




import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gryla: Minecraft JAR Downloader & Remapper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: get (raw download)
    get_parser = subparsers.add_parser("get", help="Download a vanilla JAR")
    get_parser.add_argument(
        "version", help="Minecraft Version (e.g. 1.20.1 or @omni@b1.7.3)"
    )
    parser.add_argument(
        "side",
        choices=["client", "server"],
        nargs="?",
        default="client",
        help="Side (client or server, default: client)",
    )
    get_parser.add_argument("-o", "--output", help="Output file path")

    # Subcommand: remap
    remap_parser = subparsers.add_parser(
        "remap", help="Download and remap a JAR to named mappings"
    )
    remap_parser.add_argument(
        "version", help="Minecraft Version (e.g. 1.20.1 or @omni@b1.7.3)"
    )
    parser.add_argument(
        "-m",
        "--mappings",
        choices=["yarn", "mojang", "spigot", "retromcp"],
        default="yarn",
        help="Mappings type (default: yarn)",
    )
    remap_parser.add_argument("-o", "--output", help="Output file path")

    args = parser.parse_args()

    result_path = None

    if args.command == "get":
        result_path = get_piston_file(args.version, args.side)

    elif args.command == "remap":
        if args.mappings == "yarn":
            result_path = map_yarn(args.version, args.side)
        elif args.mappings == "mojang":
            result_path = map_mojang(args.version, args.side)
        elif args.mappings == "spigot":
            result_path = map_spigot(args.version)
        elif args.mappings == "retromcp":
            result_path = map_retromcp(args.version, args.side)
    if result_path:
        output_dest = args.output or os.path.basename(result_path)
        # Check if output is a directory
        if os.path.isdir(output_dest):
            output_dest = os.path.join(output_dest, os.path.basename(result_path))

        print(f"Copying result to: {output_dest}")
        shutil.copyfile(result_path, output_dest)
        print("Done.")



