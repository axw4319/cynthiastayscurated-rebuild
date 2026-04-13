#!/usr/bin/env python3
"""
Scan all HTML files for internal <a href> links and verify each target
exists on disk. Reports dead links so each one can be fixed.

Usage: python3 tools/find-dead-links.py
"""
import os
import re
import sys
import json
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', 'node_modules', 'tests', 'tools', '.tmp', '.claude'}

# Only check anchor tags — skip <link rel="canonical">, og:url meta, schema, etc.
href_re = re.compile(r'<a\b[^>]*\bhref="([^"]+)"', re.IGNORECASE)

def resolve_internal(href):
    href = href.strip()
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
        return None
    if href.startswith(('http://', 'https://')):
        if 'cynthiastayscurated.com' not in href:
            return None
        href = re.sub(r'^https?://[^/]+', '', href)
    href = href.split('#')[0].split('?')[0]
    if not href or not href.startswith('/'):
        # Relative link — treat as relative to site root for simplicity
        return '/' + href if href else None
    return href

def target_exists(path_str):
    if path_str == '/':
        return (SITE_DIR / 'index.html').exists()
    p = path_str.lstrip('/')
    full = SITE_DIR / p
    if full.is_file():
        return True
    if (SITE_DIR / p / 'index.html').exists():
        return True
    if not p.endswith('/') and (SITE_DIR / (p + '.html')).exists():
        return True
    return False

def main():
    findings = {}  # dead_path -> list of (file, line_num, href)
    files_scanned = 0
    links_checked = 0
    existence_cache = {}

    for root, dirs, files in os.walk(SITE_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith('.html'):
                continue
            fp = Path(root) / fn
            rel = str(fp.relative_to(SITE_DIR))
            files_scanned += 1
            try:
                with open(fp, encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        for m in href_re.finditer(line):
                            href = m.group(1)
                            target = resolve_internal(href)
                            if target is None:
                                continue
                            links_checked += 1
                            if target not in existence_cache:
                                existence_cache[target] = target_exists(target)
                            if not existence_cache[target]:
                                findings.setdefault(target, []).append((rel, line_num, href))
            except Exception as e:
                print(f'ERR reading {fp}: {e}')

    print(f'Scanned:        {files_scanned} HTML files')
    print(f'Links checked:  {links_checked}')
    print(f'Dead targets:   {len(findings)}')
    print(f'Dead instances: {sum(len(v) for v in findings.values())}')

    if not findings:
        print('\nNo dead internal links. Clean.')
        return 0

    print()
    sorted_findings = sorted(findings.items(), key=lambda kv: -len(kv[1]))
    for target, refs in sorted_findings:
        print(f'  {len(refs):3d}x  {target}')
        for f, ln, _ in refs[:3]:
            print(f'         {f}:{ln}')
        if len(refs) > 3:
            print(f'         ... +{len(refs) - 3} more')

    # Write JSON for programmatic use
    tmp = SITE_DIR / '.tmp'
    tmp.mkdir(exist_ok=True)
    out = {target: [{'file': f, 'line': ln, 'href': h} for f, ln, h in refs]
           for target, refs in sorted_findings}
    (tmp / 'dead-links.json').write_text(json.dumps(out, indent=2))
    print(f'\nFull report: .tmp/dead-links.json')
    return 1

if __name__ == '__main__':
    sys.exit(main())
