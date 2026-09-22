# Product Requirements Document (PRD)

**Product:** LPSE Tender Monitoring App
**Document Version:** 1.0
**Product Status:** Feature-complete local version
**Primary Deployment:** Local Windows environment
**Future Deployment:** Streamlit online deployment
**Target Users:** Admin Sales / Administrative Staff

---

# 1. Product Overview

The LPSE Tender Monitoring App is an administrative monitoring tool designed to simplify the process of checking Indonesian government procurement/tender information from LPSE/SPSE websites.

The application retrieves procurement package information, identifies packages relevant to road and infrastructure work using configurable keywords, stores historical data locally, detects new or updated packages, and presents the results through a simple administrative dashboard.

The application is designed primarily for internal administrative use.

The current version operates locally.

Online deployment is considered a future enhancement rather than a requirement for the current version.

---

# 2. Product Objective

The primary objective is to reduce repetitive manual work when monitoring LPSE procurement information.

The application should allow an administrator to:

1. Select one or more LPSE regions.
2. Retrieve current tender/package information.
3. Filter packages using configurable keywords.
4. Compare current results against previously collected data.
5. Identify newly discovered packages.
6. Identify packages whose information has changed.
7. Review historical monitoring activity.
8. Maintain data locally.
9. Update an existing Excel reporting file.
10. Keep an audit/log history of important application activities.

---

# 3. Target Users

Primary users:

* Admin Sales
* Sales Administration
* Administrative staff
* Other internal staff who monitor procurement opportunities

The target users are generally not programmers.

Therefore:

* The interface should use simple Indonesian terminology.
* Important information should be immediately visible.
* Technical errors should be hidden by default.
* Configuration should be understandable without editing source code.
* The application should minimize unnecessary steps.

---

# 4. Problem Statement

LPSE procurement information currently requires repeated manual checking.

This creates several issues:

* Repetitive administrative work.
* New packages may be overlooked.
* It is difficult to determine whether a package has already been recorded.
* Searching for road-related procurement packages takes time.
* Information must eventually be transferred into Excel.
* Changes to previously discovered packages may not be noticed.
* There is limited historical visibility regarding when information was discovered or updated.

The application addresses these problems through automated retrieval, filtering, comparison, and logging.

---

# 5. Primary User Workflow

The normal workflow is:

```text
Open Application
       ↓
Select / Review LPSE Regions
       ↓
Click "Cek Tender"
       ↓
Retrieve LPSE Data
       ↓
Filter Relevant Packages
       ↓
Compare Against Historical Data
       ↓
┌───────────────────────────────┐
│                               │
│ NEW        EXISTING    UPDATED│
│                               │
└───────────────────────────────┘
       ↓
Review Results
       ↓
Update Excel if Required
       ↓
Activity Recorded in Logs
```

The application is initially intended to be used approximately twice per day:

* Morning
* Night

Automatic scheduled checking is a future feature.

---

# 6. LPSE Region Management

The application must support multiple LPSE regions.

The LPSE region identifier must not be hardcoded.

Example:

```text
Region:
Kota Singkawang

Identifier:
singkawangkota

URL:
https://spse.inaproc.id/singkawangkota/lelang
```

Another region can be configured without modifying source code.

Users should be able to:

* Add region
* Edit region
* Delete region
* Activate/deactivate region
* Check individual regions
* Check multiple active regions

---

# 7. LPSE Scraping

The scraper is a core component of the application.

The application retrieves data from:

```text
https://spse.inaproc.id/{region_identifier}/lelang
```

The scraper should use the most reliable available retrieval method.

Preferred approach:

1. Public/API endpoint if reliably available.
2. Direct HTTP requests and HTML parsing.
3. Browser automation only when necessary.

The scraper must be implemented separately from the UI.

The application should not assume that all LPSE pages will have identical structures without validation.

---

# 8. Package Data

The application should retrieve the relevant package information available from the LPSE source.

Required core fields:

* Package ID
* Nama Paket
* LPSE Region
* Tender Status
* Pagu Anggaran
* HPS, when available
* Relevant date information
* Package URL
* First discovered timestamp
* Last checked timestamp
* Last updated timestamp

**Procurement Method is not required and should not be part of the core application data requirement.**

Additional useful fields may be added if they are reliably available from the source.

---

# 9. Relevant Package Detection

The primary monitoring objective is to identify road-related procurement packages.

Initial keywords include:

