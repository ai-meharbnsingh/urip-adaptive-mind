/**
 * URIP — Connector Schemas (FV-1)
 *
 * Shared registry consumed by:
 *   - tool-catalog.js   (renders the 12-tile grid)
 *   - connector-wizard.js (renders the per-tool credential form)
 *   - connector-status.js (renders per-connector health detail)
 *
 * Each entry defines:
 *   key            (slug used in ?tool=…)
 *   name           (display label)
 *   category       (VM / EDR / Network / Identity / Collab / ITSM / UEM / MDM / DAST / DLP / External Threat)
 *   description    (one-line catalog blurb)
 *   logoLetter     (single letter shown inside the colored circle placeholder)
 *   logoColor      (background color of the placeholder)
 *   docsUrl        (link to vendor API docs — opens in new tab)
 *   sourceType     (matches backend ConnectorConfig.source_type, used for matching status)
 *   poll           (human-readable cadence for the status pill)
 *   fields         (ordered array of field defs — see FIELD_SHAPE below)
 *
 * FIELD_SHAPE
 * -----------
 *   {
 *     name:        'access_key',                  // POST body key
 *     label:       'Access Key',                  // displayed label
 *     type:        'text' | 'url' | 'password' | 'number' | 'select' | 'uuid',
 *     required:    true | false,
 *     secret:      true | false,                  // password style with show/hide toggle
 *     help:        'Tenable.io API key prefix',   // small text under input
 *     placeholder: 'e.g. abcd1234…',
 *     default:     1000,                          // optional pre-fill
 *     pattern:     /^https?:\/\//                 // optional regex
 *     options:     [{value:'us', label:'US'}]     // for select
 *     min:         1,                             // for number
 *     max:         86400                          // for number
 *   }
 */
