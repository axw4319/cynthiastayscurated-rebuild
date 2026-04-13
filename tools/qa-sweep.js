#!/usr/bin/env node
/**
 * QA Sweep — Cynthia Stays Curated
 *
 * Loads every page at 4 viewport sizes, captures screenshots,
 * checks for common issues, and writes a markdown report.
 *
 * Usage:
 *   node tools/qa-sweep.js              # test local server (default: http://localhost:8080)
 *   node tools/qa-sweep.js --port 3000  # different port
 *   node tools/qa-sweep.js --url <url>  # specific single URL
 *
 * Output:
 *   tests/qa-report.md           — readable markdown summary
 *   tests/screenshots/<device>/  — one PNG per (page × viewport)
 */

'use strict';

const { chromium } = require('../node_modules/playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ─── Config ──────────────────────────────────────────────────────────────────

const ROOT = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT, 'tests', 'screenshots');
const REPORT_PATH = path.join(ROOT, 'tests', 'qa-report.md');

const VIEWPORTS = [
  { name: 'mobile',   width: 375,  height: 812  },
  { name: 'tablet',   width: 768,  height: 1024 },
  { name: 'desktop',  width: 1440, height: 900  },
];

// All pages to test
const PAGES = [
  { slug: 'home',          path: '/index.html' },
  { slug: 'design-form',   path: '/contact-design.html' },
  { slug: 'travel-form',   path: '/contact-travel.html' },
  { slug: 'blog',          path: '/blog.html' },
  { slug: 'blog-post',     path: '/blog-post.html' },
  { slug: 'accessibility', path: '/accessibility-statement.html' },
  { slug: 'privacy',       path: '/privacy-policy.html' },
];

// Parse args
const args = process.argv.slice(2);
const portArg = args[args.indexOf('--port') + 1];
const PORT = portArg || '8080';
const BASE_URL = `http://localhost:${PORT}`;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function screenshotPath(device, slug) {
  const dir = path.join(SCREENSHOTS_DIR, device);
  ensureDir(dir);
  return path.join(dir, `${slug}.png`);
}

// ─── Page check ──────────────────────────────────────────────────────────────

async function checkPage(browser, pageUrl, viewport, slug) {
  const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];

  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  page.on('requestfailed', req => {
    failedRequests.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
  });

  let httpStatus = null;
  try {
    const response = await page.goto(pageUrl, { waitUntil: 'networkidle', timeout: 30000 });
    httpStatus = response ? response.status() : null;
  } catch (err) {
    await context.close();
    return { error: `Navigation failed: ${err.message}`, issues: [], consoleErrors, failedRequests };
  }

  await page.waitForTimeout(600);

  const issues = [];

  // 1. HTTP error
  if (httpStatus && httpStatus >= 400) {
    issues.push(`HTTP ${httpStatus} error`);
  }

  // 2. Horizontal overflow (only flag real scrollability)
  const overflows = await page.evaluate(() => {
    const vw = window.innerWidth;
    const prevX = window.scrollX;
    window.scrollTo(vw, 0);
    const actualScrolled = window.scrollX;
    window.scrollTo(prevX, 0);
    if (actualScrolled > 2) {
      const offenders = [];
      document.querySelectorAll('*').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.right > vw + 2 && rect.width > 0) {
          let ancestor = el.parentElement;
          let inScrollContainer = false;
          while (ancestor && ancestor !== document.body) {
            const style = window.getComputedStyle(ancestor);
            if (style.overflowX === 'auto' || style.overflowX === 'scroll') {
              inScrollContainer = true;
              break;
            }
            ancestor = ancestor.parentElement;
          }
          if (!inScrollContainer) {
            const tag = el.tagName.toLowerCase();
            const cls = el.className ? `.${[...el.classList].slice(0, 2).join('.')}` : '';
            offenders.push(`${tag}${cls}`.substring(0, 60));
          }
        }
      });
      return { overflow: Math.round(actualScrolled), offenders: offenders.slice(0, 3) };
    }
    return null;
  });

  if (overflows) {
    issues.push(`Horizontal overflow: ${overflows.overflow}px`);
    if (overflows.offenders.length) {
      issues.push(`  Offenders: ${overflows.offenders.join(', ')}`);
    }
  }

  // 3. Broken images
  const brokenImages = await page.evaluate(() =>
    [...document.images]
      .filter(img => img.complete && img.naturalWidth === 0)
      .map(img => (img.getAttribute('src') || '').split('/').pop())
      .slice(0, 5)
  );
  if (brokenImages.length) {
    issues.push(`Broken images (${brokenImages.length}): ${brokenImages.join(', ')}`);
  }

  // 4. Missing page title
  const title = await page.title();
  if (!title || title.trim() === '') {
    issues.push('Missing <title>');
  }

  // 5. Missing or multiple H1
  const h1Count = await page.locator('h1').count();
  if (h1Count === 0) issues.push('Missing <h1>');
  if (h1Count > 1) issues.push(`Multiple <h1> tags (${h1Count})`);

  // 6. Console errors
  if (consoleErrors.length) {
    issues.push(`Console errors (${consoleErrors.length}): ${consoleErrors.slice(0, 2).join(' | ')}`);
  }

  // 7. Menu check — all 4 items present
  const menuItems = await page.locator('.mobile-menu-links li').allInnerTexts();
  // The Journal is hidden until real blog content is published
  const expectedItems = ['Home', 'Free Design Consultation', 'Free Travel Quote'];
  const missing = expectedItems.filter(item => !menuItems.some(m => m.trim() === item));
  if (missing.length) {
    issues.push(`Menu missing items: ${missing.join(', ')}`);
  }
  const wrongOrder = menuItems.length >= 4 &&
    menuItems.map(m => m.trim()).join('|') !== expectedItems.join('|');
  if (menuItems.length >= 4 && wrongOrder) {
    issues.push(`Menu order wrong: ${menuItems.map(m => m.trim()).join(' → ')}`);
  }

  // 8. Viewport meta tag
  const hasViewportMeta = await page.evaluate(() =>
    !!document.querySelector('meta[name="viewport"]')
  );
  if (!hasViewportMeta) {
    issues.push('Missing <meta name="viewport">');
  }

  // Screenshot (above-the-fold)
  const shotPath = screenshotPath(viewport.name, slug);
  await page.screenshot({ path: shotPath, fullPage: false });

  await context.close();
  return { issues, consoleErrors, failedRequests: failedRequests.slice(0, 3), httpStatus, title };
}