* jalan
* Jl.
* Jl
* jalan raya
* peningkatan jalan
* pembangunan jalan
* rehabilitasi jalan
* preservasi jalan
* pemeliharaan jalan
* rekonstruksi jalan
* ruas jalan

Keyword matching should:

* Be case-insensitive.
* Support partial matches.
* Be configurable.
* Allow keywords to be added or removed without modifying application source code.

Future keyword categories may include:

### Road

* jalan
* ruas jalan
* rekonstruksi
* preservasi

### Asphalt / Pavement

* hotmix
* AC-WC
* AC-BC
* lapis aspal
* perkerasan

### Bridge

* jembatan
* duiker

### Drainage

* drainase
* saluran

These additional categories are suggestions for future expansion and do not necessarily need to be enabled by default.

---

# 10. Package Status Detection

The application must classify packages into:

### NEW

The package has not previously been recorded.

### EXISTING

The package has already been recorded and no relevant tracked information has changed.

### UPDATED

The package already exists in the database but one or more tracked fields have changed.

The primary package identity should be:

```text
Package ID
```

If Package ID is unavailable, a fallback identification method should be used based on normalized package information.

---

# 11. Historical Data

The application must retain historical package information.

Historical information should allow the user to determine:

* When a package was first discovered.
* When it was last checked.
* When relevant information changed.
* What information changed.
* Which LPSE region it belongs to.

Historical data should remain available across application restarts.

---

# 12. Dashboard

The dashboard should prioritize information that matters to an administrative user.

Example:

```text
LPSE MONITORING

Last Check
22 September 2026 — 08:15

Regions Checked
3

Relevant Packages
42

New Packages
3

Updated Packages
2
```

The dashboard should prominently display:

```text
3 NEW PACKAGES FOUND
```

or:

```text
NO NEW PACKAGES
```

The dashboard should also provide access to:

* New packages
* Updated packages
* Recent activity
* Last scrape
* Scrape errors

---

# 13. Tender Data Page

The application should provide a searchable and filterable package table.

Recommended columns:

* Status Data
* Nama Paket
* Wilayah
* Status Tender
* Pagu
* HPS
* Tanggal Ditemukan
* Last Updated
* URL

The table should support:

* Search
* Region filtering
* NEW filtering
* UPDATED filtering
* EXISTING filtering
* Sorting
* Opening the original LPSE package page

---

# 14. Package Detail

Selecting a package should display:

* Nama Paket
* Package ID
* LPSE Region
* Tender Status
* Pagu
* HPS
* Package URL
* First Seen
* Last Seen
* Last Updated

Where historical data exists, display relevant changes.

Example:

```text
PACKAGE HISTORY

13 Sep 2026
Package discovered

15 Sep 2026
Status changed

20 Sep 2026
HPS changed
```

---

# 15. Scrape History

The application must maintain a history of scraping activities.

Example:

```text
22 Sep 2026 — 08:15

Regions checked: 3
Packages retrieved: 120
Relevant packages: 42
New packages: 3
Updated packages: 2

Status:
Completed
```

The history should allow the user to determine:

* When a check occurred.
* Which regions were checked.
* How many packages were retrieved.
* How many were relevant.
* How many were new.
* How many were updated.
* Whether errors occurred.

---

# 16. Application Activity Logs

The application should maintain logs for important application events.

Examples:

### Data update

```text
22 Sep 2026 08:15
LPSE Singkawang checked.
3 new packages detected.
```

### Configuration update

```text
22 Sep 2026 08:20
Keyword "hotmix" added.
```

### Region update

```text
22 Sep 2026 08:25
Region "Kota Pontianak" activated.
```

### Excel update

```text
22 Sep 2026 08:40
Excel file updated.
27 records replaced.
Backup created.
```

### Error

```text
22 Sep 2026 09:10
ERROR:
Failed to retrieve LPSE Singkawang.
```

Logs should record:

* Timestamp
* Event type
* Action
* Relevant object/data
* Result
* Error information where applicable

Technical details may be stored in the application log while the UI should present simplified explanations.

---

# 17. Notification History

The application should retain a record of important notifications.

Examples:

```text
NEW DATA

3 new packages detected
22 Sep 2026 — 08:15
```

```text
UPDATE

Package information changed
22 Sep 2026 — 20:10
```

```text
ERROR

LPSE Singkawang could not be checked
22 Sep 2026 — 20:12
```

This provides an audit trail even if the user does not immediately notice the notification.

---

# 18. Excel Integration

The application should work with one reusable Excel file.

Example:

```text
LPSE_Monitoring.xlsx
```

The application should eventually support:

