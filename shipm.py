#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import tarfile
import zipfile
import shutil
import requests

SHIPM_UPDATE_URL = "https://raw.githubusercontent.com/PtaterTot/Shipment/refs/heads/main/shipm.py"

def self_update():
    print("Checking for updates...")

    try:
        r = requests.get(SHIPM_UPDATE_URL)
        if r.status_code != 200:
            print("Failed to fetch latest shipm.py")
            return

        new_code = r.text

        current_path = os.path.realpath(sys.argv[0])

        # On Windows with .bat wrapper
        if current_path.endswith(".bat"):
            # Replace shipm.py next to it
            current_path = os.path.join(os.path.dirname(current_path), "shipm.py")

        print(f"Updating {current_path} ...")

        # Write new version
        with open(current_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        print("Update complete!")

        # Make it executable on Unix
        if platform.system().lower() != "windows":
            os.chmod(current_path, 0o755)

    except Exception as e:
        print("Update failed:", e)


# ========================
# CONFIG: Your GitHub repos + dependencies
# ========================
PACKAGES = {
    "fastfetch": {
        "repo": "fastfetch-cli/fastfetch",
        "deps": {
            "debian": ["curl", "libc6"],
            "arch": ["curl"],
            "fedora": ["curl"],
            "windows": []
        }
    },

    "nvim": {
        "repo": "neovim/neovim",
        "deps": {
            "debian": ["python3"],
            "arch": ["python"],
            "fedora": ["python3"],
            "windows": []
        }
    }
}

# ========================
# Detect OS + Distro
# ========================
def detect_system():
    system = platform.system().lower()

    if system == "linux":
        if os.path.exists("/etc/debian_version"):
            distro = "debian"
        elif os.path.exists("/etc/arch-release"):
            distro = "arch"
        elif os.path.exists("/etc/fedora-release"):
            distro = "fedora"
        else:
            distro = "unknown"
    elif system == "windows":
        distro = "windows"
    else:
        distro = "unknown"

    return system, distro

# ========================
# Install dependencies
# ========================
def install_dependencies(pkg_info, distro):
    deps = pkg_info["deps"].get(distro, [])
    if not deps:
        print("No dependencies needed.")
        return

    print(f"Installing dependencies: {' '.join(deps)}")

    if distro == "debian":
        subprocess.run(["sudo", "apt", "update"])
        subprocess.run(["sudo", "apt", "install", "-y"] + deps)

    elif distro == "arch":
        subprocess.run(["sudo", "pacman", "-Sy", "--needed"] + deps)

    elif distro == "fedora":
        subprocess.run(["sudo", "dnf", "install", "-y"] + deps)

    elif distro == "windows":
        print("Windows: please install dependencies manually (or extend me!)")

    else:
        print("Unknown distro, skipping dependency install.")

# ========================
# Download GitHub Release
# ========================
def download_latest(repo, output_dir="downloads"):
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    r = requests.get(api_url)

    if r.status_code != 200:
        print(f"Error: Could not fetch release for {repo}")
        return None

    release = r.json()
    assets = release.get("assets", [])
    if not assets:
        print("No assets found in latest release.")
        return None

    os.makedirs(output_dir, exist_ok=True)

    downloaded_files = []

    for asset in assets:
        url = asset["browser_download_url"]
        filename = asset["name"]
        path = os.path.join(output_dir, filename)

        print(f"Downloading {filename}")

        with requests.get(url, stream=True) as f:
            f.raise_for_status()
            with open(path, "wb") as out:
                for chunk in f.iter_content(chunk_size=8192):
                    if chunk:
                        out.write(chunk)

        print(f"Saved to {path}")
        downloaded_files.append(path)

    return downloaded_files

# =============================
# Install extracted packages
# =============================
def install_file(path, system, distro):
    print(f"Installing {os.path.basename(path)} ...")

    # ---- .deb ----
    if path.endswith(".deb") and system == "linux":
        if distro == "debian":
            subprocess.run(["sudo", "apt", "install", "-y", path])
        else:
            print("Warning: .deb on non-Debian systems may not work.")
            subprocess.run(["sudo", "dpkg", "-i", path])

    # ---- .rpm ----
    elif path.endswith(".rpm") and system == "linux":
        subprocess.run(["sudo", "rpm", "-i", path])

    # ---- .zip ----
    elif path.endswith(".zip"):
        extract_dir = path + "_extracted"
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")

    # ---- tar.* ----
    elif path.endswith(".tar.gz") or path.endswith(".tgz") or path.endswith(".tar.xz") or path.endswith(".tar"):
        extract_dir = path + "_extracted"
        os.makedirs(extract_dir, exist_ok=True)
        with tarfile.open(path, "r:*") as tar_ref:
            tar_ref.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")

    else:
        print(f"Unknown file type: {path}")

# ========================
# Main CLI
# ========================
def main():
    if len(sys.argv) < 3:
        print("Usage: shipm <install|deps> <package>")
        return

    command = sys.argv[1]
    pkg = sys.argv[2]

    if pkg not in PACKAGES:
        print(f"Unknown package '{pkg}'")
        print("Available:", ", ".join(PACKAGES.keys()))
        return

    pkg_info = PACKAGES[pkg]
    repo = pkg_info["repo"]

    system, distro = detect_system()
    print(f"System: {system}, Distro: {distro}")

    # ---- deps command ----
    if command == "deps":
        install_dependencies(pkg_info, distro)
        return

    # ---- install command ----
    if command == "install":
        install_dependencies(pkg_info, distro)

        files = download_latest(repo)
        if not files:
            return

        for f in files:
            install_file(f, system, distro)

    else:
        print(f"Unknown command '{command}'")


if __name__ == "__main__":
    main()