(function () {
  'use strict';

  var URIP = window.URIP || {};

  // Simple validators reused across fields.
  var URL_RX  = /^https?:\/\/[^\s/$.?#].[^\s]*$/i;
  var UUID_RX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  // Color palette for tile placeholders — chosen for high contrast vs white text.
  var C = {
    teal:    '#1ABC9C',
    indigo:  '#6366F1',
    sky:     '#0EA5E9',
    amber:   '#D97706',
    rose:    '#E11D48',
    violet:  '#7C3AED',
    slate:   '#475569',
    emerald: '#059669',
    crimson: '#B91C1C',
    cobalt:  '#1D4ED8'
  };

  /**
   * Tool registry — 12 tools per VISION_DOC_FINAL Section 1 + MASTER_BLUEPRINT Section 2.
   * SharePoint / OneDrive / Teams collapsed into ONE tile (per spec) since they share MS Graph auth.
   */
  var TOOLS = [
    {
      key: 'tenable',
      name: 'Tenable Vulnerability Manager',
      category: 'VM',
      description: 'Pulls CVE inventory, CVSS, EPSS, exploit availability for every scanned asset.',
      logoLetter: 'T',
      logoColor: C.cobalt,
      docsUrl: 'https://developer.tenable.com/reference/navigate',
      sourceType: 'tenable',
      poll: '15 min',
      fields: [
        { name: 'base_url', label: 'API Endpoint', type: 'url', required: true,
          default: 'https://cloud.tenable.com',
          help: 'Tenable.io cloud URL — keep default unless on a regional pod.',
          placeholder: 'https://cloud.tenable.com', pattern: URL_RX },
        { name: 'access_key', label: 'Access Key', type: 'password', required: true, secret: true,
          help: 'Settings → My Account → API Keys → Access Key.',
          placeholder: 'abcd1234efgh5678…' },
        { name: 'secret_key', label: 'Secret Key', type: 'password', required: true, secret: true,
          help: 'Settings → My Account → API Keys → Secret Key.',
          placeholder: 'wxyz9876mnop5432…' },
        { name: 'max_requests_per_hour', label: 'Max requests / hour', type: 'number',
          required: false, default: 1000, min: 1, max: 100000,
          help: 'Tenable global rate-limit ceiling — leave default unless you have a high-volume tenant.' }
      ]
    },
    {
      key: 'sentinelone',
      name: 'SentinelOne Singularity',
      category: 'EDR',
      description: 'Endpoint telemetry, threat detections, agent health, IoC matches.',
      logoLetter: 'S',
      logoColor: C.violet,
      docsUrl: 'https://usea1-partners.sentinelone.net/api-doc/overview',
      sourceType: 'sentinelone',
      poll: '15 min',
      fields: [
        { name: 'base_url', label: 'Console URL', type: 'url', required: true,
          help: 'Your SentinelOne console root, e.g. https://usea1-partners.sentinelone.net.',
          placeholder: 'https://usea1-xxxx.sentinelone.net', pattern: URL_RX },
        { name: 'api_token', label: 'API Token', type: 'password', required: true, secret: true,
          help: 'Settings → Users → Service Users → generate API token (read-only is enough).',
          placeholder: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…' },
        { name: 'max_requests_per_minute', label: 'Max requests / min', type: 'number',
          required: false, default: 200, min: 1, max: 600,
          help: 'SentinelOne enforces 200 req/min per token by default.' }
      ]
    },
    {
      key: 'zscaler',
      name: 'Zscaler ZIA / ZTA / CASB',
      category: 'Network',
      description: 'Blocked URLs, shadow SaaS detections, malicious downloads from the secure web gateway.',
      logoLetter: 'Z',
      logoColor: C.sky,
      docsUrl: 'https://help.zscaler.com/zia/api',
      sourceType: 'zscaler',
      poll: '15 min',
      fields: [
        { name: 'cloud', label: 'Zscaler Cloud', type: 'select', required: true,
          help: 'Select the Zscaler cloud you log into (visible in your admin URL).',
          options: [
            { value: 'zscaler.net',      label: 'zscaler.net' },
            { value: 'zscalerone.net',   label: 'zscalerone.net' },
            { value: 'zscalertwo.net',   label: 'zscalertwo.net' },
            { value: 'zscalerthree.net', label: 'zscalerthree.net' },
            { value: 'zscalerbeta.net',  label: 'zscalerbeta.net' },
            { value: 'zscalergov.net',   label: 'zscalergov.net' }
          ]},
        { name: 'username', label: 'Admin Username', type: 'text', required: true,
          help: 'API-enabled admin account (NOT your SSO email).',
          placeholder: 'api-admin@acme.com' },
        { name: 'password', label: 'Admin Password', type: 'password', required: true, secret: true,
          help: 'Password for the API admin account above.',
          placeholder: '••••••••' },
        { name: 'api_key', label: 'API Key', type: 'password', required: true, secret: true,
          help: 'Administration → API Key Management → copy the obfuscated key.',
          placeholder: '8a3c…' }
      ]
    },
    {
      key: 'netskope',
      name: 'Netskope',
      category: 'Network',
      description: 'Cloud app risk scores, DLP violations, sanctioned-vs-unsanctioned SaaS usage.',
      logoLetter: 'N',
      logoColor: C.indigo,
      docsUrl: 'https://docs.netskope.com/en/rest-api-v2-overview/',
      sourceType: 'netskope',
      poll: '60 min',
      fields: [
        { name: 'tenant_url', label: 'Tenant URL', type: 'url', required: true,
          help: 'Your Netskope tenant URL, e.g. https://yourorg.goskope.com.',
          placeholder: 'https://acme.goskope.com', pattern: URL_RX },
        { name: 'api_token', label: 'REST API v2 Token', type: 'password', required: true, secret: true,
          help: 'Settings → Tools → REST API v2 → generate token with read-only scopes.',
          placeholder: 'eyJ…' },
        { name: 'sync_interval_minutes', label: 'Sync interval (min)', type: 'number',
          required: false, default: 60, min: 5, max: 1440,
          help: 'How often to pull events. 60 min is a safe default.' }
      ]
    },
    {
      key: 'msentra',
      name: 'Microsoft Entra ID',
      category: 'Identity',
      description: 'Risky sign-ins, MFA bypass attempts, conditional-access violations, privileged role assignments.',
      logoLetter: 'M',
      logoColor: C.cobalt,
      docsUrl: 'https://learn.microsoft.com/en-us/graph/api/overview',
      sourceType: 'msentra',
      poll: '60 min',
      fields: [
        { name: 'tenant_id', label: 'Tenant ID', type: 'uuid', required: true,
          help: 'Azure portal → Microsoft Entra ID → Overview → Tenant ID.',
          placeholder: '00000000-0000-0000-0000-000000000000' },
        { name: 'client_id', label: 'Client ID (App registration)', type: 'uuid', required: true,
          help: 'App Registration → Overview → Application (client) ID.',
          placeholder: '00000000-0000-0000-0000-000000000000' },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true, secret: true,
          help: 'App Registration → Certificates & secrets → New client secret. Required scopes: SecurityEvents.Read.All, IdentityRiskEvent.Read.All, AuditLog.Read.All.',
          placeholder: '~m8Q…' }
      ]
    },
    {
      key: 'm365collab',
      name: 'SharePoint / OneDrive / Teams',
      category: 'Collab',
      description: 'Anonymous link sharing, external sharing audit, sensitive label violations across M365.',
      logoLetter: 'O',
      logoColor: C.emerald,
      docsUrl: 'https://learn.microsoft.com/en-us/graph/api/overview',
      sourceType: 'm365collab',
      poll: '60 min',
      fields: [
        { name: 'tenant_id', label: 'Tenant ID', type: 'uuid', required: true,
          help: 'Same Entra tenant ID as above. We re-use the Entra app-registration where possible.',
          placeholder: '00000000-0000-0000-0000-000000000000' },
        { name: 'client_id', label: 'Client ID', type: 'uuid', required: true,
          help: 'App Registration with Files.Read.All, Sites.Read.All, AuditLog.Read.All scopes.',
          placeholder: '00000000-0000-0000-0000-000000000000' },
        { name: 'client_secret', label: 'Client Secret', type: 'password', required: true, secret: true,
          help: 'App Registration → Certificates & secrets.',
          placeholder: '~m8Q…' }
      ]
    },
    {
      key: 'me_sdp',
      name: 'ManageEngine ServiceDesk Plus',
      category: 'ITSM',
      description: 'Bidirectional ticket creation + status sync — auto-creates remediation tickets.',
      logoLetter: 'S',
      logoColor: C.amber,
      docsUrl: 'https://www.manageengine.com/products/service-desk/sdpod-v3-api/',
      sourceType: 'me_sdp',
      poll: '60 min',
      fields: [
        { name: 'base_url', label: 'SDP Base URL', type: 'url', required: true,
          help: 'Your SDP cloud or on-prem URL.',
          placeholder: 'https://sdpondemand.manageengine.com', pattern: URL_RX },
        { name: 'auth_token', label: 'Authtoken (technician key)', type: 'password', required: true, secret: true,
          help: 'Personalize → API → generate technician key with full read/write to Requests.',
          placeholder: '5C9F…' }
      ]
    },
    {
      key: 'servicenow',
      name: 'ServiceNow',
      category: 'ITSM',
      description: 'Bidirectional sync — push URIP risks as ServiceNow incidents and ingest security incidents back as risks.',
      logoLetter: 'S',
      logoColor: C.emerald,
      logoUrl: 'https://www.vectorlogo.zone/logos/servicenow/servicenow-icon.svg',
      docsUrl: 'https://developer.servicenow.com/dev.do#!/reference/api/utah/rest/c_TableAPI',
      sourceType: 'servicenow',
      poll: '15 min',
      fields: [
        { name: 'instance_url', label: 'Instance URL', type: 'url', required: true,
          help: 'Full URL of your ServiceNow tenant — e.g. https://your-tenant.service-now.com.',
          placeholder: 'https://your-tenant.service-now.com', pattern: URL_RX },
        { name: 'auth_method', label: 'Auth Method', type: 'select', required: true,
          help: 'Choose Basic Auth (username + password) or OAuth Bearer Token.',
          options: [
            { value: 'basic', label: 'Username + Password' },
            { value: 'oauth', label: 'OAuth Bearer Token' }
          ]},
        { name: 'username', label: 'Username', type: 'text', required: false,
          help: 'Required when Auth Method = Username + Password. Use a dedicated integration user.',
          placeholder: 'urip_integration' },
        { name: 'password', label: 'Password', type: 'password', required: false, secret: true,
          help: 'Required when Auth Method = Username + Password.',
          placeholder: '••••••••' },
        { name: 'oauth_token', label: 'OAuth Bearer Token', type: 'password', required: false, secret: true,
          help: 'Required when Auth Method = OAuth Bearer Token.',
          placeholder: 'eyJ…' },
        { name: 'risk_query', label: 'Risk Query', type: 'text', required: true,
          help: 'ServiceNow encoded query selecting which incidents to ingest. State 7 = Closed.',
          placeholder: 'category=security^state!=7',
          default: 'category=security^active=true' }
      ]
    },
    {
      key: 'me_endpoint_central',
      name: 'ManageEngine Endpoint Central',
      category: 'UEM',
      description: 'Patch status, missing critical patches, software inventory across managed endpoints.',
      logoLetter: 'E',
      logoColor: C.amber,
      docsUrl: 'https://www.manageengine.com/products/desktop-central/api/',
      sourceType: 'me_endpoint_central',
      poll: '60 min',
      fields: [
        { name: 'base_url', label: 'Endpoint Central URL', type: 'url', required: true,
          placeholder: 'https://endpointcentral.acme.com:8383', pattern: URL_RX,
          help: 'Server URL including port (default 8383 / 8443).' },
        { name: 'auth_token', label: 'API Auth Token', type: 'password', required: true, secret: true,
          placeholder: '24F1…',
          help: 'Admin → API → Generate Token with at least the Patch Manager read role.' }
      ]
    },
    {
      key: 'me_mdm',
      name: 'ManageEngine MDM',
      category: 'MDM',
      description: 'Jailbroken devices, non-compliant mobile, lost / stolen events.',
      logoLetter: 'M',
      logoColor: C.amber,
      docsUrl: 'https://www.manageengine.com/mobile-device-management/api/',
      sourceType: 'me_mdm',
      poll: '4 h',
      fields: [
        { name: 'base_url', label: 'MDM URL', type: 'url', required: true,
          placeholder: 'https://mdm.manageengine.com', pattern: URL_RX,
          help: 'Cloud or on-prem MDM URL.' },
        { name: 'auth_token', label: 'API Auth Token', type: 'password', required: true, secret: true,
          placeholder: '7BD3…',
          help: 'Generate from Admin → API → MDM → Authtoken.' }
      ]
    },
    {
      key: 'burpsuite',
      name: 'Burp Suite Enterprise',
      category: 'DAST',
      description: 'Web app scan findings — XSS, SQLi, CSRF, broken auth across registered targets.',
      logoLetter: 'B',
      logoColor: C.rose,
      docsUrl: 'https://portswigger.net/burp/documentation/enterprise/api',
      sourceType: 'burpsuite',
      poll: '4 h',
      fields: [
        { name: 'base_url', label: 'Burp Enterprise URL', type: 'url', required: true,
          placeholder: 'https://burp-enterprise.acme.com', pattern: URL_RX,
          help: 'Requires Burp Suite Enterprise — Pro is NOT supported (no API).' },
        { name: 'api_key', label: 'GraphQL API Key', type: 'password', required: true, secret: true,
          placeholder: 'bse_…',
          help: 'Settings → API → Generate key with read access to scans + sites.' }
      ]
    },
    {
      key: 'gtb_endpoint_protector',
      name: 'GTB Endpoint Protector',
      category: 'DLP',
      description: 'DLP policy violations, USB block events, exfiltration attempts on managed endpoints.',
      logoLetter: 'G',
      logoColor: C.crimson,
      docsUrl: 'https://www.endpointprotector.com/support/online-help/api/',
      sourceType: 'gtb_endpoint_protector',
      poll: '60 min',
      fields: [
        { name: 'base_url', label: 'EPP Server URL', type: 'url', required: true,
          placeholder: 'https://epp.acme.com', pattern: URL_RX,
          help: 'EPP server URL (cloud or on-prem).' },
        { name: 'api_key', label: 'API Key', type: 'password', required: true, secret: true,
          placeholder: 'epp_…',
          help: 'System → API → generate key with DLP + Device Control read scopes.' }
      ]
    },
    {
      key: 'cloudsek',
      name: 'CloudSEK',
      category: 'External Threat',
      description: 'Dark-web alerts, brand abuse, leaked credentials, supply-chain risk (XVigil + BeVigil + SVigil).',
      logoLetter: 'C',
      logoColor: C.slate,
      docsUrl: 'https://docs.cloudsek.com/',
      sourceType: 'cloudsek',
      poll: '4 h',
      fields: [
        { name: 'api_key', label: 'CloudSEK API Key', type: 'password', required: true, secret: true,
          placeholder: 'csek_…',
          help: 'Account → API → generate key with XVigil + BeVigil + SVigil read scopes.' },
        { name: 'organization_id', label: 'Organization ID', type: 'text', required: true,
          placeholder: 'org_abcd1234',
          help: 'CloudSEK organization ID (visible in URL when logged into the dashboard).' }
      ]
    },
    {
      key: 'jira',
      name: 'Jira',
      category: 'ITSM',
      description: 'Bidirectional sync — push URIP risks as Jira issues, ingest security tickets back as risk records.',
      logoLetter: 'J',
      logoColor: C.cobalt,
      logoUrl: 'https://wac-cdn.atlassian.com/dam/jcr:e7e22f25-bb2a-4d22-b9a9-bd38c1b86b48/Jira-Logo.png',
      docsUrl: 'https://developer.atlassian.com/cloud/jira/platform/rest/v3/',
      sourceType: 'jira',
      poll: '15 min',
      fields: [
        { name: 'base_url', label: 'Jira Base URL', type: 'url', required: true,
          placeholder: 'https://your-org.atlassian.net', pattern: URL_RX,
          help: 'Cloud: https://your-org.atlassian.net. DC/Server: your internal Jira URL.' },
        { name: 'auth_method', label: 'Auth Method', type: 'select', required: true,
          help: 'Email + API Token for Jira Cloud; Personal Access Token for DC/Server.',
          options: [
            { value: 'basic',  label: 'Email + API Token (Cloud)' },
            { value: 'bearer', label: 'Personal Access Token (DC/Server)' }
          ]},
        { name: 'email', label: 'Email', type: 'text', required: false,
          placeholder: 'you@your-org.com',
          help: 'Required for Cloud (basic auth). Atlassian account email.' },
        { name: 'api_token', label: 'API Token', type: 'password', required: false, secret: true,
          placeholder: 'ATATT3xFfGF0…',
          help: 'Required for Cloud. Generate at id.atlassian.com → Security → API tokens.' },
        { name: 'bearer_token', label: 'Personal Access Token', type: 'password', required: false, secret: true,
          placeholder: 'NjI2NzYwMzU5NDU4Oj…',
          help: 'Required for DC/Server. Profile → Personal Access Tokens.' },
        { name: 'default_project_key', label: 'Default Project Key', type: 'text', required: true,
          placeholder: 'SEC',
          help: 'Project where URIP-pushed risks will land (e.g. SEC, OPS, CSEC).' },
        { name: 'risk_jql', label: 'JQL Filter (security tickets to ingest)', type: 'text', required: true,
          placeholder: 'project = SEC AND labels = "security"',
          help: 'JQL expression selecting security tickets for URIP to ingest.' }
      ]
    }
  ];

  // Build category list once for filter dropdowns.
  var CATEGORIES = (function () {
    var seen = {};
    var out = [];
    TOOLS.forEach(function (t) {
      if (!seen[t.category]) { seen[t.category] = true; out.push(t.category); }
    });
    return out.sort();
  })();

  /**
   * Look up a tool by its key (case-sensitive).
   * @param {string} key
   * @returns {object|null}
   */
  function getTool(key) {
    if (!key) return null;
    for (var i = 0; i < TOOLS.length; i++) {
      if (TOOLS[i].key === key) return TOOLS[i];
    }
    return null;
  }

  /**
   * Validate a single field value. Returns null when valid, else an error string.
   *
   * @param {object} field
   * @param {string|number} value
   * @returns {string|null}
   */
  function validateField(field, value) {
    var v = (value === null || value === undefined) ? '' : String(value).trim();

    if (!v) {
      return field.required ? 'Required' : null;
    }

    if (field.type === 'url') {
      if (!URL_RX.test(v)) return 'Must be a valid URL (https://…)';
    }

    if (field.type === 'uuid') {
      if (!UUID_RX.test(v)) return 'Must be a valid UUID (e.g. 00000000-0000-0000-0000-000000000000)';
    }

    if (field.type === 'number') {
      var n = Number(v);
      if (!Number.isFinite(n) || n <= 0 || Math.floor(n) !== n) {
        return 'Must be a positive integer';
      }
      if (typeof field.min === 'number' && n < field.min) return 'Must be ≥ ' + field.min;
      if (typeof field.max === 'number' && n > field.max) return 'Must be ≤ ' + field.max;
    }

    if (field.pattern && !field.pattern.test(v)) {
      return 'Invalid format';
    }

    return null;
  }

  // Public API
  URIP.connectorSchemas = {
    TOOLS:      TOOLS,
    CATEGORIES: CATEGORIES,
    getTool:    getTool,
    validateField: validateField
  };
  window.URIP = URIP;
})();