* Importing/selecting an existing Excel file.
* Reading configured worksheets.
* Replacing application-generated data.
* Adding only newly discovered packages.
* Preserving unrelated worksheets.
* Preserving existing formatting where possible.
* Creating a backup before modification.

The Excel file should NOT need to be recreated from scratch every time.

---

# 19. Excel Update Modes

At minimum:

### Replace Application Data

Remove previously application-generated records and insert the latest relevant dataset.

### Add New Data

Keep existing records and append only newly detected packages.

The user should explicitly select the desired update mode.

---

# 20. Excel Safety

Before modifying an Excel file:

1. Verify the file exists.
2. Create a timestamped backup.
3. Open the workbook.
4. Modify only the configured application-managed area.
5. Save the updated workbook.
6. Verify that the operation succeeded.

Example backup:

```text
backups/
LPSE_Monitoring_2026-09-22_081500.xlsx
```

The application must never intentionally overwrite unrelated Excel information.

---

# 21. Local Storage

The current application must operate locally.

Recommended local storage:

```text
SQLite
```

The local database should retain:

* Regions
* Keywords
* Packages
* Package history
* Scrape history
* Activity logs
* Notification history

No cloud database is required for the current version.

---

# 22. Technology Stack

The application should use a stack that is simple enough for internal administration but capable of future online deployment.

### Core

**Python**

### Application UI

**Streamlit**

### Local Database

**SQLite**

### Scraping

**requests**

**BeautifulSoup**

**Playwright**, only when necessary

### Excel

**openpyxl**

### Styling

The application should support a dedicated CSS styling layer.

CSS should be separated from core application logic as much as practical.

The goal is to allow future UI modifications without requiring major changes to Python business logic.

---

# 23. CSS / UI Styling Requirements

The UI should not depend entirely on default Streamlit styling.

Create a dedicated styling area, for example:

```text
ui/
├── styles/
│   ├── main.css
│   ├── dashboard.css
│   ├── tables.css
│   └── components.css
│
├── components/
│   ├── cards.py
│   ├── tables.py
│   ├── badges.py
│   ├── notifications.py
│   └── navigation.py
│
└── theme.py
```

The exact implementation may differ depending on Streamlit limitations, but UI-related code should remain separated from scraping and database logic.

---

# 24. UI/UX Direction

The visual direction should be:

**Clean Internal Business Dashboard**

Prioritize:

* Information density without clutter.
* Easy scanning.
* Clear hierarchy.
* Professional appearance.
* Readable tables.
* Strong status indicators.
* Minimal unnecessary animation.
* Consistent spacing.
* Consistent typography.
* Desktop-first design.

Avoid:

* Excessive gradients.
* Excessive animations.
* Huge decorative elements.
* Unnecessary illustrations.
* Consumer/social-media style interfaces.
* Excessively rounded UI components.

---

# 25. Suggested UI References

The UI can take conceptual inspiration from:

### Streamlit native dashboard

Useful for:

* Simple navigation
* Data-focused layout
* Rapid administrative tools

### GitHub

Useful for:

* Clean information hierarchy
* Status indicators
* Activity history
* Dense but readable information

### Linear

Useful for:

* Clean spacing
* Minimal interface
* Status badges
* Clear navigation

### Notion

Useful for:

* Information organization
* Simple tables
* Configuration pages

### Google Material Design

Useful as a general reference for:

* Typography
* Spacing
* Buttons
* Forms
* Accessibility
* Interaction patterns

The application should not directly copy any of these interfaces.

They are references for design principles only.

---

# 26. UI Color Direction

The application should use a restrained professional color system.

Suggested semantic colors:

```text
Primary
Used for navigation and primary actions.

Success
Used for:
NEW / completed / successful operations

Warning
Used for:
UPDATED / attention required

Error
Used for:
Scraping failure / Excel failure

Neutral
Used for:
EXISTING / inactive / informational states
```

Colors should be configurable through the UI/theme styling layer rather than scattered throughout Python source files.

---

# 27. UI Component Structure

Reusable UI components should be created where practical.

Example:

```text
ui/components/

status_badge
metric_card
data_table
notification_card
confirmation_dialog
filter_bar
page_header
sidebar
```

This means that changing the appearance of a status badge should ideally require editing one component rather than searching through the entire application.

---

# 28. Responsive Design

The primary environment is desktop Windows.

Therefore, desktop usability is the priority.

However, the UI should avoid unnecessarily fixed dimensions so that a future online deployment can support:

* Laptop
* Desktop
* Tablet

