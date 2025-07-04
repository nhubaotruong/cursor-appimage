#!/usr/bin/env python3

import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

# Keep original headers
headers = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
}


def download_progress_hook(count, blocksize, totalsize):
    if totalsize > 0:
        percent = min(int(count * blocksize * 100 / totalsize), 100)
        sys.stdout.write(f"\rDownloading... {percent}%")
        if percent == 100:
            sys.stdout.write("\n")
    sys.stdout.flush()


def apply_patch(product_path, patch_data):
    with open(file=product_path, mode="r") as product_file:
        product_data = json.load(product_file)

    # Apply patches in memory
    for key in patch_data.keys():
        product_data[key] = patch_data[key]

    with open(file=product_path, mode="w") as product_file:
        json.dump(obj=product_data, fp=product_file, indent="\t")


# Get latest tag
latest_tag = (
    subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"], cwd=os.getcwd()
    )
    .decode()
    .strip()
)
print("latest_tag", latest_tag)
# Check version from headers first
url = "https://www.cursor.com/api/download?platform=linux-x64&releaseTrack=stable"
get_version_req = urllib.request.Request(url, method="GET", headers=headers)
with urllib.request.urlopen(get_version_req) as get_version_response:
    get_version_data = json.load(get_version_response)

download_url = get_version_data.get("downloadUrl")
latest_version = get_version_data.get("version")

print("latest_version", latest_version)
if latest_version == latest_tag:
    print("No update needed")
    sys.exit(0)

# if version == latest_tag:
#     with open(os.environ.get('GITHUB_ENV', os.devnull), 'a') as f:
#         f.write("APP_UPDATE_NEEDED=false\n")
#     sys.exit(0)

# Set environment variables for GitHub Actions
with open(os.environ.get("GITHUB_ENV", os.devnull), "a") as f:
    f.write("APP_UPDATE_NEEDED=true\n")
    f.write(f"VERSION={latest_version}\n")

os.environ["APPIMAGE_EXTRACT_AND_RUN"] = "1"

# Handle Cursor AppImage download and extraction
with tempfile.NamedTemporaryFile(suffix=".AppImage", delete=False) as tmp_appimage:
    opener = urllib.request.build_opener()
    opener.addheaders = list(headers.items())
    urllib.request.install_opener(opener)
    print("Downloading Cursor AppImage...")
    urllib.request.urlretrieve(download_url, tmp_appimage.name, download_progress_hook)
    tmp_appimage.flush()
    os.fsync(tmp_appimage.fileno())
    tmp_name = tmp_appimage.name

# Set permissions after file is closed
os.chmod(tmp_name, 0o755)

# Create and extract AppImage
os.makedirs("cursor.AppDir", exist_ok=True)
subprocess.run(
    [tmp_name, "--appimage-extract"],
    check=True,
    cwd="cursor.AppDir",
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Clean up after extraction is complete
try:
    os.unlink(tmp_name)
except OSError:
    print(f"Warning: Could not remove temporary file {tmp_name}")

# Handle appimagetool and patches in separate temp directory
with tempfile.TemporaryDirectory() as tools_tmpdir:
    machine = platform.machine()

    # Download and setup appimagetool
    appimagetool_url = f"https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{machine}.AppImage"
    appimagetool_path = os.path.join(tools_tmpdir, "appimagetool")
    print("Downloading appimagetool...")
    urllib.request.urlretrieve(
        appimagetool_url, appimagetool_path, download_progress_hook
    )
    os.chmod(appimagetool_path, 0o755)

    # Extract appimagetool
    original_dir = os.getcwd()
    # os.chdir(tools_tmpdir)
    subprocess.run(
        [appimagetool_path, "--appimage-extract"],
        check=True,
        cwd=tools_tmpdir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # os.chdir(original_dir)
    appimagetool_dir = os.path.join(tools_tmpdir, "squashfs-root")

    # Set permissions
    os.chmod("cursor.AppDir/squashfs-root", 0o755)

    # Download and apply patches
    # patch_urls = {
        # "features": "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-features",
        # "marketplace": "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-marketplace",
    # }

    # product_path = "cursor.AppDir/squashfs-root/usr/share/cursor/resources/app/product.json"

    # for patch_url in patch_urls.values():
    #     req = urllib.request.Request(patch_url, headers=headers)
    #     with urllib.request.urlopen(req) as response:
    #         patch_data = json.load(response)
    #         apply_patch(
    #             product_path,
    #             patch_data,
    #         )
    
    # with open(file=product_path, mode="r") as product_file:
    #     product_data = json.load(product_file)

    # Apply patches in memory
    # product_data.pop("extensionMaxVersions", None)
    # product_data.pop("linkProtectionTrustedDomains", None)

    # with open(file=product_path, mode="w") as product_file:
    #     json.dump(obj=product_data, fp=product_file, indent="\t")

    os.remove(
        "cursor.AppDir/squashfs-root/usr/share/cursor/resources/appimageupdatetool.AppImage"
    )

    # Build final AppImage
    # Create dist directory with absolute path
    dist_dir = os.path.join(original_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    github_repo = os.environ.get("GITHUB_REPOSITORY", "").replace("/", "|")
    update_info = f"gh-releases-zsync|{github_repo}|latest|Cursor*.AppImage.zsync"
    output_name = f"Cursor-{latest_version}-{machine}.AppImage"

    subprocess.run(
        [
            os.path.join(appimagetool_dir, "AppRun"),
            "-n",
            "--comp",
            "zstd",
            os.path.join(original_dir, "cursor.AppDir", "squashfs-root"),
            "--updateinformation",
            update_info,
            output_name,
        ],
        check=True,
    )

for root, _, files in os.walk(pathlib.Path.home()):
    for file in files:
        if file.startswith(f"Cursor-{latest_version}-{machine}"):
            src = os.path.join(root, file)
            dst = os.path.join(dist_dir, file)
            shutil.move(src, dst)
