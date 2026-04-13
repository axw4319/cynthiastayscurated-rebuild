/**
 * Google Apps Script — Interior Design Consultation Form Backend
 *
 * SETUP INSTRUCTIONS:
 *
 * 1. Go to https://script.google.com and create a new project
 *    (name it "Cynthia Stays Curated — Design Consultations")
 * 2. Delete the default Code.gs contents and paste this entire file
 * 3. Click Save (floppy disk icon)
 * 4. Click Run > doPost (it will prompt for permissions — authorize with
 *    your Google account and allow access to Gmail, Drive, and Spreadsheets)
 * 5. Click Deploy > New deployment
 *    - Click the gear icon → select "Web app"
 *    - Description: "Design Consultation form endpoint v1"
 *    - Execute as: Me (your email)
 *    - Who has access: Anyone
 *    - Click Deploy
 * 6. Copy the Web App URL (starts with https://script.google.com/macros/s/...)
 * 7. Paste that URL into contact-design.html where it says
 *    DESIGN_APPS_SCRIPT_URL (currently at the top of the <script> block)
 *
 * The script will automatically create a Google Sheet named
 * "Cynthia Stays Curated — Design Consultations" in your Google Drive
 * the first time the form is submitted.
 *
 * Each submission also sends a formatted email to NOTIFY_EMAIL.
 */

// Write to the EXISTING shared spreadsheet in a "Design Consultations" tab
const SPREADSHEET_ID = '1vzUx_P4N7BijFNiTomRYjGpmuBnzFHvzXvnQYjHBlKI';
const TAB_NAME = 'Design Consultations';
const NOTIFY_EMAIL = 'cynthiastayscurated@gmail.com,aaron@procloser.ai';

function getOrCreateSheet() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  // Check if the tab already exists
  let sheet = ss.getSheetByName(TAB_NAME);
  if (sheet) return ss;

  // Create the tab and add headers
  sheet = ss.insertSheet(TAB_NAME);

  const headers = [
    'Timestamp',
    'First Name',
    'Last Name',
    'Email',
    'Phone',
    'Services',
    'Address 1',
    'Address 2',
    'City',
    'State',
    'ZIP',
    'Country',
    'Estimated Budget',
    'Projected Launch Date',
    'Links to Inspiration',
    'Additional Notes'
  ];

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold')
    .setBackground('#1c3939')
    .setFontColor('#f8f6f2');
  sheet.setFrozenRows(1);

  sheet.setColumnWidth(1, 150);
  sheet.setColumnWidth(6, 320);
  sheet.setColumnWidth(15, 280);
  sheet.setColumnWidth(16, 320);

  return ss;
}

function doPost(e) {
  try {
    const p = e.parameter;
    const ss = getOrCreateSheet();
    const sheet = ss.getSheetByName(TAB_NAME);

    // Collect which service checkboxes are Yes into a readable string
    const services = [];
    if (p.service_new_links === 'Yes') services.push('New Property Virtual Design with Links');
    if (p.service_new_ordering === 'Yes') services.push('New Property Virtual Design + Ordering');
    if (p.service_refresh_links === 'Yes') services.push('Property Refresh Virtual Design with Links');
    if (p.service_refresh_ordering === 'Yes') services.push('Property Refresh + Ordering');

    const servicesStr = services.join(', ');

    // Build the row
    const row = [
      new Date(),
      p.firstName || '',
      p.lastName || '',
      p.email || '',
      p.phone || '',
      servicesStr,
      p.address1 || '',
      p.address2 || '',
      p.city || '',
      p.state || '',
      p.zip || '',
      p.country || '',
      p.budget || '',
      p.launchDate || '',
      p.inspiration || '',
      p.notes || ''
    ];

    sheet.appendRow(row);

    // Send the email notification
    sendNotificationEmail(p, services);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function sendNotificationEmail(p, services) {
  const name = [p.firstName, p.lastName].filter(Boolean).join(' ');
  const address = [p.address1, p.address2, p.city, p.state, p.zip, p.country]
    .filter(Boolean)
    .join(', ');

  let body = '🏡 NEW DESIGN CONSULTATION REQUEST 🏡\n';
  body += '━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

  body += '👤 CLIENT INFO\n';
  body += 'Name: ' + name + '\n';
  body += 'Email: ' + (p.email || '') + '\n';
  body += 'Phone: ' + (p.phone || '') + '\n\n';

  body += '🛠️ SERVICES REQUESTED\n';
  if (services.length) {
    services.forEach(function(s) { body += '  • ' + s + '\n'; });
  } else {
    body += '  (none selected)\n';
  }
  body += '\n';

  body += '📍 PROPERTY ADDRESS\n';
  body += address || '(not provided)';
  body += '\n\n';

  body += '💰 BUDGET & TIMELINE\n';
  body += 'Estimated Budget: ' + (p.budget || 'Not specified') + '\n';
  body += 'Projected Launch Date: ' + (p.launchDate || 'Not specified') + '\n\n';

  if (p.inspiration) {
    body += '🎨 INSPIRATION LINKS\n';
    body += p.inspiration + '\n\n';
  }

  if (p.notes) {
    body += '📝 ADDITIONAL NOTES\n';
    body += p.notes + '\n\n';
  }

  body += '━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
  body += 'Submitted: ' + new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' }) + ' CT\n';

  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: '🏡 New Design Consultation — ' + name,
    body: body,
    replyTo: p.email || undefined
  });
}

// GET endpoint — useful for quick "is this deployed?" checks from a browser
function doGet() {
  return ContentService
    .createTextOutput('Cynthia Stays Curated — Design Consultation form backend is running.')
    .setMimeType(ContentService.MimeType.TEXT);
}
