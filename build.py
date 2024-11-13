#!/usr/bin/env python3

import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.request
import json

# Keep original headers
headers = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
}


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
        ['git', 'describe', '--tags', '--abbrev=0'], cwd=os.getcwd()
    )
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

# Set environment variables for GitHub Actions
with open(os.environ.get('GITHUB_ENV', os.devnull), 'a') as f:
    f.write("APP_UPDATE_NEEDED=true\n")
    f.write(f"VERSION={version}\n")

os.environ['APPIMAGE_EXTRACT_AND_RUN'] = '1'

# Handle Cursor AppImage download and extraction
with tempfile.NamedTemporaryFile(suffix='.AppImage', delete=False) as tmp_appimage:
    opener = urllib.request.build_opener()
    opener.addheaders = list(headers.items())
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, tmp_appimage.name)
    os.chmod(tmp_appimage.name, 0o755)

    # Create and extract AppImage
    os.makedirs("cursor.AppDir", exist_ok=True)
    subprocess.run(
        [tmp_appimage.name, "--appimage-extract"], check=True, cwd="cursor.AppDir"
    )

# Clean up Cursor AppImage
os.unlink(tmp_appimage.name)

# Handle appimagetool and patches in separate temp directory
with tempfile.TemporaryDirectory(delete=False) as tools_tmpdir:
    machine = platform.machine()

    # Download and setup appimagetool
    appimagetool_url = f"https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-{machine}.AppImage"
    appimagetool_path = os.path.join(tools_tmpdir, "appimagetool")
    urllib.request.urlretrieve(appimagetool_url, appimagetool_path)
    os.chmod(appimagetool_path, 0o755)

    # Extract appimagetool
    original_dir = os.getcwd()
    # os.chdir(tools_tmpdir)
    subprocess.run(
        [appimagetool_path, "--appimage-extract"], check=True, cwd=tools_tmpdir
    )
    # os.chdir(original_dir)
    appimagetool_dir = os.path.join(tools_tmpdir, "squashfs-root")

    # Set permissions
    os.chmod("cursor.AppDir/squashfs-root", 0o755)

    # Download and apply patches
    patch_urls = {
        "features": "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-features",
        "marketplace": "https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-marketplace",
    }

    for patch_url in patch_urls.values():
        req = urllib.request.Request(patch_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            patch_data = json.load(response)
            apply_patch(
                "cursor.AppDir/squashfs-root/resources/app/product.json", patch_data
            )

    # Build final AppImage
    os.makedirs("dist", exist_ok=True)
    github_repo = os.environ.get('GITHUB_REPOSITORY', '').replace('/', '|')
    update_info = f"gh-releases-zsync|{github_repo}|latest|Cursor*.AppImage.zsync"
    output_name = os.path.join(
        original_dir, "dist", f"Cursor-{version}-{machine}.AppImage"
    )

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
        cwd=original_dir,
    )