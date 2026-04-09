# URIP - Unified Risk Intelligence Platform

**Enterprise Cybersecurity SaaS Template by Semantic Gravity**

---

## Overview

URIP is a production-ready web template for an enterprise-grade cybersecurity risk intelligence platform. It features a modern, responsive design with a dark sidebar navigation and light content area, inspired by industry-leading platforms like CrowdStrike and Splunk.

---

## Features

### Pages Included

1. **Login Page** (`index.html`)
   - Centered authentication card with dark navy background
   - Security-themed background image from Unsplash
   - Animated floating particles effect
   - Email + Password fields with validation
   - Security compliance badges (SOC 2, ISO 27001, GDPR)

2. **Dashboard** (`dashboard.html`)
   - KPI cards with real-time metrics
   - Risk by Domain doughnut chart (Chart.js)
   - Risk Trend line chart (6-month view)
   - Risk by Source bar chart
   - Recent Critical Alerts table
   - SLA Breach Warning banner

3. **Risk Register** (`risk-register.html`)
   - Full-width data table with 15+ sample risks
   - Advanced filtering by Severity, Source, Domain, Status, Owner
   - Real-time search functionality
   - Export to PDF/Excel buttons
   - Severity badges (Critical/High/Medium/Low)
   - Status indicators with color coding
   - Pagination controls

4. **Acceptance Workflow** (`acceptance-workflow.html`)
   - Split layout: Pending requests + Detail panel
   - AI-generated recommendations
   - Approve/Reject actions
   - Audit trail section
   - Recently accepted risks table

5. **Reports** (`reports.html`)
   - Executive Summary, CISO Report, Board Report cards
   - CERT-In Compliance tracking
   - Scheduled reports management
   - Generate and download functionality

---

## Design System

### Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Navy Primary | `#0D1B2A` | Sidebar, headers |
| Navy Dark | `#08121C` | Sidebar gradient |
| Teal Accent | `#1ABC9C` | Primary buttons, links |
| Teal Hover | `#16A085` | Button hover states |
| Red Critical | `#E74C3C` | Critical alerts, badges |
| Orange High | `#E67E22` | High severity |
| Yellow Medium | `#F1C40F` | Medium severity |
| Green Low | `#27AE60` | Low severity, success |
| White | `#FFFFFF` | Backgrounds, text |
| Light Gray | `#F0F4F8` | Page background |

### Typography

- **Font Family**: Inter (Google Fonts)
- **Weights**: 300, 400, 500, 600, 700

### Icons

- **Font Awesome 6** (CDN)
- All icons are vector-based and scalable

### Charts

- **Chart.js 4.4.1** (CDN)
- Responsive, interactive charts
- Custom tooltips and legends

---

## File Structure

```
urip-template/
├── index.html                  # Login page
├── dashboard.html              # Main dashboard
├── risk-register.html          # Risk register table
├── acceptance-workflow.html    # Risk acceptance workflow
├── reports.html                # Reports page
├── css/
│   ├── main.css               # Core styles, variables, components
│   ├── sidebar.css            # Sidebar navigation styles
│   └── dashboard.css          # Dashboard-specific styles
├── js/
│   ├── sidebar.js             # Sidebar toggle, navigation
│   ├── charts.js              # Chart.js configurations
│   └── filters.js             # Table filtering, search, pagination
└── README.md                  # This file
```

---

## Technical Specifications

### Stack

- **HTML5** - Semantic markup
- **CSS3** - Custom properties, Grid, Flexbox
- **Vanilla JavaScript** - No frameworks required
- **Chart.js** - Data visualization
- **Font Awesome 6** - Icons
- **Google Fonts (Inter)** - Typography

### Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Responsive Breakpoints

- Desktop: 1280px+
- Tablet: 768px - 1279px
- Mobile: < 768px

---

## Usage

### Local Development

1. Extract the ZIP file to your desired location
2. Open `index.html` in your browser
3. Navigate through pages using the sidebar

### Customization

#### Changing Colors

Edit CSS variables in `css/main.css`:

```css
:root {
  --navy-primary: #0D1B2A;
  --teal-accent: #1ABC9C;
  --red-critical: #E74C3C;
  /* ... */
}
```

#### Adding New Risks

Edit `js/filters.js` and modify the `riskData` array:

```javascript
const riskData = [
  {
    id: 'RISK-2024-XXX',
    finding: 'Your Finding Name',
    source: 'Tool Name',
    domain: 'Domain',
    cvss: 7.5,
    severity: 'High',
    asset: 'Asset Name',
    owner: 'Team Name',
    status: 'Open',
    sla: '2024-01-20',
    slaHours: 96
  },
  // ...
];
```

#### Modifying Charts

Edit `js/charts.js` to customize chart data and options:

```javascript
function initRiskByDomainChart() {
  // Modify data and options here
}
```

---

## Sample Data Included

### Risk Findings

- Log4j RCE Vulnerability (CVSS 10.0)
- Open S3 Bucket Exposure (CVSS 7.5)
- IDOR in User Profile API (CVSS 6.5)
- Shared Admin Password (CVSS 9.8)
- OT Protocol Vulnerability (CVSS 8.2)
- Shadow IT Application (CVSS 5.3)
- Phishing Campaign (CVSS 7.8)
- And more...

### Security Tools Referenced

- CrowdStrike Falcon
- Armis
- Zscaler CASB
- CyberArk
- Forescout
- Spotlight
- EASM
- CNAPP
- VAPT
- Threat Intel
- CERT-In
- Bug Bounty
- SoC

### Teams

- Infra Team
- App Team
- Cloud Team
- OT Team
- IAM Team
- Network Team

---

## Images

All images are sourced from Unsplash with direct URLs:

- Login background: Dark server room with blue lighting
- No local image files required

---

## License

This template is provided as-is for demonstration and development purposes.

---

## Version

**URIP v2.4.1** | Build 2024.01

---

## Credits

- **Design & Development**: Semantic Gravity
- **Icons**: Font Awesome
- **Charts**: Chart.js
- **Fonts**: Google Fonts (Inter)
- **Images**: Unsplash

---

## Support

For questions or customization requests, contact your Semantic Gravity representative.
