#!/usr/bin/env python3
"""
Replace <img src="images/foo.jpg"> with <picture> elements that serve WebP
to modern browsers with a JPEG/PNG fallback.

Only replaces images that have a corresponding .webp file in /images/.
Logos (PNG files without a WebP equivalent) are left as <img>.

Usage: python3 tools/update-picture-tags.py [--dry-run]
"""
import re
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = SITE_DIR / 'images'
DRY_RUN = '--dry-run' in sys.argv

PAGES = [p for p in SITE_DIR.glob('*.html') if p.name not in {'render-form-source.html'}]

# Build set of images that have a WebP version
webp_available = {p.stem for p in IMAGES_DIR.glob('*.webp')}

IMG_RE = re.compile(
    r'<img\b([^>]*?)\bsrc="(images/([^"]+))"([^>]*)>',
    re.IGNORECASE | re.DOTALL
)

def get_attr(attrs_str, attr_name):
    m = re.search(rf'\b{attr_name}="([^"]*)"', attrs_str, re.I)
    return m.group(1) if m else None

def strip_attr(attrs_str, attr_name):
    return re.sub(rf'\s*\b{attr_name}="[^"]*"', '', attrs_str, flags=re.I).strip()

def build_picture(before_attrs, src, stem, ext, after_attrs):
    """Return a <picture> element wrapping the img."""
    webp_src = f'images/{stem}.webp'
    fallback_src = f'images/{stem}.jpg' if ext.lower() in ('.png',) else src

    # Pull out loading and class to put on the img tag inside picture
    all_attrs = (before_attrs + ' ' + after_attrs).strip()
    alt = get_attr(all_attrs, 'alt') or ''
    loading = get_attr(all_attrs, 'loading') or ''
    cls = get_attr(all_attrs, 'class') or ''
    width = get_attr(all_attrs, 'width') or ''
    height = get_attr(all_attrs, 'height') or ''

    img_attrs = f'src="{fallback_src}"'
    if alt: img_attrs += f' alt="{alt}"'
    if cls: img_attrs += f' class="{cls}"'
    if loading: img_attrs += f' loading="{loading}"'
    if width: img_attrs += f' width="{width}"'
    if height: img_attrs += f' height="{height}"'

    return (
        f'<picture>'
        f'<source srcset="{webp_src}" type="image/webp">'
        f'<img {img_attrs}>'
        f'</picture>'
    )

def process_file(fp):
    content = original = fp.read_text(encoding='utf-8')
    replacements = 0

    def replacer(m):
        nonlocal replacements
        before_attrs = m.group(1)
        src = m.group(2)          # e.g. images/disney-world-cinderella-castle-hero.png
        filename = m.group(3)     # e.g. disney-world-cinderella-castle-hero.png
        after_attrs = m.group(4)

        p = Path(filename)
        stem = p.stem
        ext = p.suffix

        # Only wrap in <picture> if we have a WebP version
        if stem not in webp_available:
            return m.group(0)

        replacements += 1
        return build_picture(before_attrs, src, stem, ext, after_attrs)

    content = IMG_RE.sub(replacer, content)

    if content != original:
        if not DRY_RUN:
            fp.write_text(content, encoding='utf-8')
        print(f'  {fp.name}: {replacements} img → <picture> replacements')
    else:
        print(f'  {fp.name}: no changes')

    return replacements

def main():
    print(f'\n=== Update <picture> Tags {"(DRY RUN)" if DRY_RUN else ""} ===\n')

    if not list(IMAGES_DIR.glob('*.webp')):
        print('No WebP files found in images/ — run optimize-images.py first.')
        return

    print(f'WebP versions available for: {", ".join(sorted(webp_available))}\n')

    total = 0
    for fp in sorted(PAGES):
        total += process_file(fp)

    print(f'\nTotal replacements: {total}')
    if not DRY_RUN and total:
        print('Run node tools/qa-sweep.js to verify.')

if __name__ == '__main__':
    main()