// ─── Report ──────────────────────────────────────────────────────────────────

function generateReport(results, startTime) {
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const date = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';

  const withIssues = results.filter(r => r.issues.length > 0 || r.error);
  const passed = results.filter(r => !r.error && r.issues.length === 0);

  let md = `# Cynthia Stays Curated — QA Report\n\n`;
  md += `**Date:** ${date}  \n`;
  md += `**Base URL:** ${BASE_URL}  \n`;
  md += `**Duration:** ${elapsed}s  \n\n`;

  md += `## Summary\n\n`;
  md += `| Metric | Count |\n|--------|-------|\n`;
  md += `| Pages × viewports | ${results.length} |\n`;
  md += `| Passed | ${passed.length} |\n`;
  md += `| With issues | ${withIssues.length} |\n\n`;

  if (withIssues.length > 0) {
    md += `## Issues Found\n\n`;
    for (const r of withIssues) {
      md += `### ${r.page} @ ${r.viewport}\n\n`;
      if (r.error) {
        md += `- ERROR: ${r.error}\n`;
      } else {
        for (const issue of r.issues) {
          md += `- ${issue}\n`;
        }
      }
      md += `\n![screenshot](screenshots/${r.viewport}/${r.slug}.png)\n\n`;
    }
  } else {
    md += `## All checks passed!\n\n`;
  }

  md += `## Full Results\n\n`;
  md += `| Page | ${VIEWPORTS.map(v => v.name).join(' | ')} |\n`;
  md += `|------|${VIEWPORTS.map(() => '---').join('|')}|\n`;

  const bySlug = {};
  for (const r of results) {
    if (!bySlug[r.slug]) bySlug[r.slug] = {};
    bySlug[r.slug][r.viewport] = r;
  }

  for (const [slug, byVp] of Object.entries(bySlug)) {
    const cells = VIEWPORTS.map(vp => {
      const r = byVp[vp.name];
      if (!r) return '—';
      if (r.error) return '❌ error';
      return r.issues.length === 0 ? '✅' : `⚠️ ${r.issues.length}`;
    });
    md += `| \`${slug}\` | ${cells.join(' | ')} |\n`;
  }

  md += `\n---\n*Generated by tools/qa-sweep.js*\n`;
  return md;
}

// ─── Main ────────────────────────────────────────────────────────────────────

function runPreflightChecks() {
  console.log('Pre-flight: checking dead links...');
  try {
    execSync(`python3 ${path.join(ROOT, 'tools/find-dead-links.py')}`, { stdio: 'inherit' });
    console.log('Pre-flight: dead links OK\n');
    return true;
  } catch (err) {
    console.error('\nPre-flight FAILED: dead internal links found. Fix before running Playwright.\n');
    return false;
  }
}

async function main() {
  const startTime = Date.now();
  console.log(`\nCynthia Stays Curated — QA Sweep`);
  console.log(`Base URL : ${BASE_URL}`);
  console.log(`Pages    : ${PAGES.length}`);
  console.log(`Viewports: ${VIEWPORTS.map(v => v.name).join(', ')}\n`);

  // Pre-flight dead link check — abort if broken links found
  const preflightOk = runPreflightChecks();
  if (!preflightOk) process.exit(1);

  ensureDir(SCREENSHOTS_DIR);
  VIEWPORTS.forEach(vp => ensureDir(path.join(SCREENSHOTS_DIR, vp.name)));

  const browser = await chromium.launch({ headless: true });
  const allResults = [];

  for (const pg of PAGES) {
    for (const vp of VIEWPORTS) {
      const url = BASE_URL + pg.path;
      const result = await checkPage(browser, url, vp, pg.slug);
      result.page = pg.slug;
      result.slug = pg.slug;
      result.viewport = vp.name;
      result.url = url;
      allResults.push(result);

      const status = result.error ? '❌' : result.issues.length > 0 ? '⚠️ ' : '✅';
      const issueText = result.error
        ? result.error.substring(0, 60)
        : result.issues.length > 0
        ? result.issues[0].substring(0, 55)
        : '';
      console.log(`  ${status} ${vp.name.padEnd(10)} ${pg.slug}${issueText ? '  →  ' + issueText : ''}`);
    }
  }

  await browser.close();

  const report = generateReport(allResults, startTime);
  fs.writeFileSync(REPORT_PATH, report, 'utf8');

  const withIssues = allResults.filter(r => r.issues.length > 0 || r.error);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log(`\n${'─'.repeat(55)}`);
  console.log(`Done in ${elapsed}s`);
  console.log(`Issues found : ${withIssues.length}`);
  console.log(`Report       : tests/qa-report.md`);
  console.log(`Screenshots  : tests/screenshots/\n`);

  process.exit(withIssues.length > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('\nFatal error:', err);
  process.exit(1);
});
