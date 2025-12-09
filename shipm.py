#!/usr/bin/env python3
import os
import sys
import json
import platform
import subprocess
import tarfile
import zipfile
import shutil
import requests
from pathlib import Path

# ============================
# CONFIGURATION
# ============================

REPO_JSON_URL = "https://raw.githubusercontent.com/YourUser/Shipment/main/packages.json"

CACHE_DIR = Path.home() / ".shipm" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_JSON = Path.home() / ".shipm" / "packages.json"

UPDATE_URL = "https://raw.githubusercontent.com/YourUser/Shipment/main/shipm.py"

# ============================
# JSON Repo Loader + Caching
# ============================

def load_packages():
    """Load package index from GitHub with local cache fallback."""
    try:
        print("Fetching package index...")
        r = requests.get(REPO_JSON_URL, timeout=5)

        if r.status_code == 200:
            LOCAL_JSON.write_text(r.text, encoding="utf-8")
            print("Package index updated.")
        else:
            print("Failed to update package index, using cached file...")

    except:
        print("Network error, using cached package index...")

    if LOCAL_JSON.exists():
        return json.loads(LOCAL_JSON.read_text(encoding="utf-8"))

    print("ERROR: No package index available.")
    return {}

# ============================
# Self Update
# ============================

def self_update():
    print("Checking for updates...")
    try:
        new = requests.get(UPDATE_URL).text
        current = os.path.realpath(sys.argv[0])
        with open(current, "w", encoding="utf-8") as f:
            f.write(new)
        os.chmod(current, 0o755)
        print("Updated successfully!")
    except Exception as e:
        print("Update failed:", e)

# ============================
# System Detection
# ============================

def detect_system():
    system = platform.system().lower()

    if system == "linux":
        if os.path.exists("/etc/debian_version"):
            return "linux", "debian"
        if os.path.exists("/etc/arch-release"):
            return "linux", "arch"
        if os.path.exists("/etc/fedora-release"):
            return "linux", "fedora"
        return "linux", "unknown"

    if system == "windows":
        return "windows", "windows"

    return system, "unknown"

# ============================
# Dependencies
# ============================

def install_dependencies(deps, distro):
    if distro not in deps:
        print("No dependencies for this distro.")
        return

    need = deps[distro]
    if not need:
        print("No dependencies needed.")
        return

    print("Installing dependencies:", " ".join(need))

    if distro == "debian":
        subprocess.run(["sudo", "apt", "update"])
        subprocess.run(["sudo", "apt", "install", "-y"] + need)

    elif distro == "arch":
        subprocess.run(["sudo", "pacman", "-Sy", "--needed"] + need)

    elif distro == "fedora":
        subprocess.run(["sudo", "dnf", "install", "-y"] + need)

# ============================
# Release Download w/ Cache
# ============================

def download_latest(repo, match, force=False):
    """Download only the asset matching the user’s distro."""
    api = f"https://api.github.com/repos/{repo}/releases/latest"

    r = requests.get(api)
    if r.status_code != 200:
        print("Failed to fetch release.")
        return None

    assets = r.json().get("assets", [])

    # Pick asset that matches substring (e.g., ".deb")
    for asset in assets:
        if match in asset["name"]:
            url = asset["browser_download_url"]
            filename = asset["name"]
            local_path = CACHE_DIR / filename

            # Cached?
            if local_path.exists() and not force:
                print(f"Using cached file: {local_path}")
                return local_path

            print(f"Downloading {filename}...")
            with requests.get(url, stream=True) as f:
                f.raise_for_status()
                with open(local_path, "wb") as out:
                    for chunk in f.iter_content(8192):
                        out.write(chunk)

            print(f"Saved to cache: {local_path}")
            return local_path

    print("No matching asset found.")
    return None

# ============================
# Install extracted data
# ============================

def install_file(path, system, distro):
    path = str(path)
    print(f"Installing {path} ...")

    if path.endswith(".deb"):
        subprocess.run(["sudo", "apt", "install", "-y", path])

    elif path.endswith(".rpm"):
        subprocess.run(["sudo", "rpm", "-i", path])

    elif path.endswith(".zip"):
        dest = path + "_extracted"
        with zipfile.ZipFile(path) as z:
            z.extractall(dest)
        print("Extracted to", dest)

    elif any(path.endswith(x) for x in [".tar.gz", ".tgz", ".tar.xz"]):
        dest = path + "_extracted"
        with tarfile.open(path, "r:*") as t:
            t.extractall(dest)
        print("Extracted to", dest)

# ============================
# Main CLI
# ============================

def main():
    if len(sys.argv) < 2:
        print("Usage: shipm <install|deps|update> <package>")
        return

    command = sys.argv[1]

    if command == "update":
        self_update()
        return

    packages = load_packages()

    if command == "help":
        print("Available packages:", ", ".join(packages.keys()))
        return

    if len(sys.argv) < 3:
        print("Missing package name.")
        return

    pkg = sys.argv[2]

    if pkg not in packages:
        print("Unknown package:", pkg)
        return

    pkg_info = packages[pkg]

    system, distro = detect_system()
    print(f"System: {system}, Distro: {distro}")

    # deps
    if command == "deps":
        install_dependencies(pkg_info["deps"], distro)
        return

    # install
    if command == "install":
        install_dependencies(pkg_info["deps"], distro)

        # match correct file type
        match = pkg_info["assets"].get(distro, "")
        f = download_latest(pkg_info["repo"], match)
        if f:
            install_file(f, system, distro)
        return

    print("Unknown command:", command)

if __name__ == "__main__":
    main()
