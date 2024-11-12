#!/usr/bin/env python3

import os
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

# Get latest tag
latest_tag = (
    subprocess.check_output(['git', 'describe', '--tags', '--abbrev=0'])
    .decode()
    .strip()
)

# Check version from headers first
url = "https://downloader.cursor.sh/linux/appImage/x64"
req = urllib.request.Request(url, method='GET', headers=headers)
response = urllib.request.urlopen(req)
content_disposition = response.headers.get('Content-Disposition', '')

cursor_version_search = re.search(r"\d+\.\d+(?:\.\d+(?:\.\d+)?)?", content_disposition)
if not cursor_version_search:
    print("Failed to get cursor version")
    sys.exit(1)

version = cursor_version_search.group(0)
if version == latest_tag:
    with open(os.environ.get('GITHUB_ENV', os.devnull), 'a') as f:
        f.write("APP_UPDATE_NEEDED=false\n")
    sys.exit(0)

# Set environment variables for GitHub Actions since update is needed
with open(os.environ.get('GITHUB_ENV', os.devnull), 'a') as f:
    f.write("APP_UPDATE_NEEDED=true\n")
    f.write(f"VERSION={version}\n")

os.environ['APPIMAGE_EXTRACT_AND_RUN'] = '1'

# Now download the actual AppImage using a new request
req = urllib.request.Request(url, method='GET', headers=headers)
response = urllib.request.urlopen(req)

# Handle Cursor AppImage download and extraction
with tempfile.NamedTemporaryFile(suffix='.AppImage', delete=False) as tmp_appimage:
    tmp_appimage.write(response.read())
    os.chmod(tmp_appimage.name, 0o755)

    # Create and extract AppImage
    os.makedirs("cursor.AppDir", exist_ok=True)
    os.chdir("cursor.AppDir")
    subprocess.run([tmp_appimage.name, "--appimage-extract"], check=True)
    os.chdir("..")

# Clean up Cursor AppImage
os.unlink(tmp_appimage.name)

# Handle appimagetool and patches in separate temp directory
with tempfile.TemporaryDirectory() as tools_tmpdir:
    # Download and setup appimagetool
    machine = platform.machine()
    appimagetool_url = f"https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{machine}.AppImage"
    appimagetool_path = os.path.join(tools_tmpdir, "appimagetool")
    urllib.request.urlretrieve(appimagetool_url, appimagetool_path)
    os.chmod(appimagetool_path, 0o755)

    # Extract appimagetool
    subprocess.run([appimagetool_path, "--appimage-extract"], check=True)
    appimagetool_dir = os.path.join(tools_tmpdir, "appimagetool.AppDir")
    shutil.move("squashfs-root", appimagetool_dir)

    # Set permissions
    os.chmod("cursor.AppDir/squashfs-root", 0o755)

    # Download patch files
    patch_features_url = (
        "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-features"
    )
    patch_marketplace_url = (
        "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-marketplace"
    )
    patch_features_path = os.path.join(tools_tmpdir, "patch_features.json")
    patch_marketplace_path = os.path.join(tools_tmpdir, "patch_marketplace.json")
    urllib.request.urlretrieve(patch_features_url, patch_features_path)
    urllib.request.urlretrieve(patch_marketplace_url, patch_marketplace_path)

    # Apply patches
    subprocess.run(["python", "patch.py", patch_features_path], check=True)
    subprocess.run(["python", "patch.py", patch_marketplace_path], check=True)

    # Build final AppImage
    github_repo = os.environ.get('GITHUB_REPOSITORY', '').replace('/', '|')
    update_info = f"gh-releases-zsync|{github_repo}|latest|Cursor*.AppImage.zsync"
    output_name = f"Cursor-{version}-{machine}.AppImage"

    subprocess.run(
        [
            os.path.join(appimagetool_dir, "AppRun"),
            "-n",
            "--comp",
            "zstd",
            "cursor.AppDir/squashfs-root",
            "--updateinformation",
            update_info,
            output_name,
        ],
        check=True,
    )

    # Move final files to dist directory
    os.makedirs("dist", exist_ok=True)
    for file in os.listdir():
        if file.startswith(f"Cursor-{version}-{machine}"):
            shutil.move(file, os.path.join("dist", file))
