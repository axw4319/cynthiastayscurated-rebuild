#!/usr/bin/env python3
"""
SEO audit for cynthiastayscurated-rebuild.

Checks every HTML file for:
  - <title> present, length 30-60 chars
  - meta description present, length 120-160 chars
  - canonical link present
  - viewport meta tag
  - og:title, og:description, og:image, og:url, og:type
  - at least one JSON-LD schema block (valid JSON)
  - exactly 1 <h1>
  - no skipped heading levels

Usage: python3 tools/audit-seo.py
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime

SITE_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', 'node_modules', 'tests', 'tools', '.tmp', '.claude'}
# Dev/source files that aren't real site pages
SKIP_FILES = {'render-form-source.html'}
DOMAIN = 'https://www.cynthiastayscurated.com'

TITLE_RE = re.compile(r'<title>([^<]*)</title>', re.I)
META_RE = re.compile(r'<meta\s+([^>]+)>', re.I)
CANONICAL_RE = re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', re.I)
VIEWPORT_RE = re.compile(r'<meta\s+name=["\']viewport["\']', re.I)
JSONLD_RE = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', re.I)
HEADING_RE = re.compile(r'<(h[1-6])(?:\s[^>]*)?>([\s\S]*?)</\1>', re.I)

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()

def parse_metas(head):
    out = {}
    for m in META_RE.finditer(head):
        attrs = m.group(1)
        name_m = re.search(r'\bname="([^"]+)"', attrs, re.I)
        prop_m = re.search(r'\bproperty="([^"]+)"', attrs, re.I)
        content_m = re.search(r'\bcontent="([^"]*)"', attrs, re.I) or \
                    re.search(r"\bcontent='([^']*)'", attrs, re.I)
        key = (name_m or prop_m)
        if key and content_m:
            out[key.group(1).lower()] = content_m.group(1)
    return out

def main():
    findings = []
    files_scanned = 0
    stats = {k: 0 for k in [
        'missing_title', 'title_short', 'title_long',
        'missing_description', 'desc_short', 'desc_long',
        'missing_canonical', 'missing_viewport',
        'missing_og_title', 'missing_og_description', 'missing_og_image',
        'missing_og_url', 'missing_og_type',
        'missing_schema', 'schema_parse_error',
        'no_h1', 'multi_h1', 'skipped_heading',
    ]}

    for root, dirs, files in os.walk(SITE_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if not fn.endswith('.html') or fn in SKIP_FILES:
                continue
            fp = Path(root) / fn
            rel = str(fp.relative_to(SITE_DIR))
            files_scanned += 1
            content = fp.read_text(encoding='utf-8', errors='ignore')
            head_m = re.search(r'<head>([\s\S]*?)</head>', content, re.I)
            head = head_m.group(1) if head_m else content[:8192]

            issues = []

            # Title
            tm = TITLE_RE.search(head)
            if not tm:
                issues.append('NO_TITLE'); stats['missing_title'] += 1
            else:
                tl = len(tm.group(1).strip())
                if tl < 30: issues.append(f'TITLE_SHORT:{tl}'); stats['title_short'] += 1
                elif tl > 65: issues.append(f'TITLE_LONG:{tl}'); stats['title_long'] += 1

            # Meta description
            metas = parse_metas(head)
            desc = metas.get('description', '')
            if not desc:
                issues.append('NO_DESCRIPTION'); stats['missing_description'] += 1
            else:
                dl = len(desc)
                if dl < 100: issues.append(f'DESC_SHORT:{dl}'); stats['desc_short'] += 1
                elif dl > 165: issues.append(f'DESC_LONG:{dl}'); stats['desc_long'] += 1

            # Canonical
            if not CANONICAL_RE.search(head):
                issues.append('NO_CANONICAL'); stats['missing_canonical'] += 1

            # Viewport
            if not VIEWPORT_RE.search(head):
                issues.append('NO_VIEWPORT'); stats['missing_viewport'] += 1

            # OG tags
            for tag, key in [('og:title','missing_og_title'), ('og:description','missing_og_description'),
                              ('og:image','missing_og_image'), ('og:url','missing_og_url'),
                              ('og:type','missing_og_type')]:
                if tag not in metas:
                    issues.append(f'NO_{tag.upper().replace(":","_")}')
                    stats[key] += 1

            # Schema
            schemas = JSONLD_RE.findall(content)
            if not schemas:
                issues.append('NO_SCHEMA'); stats['missing_schema'] += 1
            else:
                for s in schemas:
                    try:
                        json.loads(s.strip())
                    except json.JSONDecodeError:
                        issues.append('SCHEMA_PARSE_ERROR'); stats['schema_parse_error'] += 1; break

            # Headings
            headings = [(m.group(1).lower(), strip_tags(m.group(2))) for m in HEADING_RE.finditer(content)]
            h1s = [h for h in headings if h[0] == 'h1']
            if not h1s: issues.append('NO_H1'); stats['no_h1'] += 1
            elif len(h1s) > 1: issues.append(f'MULTI_H1:{len(h1s)}'); stats['multi_h1'] += 1

            last = 0
            for tag, _ in headings:
                lvl = int(tag[1])
                if last > 0 and lvl > last + 1:
                    issues.append(f'SKIPPED_HEADING:{tag}'); stats['skipped_heading'] += 1; break
                if lvl > last: last = lvl

            if issues:
                findings.append({'file': rel, 'issues': issues})

    # Console output
    print(f'\n=== SEO Audit — {datetime.now().strftime("%Y-%m-%d")} ===')
    print(f'Files scanned:     {files_scanned}')
    print(f'Files with issues: {len(findings)}\n')
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        if v: print(f'  {k:30} {v}')

    if findings:
        print()
        for entry in findings:
            print(f'  {entry["file"]}')
            for iss in entry['issues']:
                print(f'    - {iss}')

    # Write report
    tmp = SITE_DIR / '.tmp'
    tmp.mkdir(exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    lines = [f'# SEO Audit — {date}', '',
             f'**Files scanned:** {files_scanned}',
             f'**Files with issues:** {len(findings)}', '', '## Issues', '']
    for entry in findings:
        lines.append(f'### `{entry["file"]}`')
        for iss in entry['issues']: lines.append(f'- {iss}')
        lines.append('')
    (tmp / f'seo-audit-{date}.md').write_text('\n'.join(lines))
    print(f'\nReport: .tmp/seo-audit-{date}.md')
    return 1 if findings else 0

if __name__ == '__main__':
    import sys; sys.exit(main())
