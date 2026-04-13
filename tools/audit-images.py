#!/usr/bin/env python3
"""
Image audit for cynthiastayscurated-rebuild.

Checks every HTML file for:
  - alt attribute present and non-empty
  - generic/low-quality alt text
  - loading="lazy" on below-the-fold images
  - src file actually exists on disk
  - generic/untouched filenames (IMG_1234.jpg, screenshot.png, etc.)

Usage: python3 tools/audit-images.py
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

SITE_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', 'node_modules', 'tests', 'tools', '.tmp', '.claude'}

IMG_RE = re.compile(r'<img\b([^>]*)>', re.IGNORECASE | re.DOTALL)
GENERIC_ALT = re.compile(r'^(image|photo|picture|img|screenshot|icon|banner|\d+|img_\d+)\.*$', re.I)
GENERIC_FILENAME = re.compile(r'^(img_\d+|image\d*|photo\d*|screenshot[-_\s]?\d*|untitled|dsc\d+|image[-\s]copy\d*)\.(jpg|jpeg|png|gif|webp|svg)$', re.I)

def parse_attrs(inner):
    attrs = {}
    for m in re.finditer(r'(\w[\w-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', inner):
        attrs[m.group(1).lower()] = m.group(2) if m.group(2) is not None else m.group(3)
    return attrs

def resolve_src(src, html_dir):
    if not src or src.startswith(('http://', 'https://', '//', 'data:')):
        return None
    src = src.split('?')[0].split('#')[0]
    if src.startswith('/'):
        return SITE_DIR / src.lstrip('/')
    return (html_dir / src).resolve()

def main():
    findings = []
    total_imgs = 0
    files_scanned = 0
    stats = {k: 0 for k in ['missing_alt', 'generic_alt', 'generic_filename',
                              'broken_src', 'missing_loading']}

    for root, dirs, files in os.walk(SITE_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if not fn.endswith('.html'):
                continue
            fp = Path(root) / fn
            rel = str(fp.relative_to(SITE_DIR))
            files_scanned += 1
            content = fp.read_text(encoding='utf-8', errors='ignore')
            # strip script/style to avoid false matches
            content_scan = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', content, flags=re.I)
            content_scan = re.sub(r'<style\b[^>]*>[\s\S]*?</style>', '', content_scan, flags=re.I)

            for img_idx, m in enumerate(IMG_RE.finditer(content_scan), 1):
                total_imgs += 1
                attrs = parse_attrs(m.group(1))
                src = attrs.get('src', '')
                alt = attrs.get('alt')
                loading = attrs.get('loading', '').lower()
                issues = []

                if alt is None:
                    issues.append('MISSING_ALT'); stats['missing_alt'] += 1
                elif alt.strip() and GENERIC_ALT.match(alt.strip()):
                    issues.append(f'GENERIC_ALT: "{alt[:50]}"'); stats['generic_alt'] += 1

                if img_idx > 2 and loading not in ('lazy', 'eager'):
                    issues.append('MISSING_LOADING_LAZY'); stats['missing_loading'] += 1

                if src:
                    resolved = resolve_src(src, fp.parent)
                    if resolved and not resolved.exists():
                        issues.append(f'BROKEN_SRC: {src[:60]}'); stats['broken_src'] += 1
                    if resolved and GENERIC_FILENAME.match(resolved.name):
                        issues.append(f'GENERIC_FILENAME: {resolved.name}'); stats['generic_filename'] += 1

                if issues:
                    findings.append({'file': rel, 'img': img_idx, 'src': src[:80], 'issues': issues})

    print(f'\n=== Image Audit — {datetime.now().strftime("%Y-%m-%d")} ===')
    print(f'Files scanned:   {files_scanned}')
    print(f'Images found:    {total_imgs}')
    print(f'Images flagged:  {len(findings)}\n')
    print(f'  Missing alt:       {stats["missing_alt"]}')
    print(f'  Generic alt:       {stats["generic_alt"]}')
    print(f'  Generic filename:  {stats["generic_filename"]}')
    print(f'  Broken src:        {stats["broken_src"]}')
    print(f'  Missing lazy:      {stats["missing_loading"]}')

    if findings:
        print()
        for entry in findings:
            print(f'  {entry["file"]} img#{entry["img"]} ({entry["src"].split("/")[-1]})')
            for iss in entry['issues']:
                print(f'    - {iss}')

    tmp = SITE_DIR / '.tmp'
    tmp.mkdir(exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    lines = [f'# Image Audit — {date}', '',
             f'**Images found:** {total_imgs}', f'**Flagged:** {len(findings)}', '', '## Issues', '']
    for entry in findings:
        lines.append(f'### `{entry["file"]}` img #{entry["img"]}')
        lines.append(f'`{entry["src"]}`')
        for iss in entry['issues']: lines.append(f'- {iss}')
        lines.append('')
    (tmp / f'image-audit-{date}.md').write_text('\n'.join(lines))
    print(f'\nReport: .tmp/image-audit-{date}.md')
    return 1 if stats['broken_src'] > 0 or stats['missing_alt'] > 0 else 0

if __name__ == '__main__':
    import sys; sys.exit(main())
