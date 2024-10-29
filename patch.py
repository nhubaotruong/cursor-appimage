#!/usr/bin/env python3
import json
import sys
import os

product_path = f"{os.curdir}/squashfs-root/resources/app/product.json"
patch_path = sys.argv[1]
cache_path = "/tmp/cache.json"


def patch():
    with open(file=product_path, mode="r") as product_file:
        product_data = json.load(product_file)
    with open(file=patch_path, mode="r") as patch_file:
        patch_data = json.load(patch_file)
    cache_data = {}
    for key in patch_data.keys():
        if key in product_data:
            cache_data[key] = product_data[key]
        product_data[key] = patch_data[key]
    with open(file=product_path, mode="w") as product_file:
        json.dump(obj=product_data, fp=product_file, indent="\t")
    with open(file=cache_path, mode="w") as cache_file:
        json.dump(obj=cache_data, fp=cache_file, indent="\t")


patch()