Mobile support is not a Version 1 priority.

---

# 29. Online Deployment — Future

The current application is local-first.

Online deployment is an **after-afterthought / future phase** and should not complicate the current implementation unnecessarily.

Potential future deployment:

```text
Streamlit
     ↓
Cloud Hosting
     ↓
Online Application
```

The application architecture should nevertheless avoid making online migration impossible.

Potential future services may include:

* Streamlit Community Cloud or equivalent hosting
* Cloud database
* Cloud file storage
* Authentication
* Scheduled jobs

These are NOT current requirements.

---

# 30. Automatic Data Updating — Future

If the application is eventually deployed online, it should have the potential to automatically update LPSE data.

Possible future workflow:

```text
Scheduled Job
      ↓
LPSE Scraper
      ↓
Database
      ↓
Detect New/Updated Packages
      ↓
Notification
```

Possible schedules:

* Every morning
* Every night
* Every X hours
* User-defined schedule

The user should be able to explicitly enable or disable automatic updates.

Automatic updates must NOT be enabled by default merely because the application is deployed online.

---

# 31. Future Notification System

When deployed online, potential notification channels include:

* In-app notification
* Email
* Telegram
* WhatsApp, if a suitable integration becomes available
* Other supported messaging services

Notifications should only be introduced after the core local monitoring workflow is stable.

---

# 32. Security Considerations for Future Online Deployment

The local version does not require authentication.

If deployed online, authentication should become mandatory before exposing the application publicly.

Future deployment should consider:

* User authentication
* Access control
* Database security
* Secrets/environment variables
* HTTPS
* Rate limiting
* Scraper request limits
* Protection of uploaded Excel files

---

# 33. Version Status

The current project should be treated as being on the **latest local feature version**.

The core application functionality is considered implemented.

Current scope includes:

* LPSE scraping
* Configurable LPSE regions
* Keyword filtering
* Package storage
* New package detection
* Updated package detection
* Historical data
* Dashboard
* Tender data viewing
* Package details
* Scrape history
* Activity logs
* Notification history
* Excel integration
* Excel backup
* Local SQLite storage
* Configurable UI styling structure

The major functionality not currently implemented is:

**Online deployment.**

Future online work should therefore be treated as an additional deployment phase rather than a rewrite of the product.

---

# 34. Development Philosophy

The project should follow these principles:

### Local First

The application should work completely without cloud infrastructure.

### Data Safety

User data and Excel files must be protected from accidental modification or deletion.

### Modular

Scraping, database, business logic, Excel processing, and UI should remain separated.

### Configurable

Users should not need to edit Python source code for ordinary configuration.

### Maintainable

The code should remain understandable to future developers or AI coding agents.

### Upgradeable

Future online deployment should be possible without rebuilding the application from zero.

### Practical

Features should solve actual administrative problems rather than add complexity for its own sake.

---

# 35. Current vs Future Scope

| Feature                      | Current Local Version |        Future Online |
| ----------------------------- | ---------------------: | ---------------------: |
| LPSE Scraping                |                     ✅ |                    ✅ |
| Keyword Filtering            |                     ✅ |                    ✅ |
| Multiple Regions             |                     ✅ |                    ✅ |
| New Package Detection        |                     ✅ |                    ✅ |
| Updated Package Detection    |                     ✅ |                    ✅ |
| Historical Data              |                     ✅ |                    ✅ |
| Dashboard                    |                     ✅ |                    ✅ |
| Activity Logs                |                     ✅ |                    ✅ |
| Notification History         |                     ✅ |                    ✅ |
| Excel Integration            |                     ✅ |                    ✅ |
| Excel Backup                 |                     ✅ |                    ✅ |
| Local SQLite                 |                     ✅ | Optional replacement |
| Dedicated UI Styling         |                     ✅ |                    ✅ |
| Online Deployment            |                     — |                   🔜 |
| User Authentication          |                     — |                   🔜 |
| Automatic Scheduled Scraping |                     — |                   🔜 |
| Cloud Database               |                     — |                   🔜 |
| Email/Telegram Notifications |                     — |                   🔜 |

---

# 36. Definition of Success

The application is successful when an admin can:

1. Open the application.
2. Click "Cek Tender".
3. Retrieve current LPSE data.
4. See relevant road-related packages.
5. Immediately identify new packages.
6. Identify updated packages.
7. Review previous activity.
8. Safely update the existing Excel file.
9. Understand the result without needing programming knowledge.

The application should make the administrative monitoring process faster, more consistent, and easier to review.
