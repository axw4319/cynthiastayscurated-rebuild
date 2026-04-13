#!/usr/bin/env python3
"""
Image optimization for cynthiastayscurated-rebuild.

For each image in /images/:
  - Convert PNG photos → WebP (quality 82) + compressed JPEG fallback
  - Convert JPEG → WebP (quality 82) + re-compressed JPEG
  - Keep PNG logos/icons as PNG (optimized)
  - Print before/after sizes

After running, update HTML with update-picture-tags.py to use <picture> elements.

Usage: python3 tools/optimize-images.py [--dry-run]
"""
import os
import sys
from pathlib import Path
from PIL import Image

SITE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = SITE_DIR / 'images'

# These are logos/icons with transparency — keep as PNG, just optimize
PNG_KEEP_AS_PNG = {
    'cynthia-stays-curated-logo.png',
    'cynthia-stays-curated-logo-horizontal.png',
}

JPEG_QUALITY = 82
WEBP_QUALITY = 82
DRY_RUN = '--dry-run' in sys.argv

def fmt(b):
    if b >= 1024 * 1024:
        return f'{b/1024/1024:.2f}MB'
    return f'{b/1024:.0f}KB'

def savings_pct(orig, new):
    if orig == 0:
        return '0%'
    return f'-{100 * (orig - new) // orig}%'

def optimize_png_logo(src_path):
    """Re-save PNG with optimize=True to shrink file size without quality loss."""
    orig_size = src_path.stat().st_size
    img = Image.open(src_path)
    if not DRY_RUN:
        img.save(src_path, 'PNG', optimize=True)
    new_size = src_path.stat().st_size if not DRY_RUN else orig_size
    return orig_size, new_size

def convert_image(src_path):
    """
    For a photo PNG or JPEG:
    - Create a .webp version (primary, best quality/size)
    - Create a .jpg version (fallback for old browsers)
    - Leave the original in place (used as ultimate fallback)
    Returns (orig_size, webp_size, jpg_size, webp_path, jpg_path)
    """
    orig_size = src_path.stat().st_size
    img = Image.open(src_path).convert('RGB')  # drop alpha for photos

    stem = src_path.stem
    webp_path = src_path.parent / f'{stem}.webp'
    jpg_path  = src_path.parent / f'{stem}.jpg'

    webp_size = orig_size  # default for dry-run
    jpg_size  = orig_size

    if not DRY_RUN:
        img.save(webp_path, 'WEBP', quality=WEBP_QUALITY, method=6)
        img.save(jpg_path,  'JPEG', quality=JPEG_QUALITY, optimize=True)
        webp_size = webp_path.stat().st_size
        jpg_size  = jpg_path.stat().st_size

    return orig_size, webp_size, jpg_size, webp_path, jpg_path

def main():
    print(f'\n=== Image Optimization {"(DRY RUN)" if DRY_RUN else ""} ===\n')

    total_orig = 0
    total_webp = 0
    results = []

    for img_path in sorted(IMAGES_DIR.iterdir()):
        if img_path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
            continue

        name = img_path.name

        if name in PNG_KEEP_AS_PNG:
            orig, new = optimize_png_logo(img_path)
            total_orig += orig
            total_webp += new
            print(f'  [PNG logo]  {name}')
            print(f'              {fmt(orig)} → {fmt(new)} ({savings_pct(orig, new)})')
            results.append({'name': name, 'type': 'png_logo', 'orig': orig, 'new': new})
        else:
            orig, webp_sz, jpg_sz, webp_path, jpg_path = convert_image(img_path)
            total_orig += orig
            total_webp += webp_sz
            print(f'  [convert]   {name}')
            print(f'              orig: {fmt(orig)}')
            print(f'              webp: {fmt(webp_sz)} ({savings_pct(orig, webp_sz)}) ← browsers will use this')
            print(f'              jpg:  {fmt(jpg_sz)}  ({savings_pct(orig, jpg_sz)}) ← fallback')
            results.append({
                'name': name, 'type': 'photo',
                'orig': orig, 'webp': webp_sz, 'jpg': jpg_sz,
                'webp_name': webp_path.name, 'jpg_name': jpg_path.name
            })
        print()

    print(f'{"─"*50}')
    print(f'Total original: {fmt(total_orig)}')
    print(f'Total WebP:     {fmt(total_webp)} ({savings_pct(total_orig, total_webp)} smaller)')
    print(f'\nNext step: python3 tools/update-picture-tags.py')

    return results

if __name__ == '__main__':
    main()
