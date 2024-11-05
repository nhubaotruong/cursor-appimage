#!/usr/bin/env bash

set -eu

export APPIMAGE_EXTRACT_AND_RUN=1

# Get version info first
curl -L https://downloader.cursor.sh/linux/appImage/x64 -o app.AppImage
chmod +x app.AppImage
mkdir -p cursor.AppDir
cd cursor.AppDir
../app.AppImage --appimage-extract
cd ..
VERSION=$(jq -r '.version' cursor.AppDir/squashfs-root/resources/app/package.json)

LATEST_TAG=$(git describe --tags --abbrev=0)
if [ "$VERSION" == "$LATEST_TAG" ]; then
    echo "APP_UPDATE_NEEDED=false" >>$GITHUB_ENV
    exit 0
fi
echo "APP_UPDATE_NEEDED=true" >>$GITHUB_ENV
echo "VERSION=$VERSION" >>$GITHUB_ENV

# Only download and setup appimagetool if update is needed
curl -L "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$(uname -m).AppImage" -o /tmp/appimagetool
chmod +x /tmp/appimagetool
/tmp/appimagetool --appimage-extract && mv ./squashfs-root /tmp/appimagetool.AppDir

# Update paths for the rest of the script to use cursor.AppDir
chmod 0755 cursor.AppDir/squashfs-root

curl -L https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-features -o /tmp/patch_features.json
curl -L https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-marketplace -o /tmp/patch_marketplace.json

python patch.py /tmp/patch_features.json
python patch.py /tmp/patch_marketplace.json

/tmp/appimagetool.AppDir/AppRun -n --comp zstd cursor.AppDir/squashfs-root --updateinformation "gh-releases-zsync|${GITHUB_REPOSITORY/\//|}|latest|Cursor*.AppImage.zsync" Cursor-"$VERSION"-"$(uname -m)".AppImage

mkdir -p dist
mv Cursor-"$VERSION"-"$(uname -m)".AppImage* dist
