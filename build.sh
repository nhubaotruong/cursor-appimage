#!/usr/bin/env bash

# # Determine if we're running inside GitHub actions.
# GITHUB_RUNNING_ACTION=$GITHUB_ACTIONS

# APP_NAME=Lark
# VERSION=$(wget -qO- https://www.larksuite.com/api/downloads | jq -r '.versions.Linux_deb_x64.version_number' | cut -d'@' -f2)

# echo $GITHUB_REPOSITORY

# if [ "$GITHUB_RUNNING_ACTION" == true ]; then
#     # If we check only for version here.
#     RELEASE_VERSION=$(gh api -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" /repos/$GITHUB_REPOSITORY/releases/latest | jq -r ".name" | sed 's/'"$APP_NAME"' AppImage //g')

#     if [ "$VERSION" = "$RELEASE_VERSION" ]; then
#         echo "::set-output name=app_update_needed::false"
#         echo "APP_UPDATE_NEEDED=false" >>"$GITHUB_ENV"
#         # Always exit here.
#         echo "No update needed. Exiting."
#         exit 0
#     else
#         echo "::set-output name=app_update_needed::true"
#         echo "Update required."
#         echo "APP_UPDATE_NEEDED=true" >>"$GITHUB_ENV"
#     fi
# fi

# wget -cO ./pkg2appimage.AppImage https://github.com/AppImageCommunity/pkg2appimage/releases/download/continuous/pkg2appimage--x86_64.AppImage

# chmod +x ./pkg2appimage.AppImage

# if [ "$GITHUB_RUNNING_ACTION" == true ]; then
#     _updateinformation="gh-releases-zsync|$($GITHUB_REPOSITORY | tr '/' '|')|latest|Lark*.AppImage.zsync" ./pkg2appimage.AppImage lark.yml
#     echo "APP_NAME=$APP_NAME" >>"$GITHUB_ENV"
#     echo "APP_SHORT_NAME=$APP_NAME" >>"$GITHUB_ENV"
#     echo "APP_VERSION=$VERSION" >>"$GITHUB_ENV"
# else
#     ./pkg2appimage.AppImage lark.yml
# fi
set -eu

export APPIMAGE_EXTRACT_AND_RUN=1

curl -L https://downloader.cursor.sh/linux/appImage/x64 -o app.AppImage

chmod +x app.AppImage

./app.AppImage --appimage-extract

curl -L https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-features -o /tmp/patch_features.json
curl -L https://aur.archlinux.org/cgit/aur.git/plain/patch.json?h=code-marketplace -o /tmp/patch_marketplace.json

python patch.py /tmp/patch_features.json
python patch.py /tmp/patch_marketplace.json

curl -L "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$(uname -m).AppImage" -o /tmp/appimagetool
chmod +x /tmp/appimagetool

VERSION=$(jq -r '.version' squashfs-root/resources/app/package.json)
chmod 0755 squashfs-root

# GH_USER="$( echo $GITHUB_REPOSITORY | grep -o ".*/" | head -c-2 )"
# GH_REPO="$( echo $GITHUB_REPOSITORY | grep -o "/.*" | cut -c2- )"
GH_USER="nhubaotruong"
GH_REPO="cursor-appimage"

/tmp/appimagetool -n --comp gzip squashfs-root --updateinformation "gh-releases-zsync|$GH_USER|$GH_REPO|latest|Cursor*.AppImage.zsync" Cursor-"$VERSION"-"$(uname -m)".AppImage

mkdir -p dist
mv Cursor-"$VERSION"-"$(uname -m)".AppImage* dist
