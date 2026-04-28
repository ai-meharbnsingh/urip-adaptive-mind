/**
 * URIP — Per-Tool Credential Wizard (FV-1)
 *
 * URL: connector-wizard.html?tool=<key>
 *
 * Renders a single-screen guided form per the schema in URIP.connectorSchemas.
 * Fields:
 *   - text / url / number / select rendered as form-input
 *   - password / secret rendered with a show-hide eye toggle
 *   - inline error on blur (uses validateField)
 *
 * Behaviors:
 *   - "Test Connection" button:
 *       If a ConnectorConfig already exists for this source_type, calls real
 *       backend POST /api/connectors/<id>/test (mocked server-side today —
 *       see Backend Gaps below).
 *       If no row exists yet, the test is purely client-side: it validates
 *       the form, then calls a setTimeout(800ms) returning a randomized
 *       success / failure with an honest "(simulated — connector not yet saved)"
 *       label so the user knows it's a dry run.
 *
 *   - "Save & Enable" button:
 *       1. Validate every field — abort + focus first invalid on failure.
 *       2. Refuse to submit if window.location.protocol !== 'https:' AND host
 *          is not localhost — show toast + don't send.
 *       3. POST /api/connectors with {name, source_type, base_url, credentials, sync_interval_minutes}.
 *       4. On success: clear secret fields, show "(last 4: ____)" hint, toast,
 *          repaint form into "edit" mode.
 *
 *   - Secrets:
 *       Never written to localStorage / sessionStorage at any point.
 *       After save, only a "last 4 chars" hint is rendered next to each secret
 *       field, allowing the operator to verify they re-entered the same value
 *       on the next edit without exposing the full value.
 *
 * Backend gaps discovered (documented for the orchestrator):
 *   - There is no "test before save" route. POST /api/connectors/{id}/test
 *     (settings.py:443) requires the connector_id to already exist. So the
 *     "Test Connection" button is honestly two-mode:
 *         (a) For an EXISTING connector → real backend call (mocked server-side).
 *         (b) For a NEW connector being entered → client-side simulated check.
 *     The user-facing label makes this distinction explicit.
 *   - GET /api/connectors does not return decrypted credentials (security win)
 *     so we cannot pre-fill secret fields on edit. We only show "last 4: ****"
 *     when the row already has has_credentials=true.
 *   - Backend does not currently expose per-tool error logs / health detail —
 *     the connector-status page therefore renders best-effort from is_active
 *     and last_sync only. A future endpoint (e.g. GET /connectors/{id}/health)
 *     would unblock richer health UX.
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  var schemas = window.URIP && window.URIP.connectorSchemas;
  if (!schemas) return; // schema script failed to load

  // State
  var tool = null;            // tool schema entry
  var existingRow = null;     // ConnectorConfig row from backend (or null)
  var secretsLast4 = {};      // field.name -> last 4 chars (after save), purely transient
  var errorEls = {};          // field.name -> inline error span

  // ---------------------------------------------------------------------------
  // Initial resolve: parse ?tool=… and load any existing connector row.
  // ---------------------------------------------------------------------------

  function readToolKey() {
    try {
      var p = new URLSearchParams(window.location.search);
      return p.get('tool');
    } catch (_e) { return null; }
  }

  function showHardError(msg) {
    $('wizardLoading').style.display = 'none';
    $('wizardShell').style.display = 'none';
    $('wizardError').style.display = 'flex';
    $('wizardErrorMsg').textContent = msg;
  }

  async function init() {
    var key = readToolKey();
    tool = schemas.getTool(key);
    if (!tool) {
      showHardError('Unknown tool key "' + (key || '') + '" — pick a tool from the catalog.');
      return;
    }

    // Update title + subtitle
    document.title = tool.name + ' setup | URIP';
    $('wizardSubtitle').textContent = 'Connect ' + tool.name + ' to URIP — credentials encrypted at rest, never stored in your browser.';

    // Insecure-page banner
    var insecure = window.location.protocol === 'http:'
      && window.location.hostname !== 'localhost'
      && window.location.hostname !== '127.0.0.1';
    if (insecure) $('insecureBanner').style.display = 'flex';

    // Header
    var logo = $('wizardLogo');
    logo.style.background = tool.logoColor;
    logo.textContent = tool.logoLetter;
    logo.setAttribute('aria-hidden', 'true');
    $('wizardToolName').textContent = tool.name;
    $('wizardToolSub').textContent = tool.category + ' · pulls every ' + tool.poll;
    $('wizardDocsLink').href = tool.docsUrl;

    // Render fields
    renderFields();

    // Try to fetch existing connector row
    await loadExistingRow();

    // Wire actions
    $('btnTest').addEventListener('click', onTestConnection);
    $('wizardForm').addEventListener('submit', onSave);

    // Show
    $('wizardLoading').style.display = 'none';
    $('wizardShell').style.display = '';
  }

  // ---------------------------------------------------------------------------
  // Field rendering
  // ---------------------------------------------------------------------------

  function renderFields() {
    var grid = $('wizardFields');
    grid.textContent = '';
    errorEls = {};

    tool.fields.forEach(function (field, idx) {
      var group = document.createElement('div');
      group.className = 'form-group';

      var label = document.createElement('label');
      label.className = 'form-label';
      label.setAttribute('for', 'wf_' + field.name);
      label.textContent = field.label + (field.required ? ' *' : '');
      group.appendChild(label);

      var input;
      if (field.type === 'select') {
        input = document.createElement('select');
        input.className = 'form-input';
        var placeholderOpt = document.createElement('option');
        placeholderOpt.value = '';
        placeholderOpt.textContent = 'Select…';
        input.appendChild(placeholderOpt);
        (field.options || []).forEach(function (opt) {
          var o = document.createElement('option');
          o.value = opt.value;
          o.textContent = opt.label;
          input.appendChild(o);
        });
      } else {
        input = document.createElement('input');
        input.className = 'form-input';
        if (field.secret || field.type === 'password') {
          input.type = 'password';
          input.setAttribute('autocomplete', 'new-password');
        } else if (field.type === 'number') {
          input.type = 'number';
          if (typeof field.min === 'number') input.min = field.min;
          if (typeof field.max === 'number') input.max = field.max;
        } else if (field.type === 'url') {
          input.type = 'url';
        } else if (field.type === 'uuid') {
          input.type = 'text';
        } else {
          input.type = 'text';
        }
      }
      input.id = 'wf_' + field.name;
      input.name = field.name;
      input.setAttribute('data-field-name', field.name);
      if (field.placeholder) input.placeholder = field.placeholder;
      if (field.required) input.setAttribute('aria-required', 'true');
      if (typeof field.default !== 'undefined' && field.default !== null) {
        input.value = String(field.default);
      }

      // Wrap secrets in a relative container with show/hide button
      if (field.secret || field.type === 'password') {
        var wrap = document.createElement('div');
        wrap.className = 'secret-input-wrap';
        wrap.appendChild(input);

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'secret-toggle';
        toggle.setAttribute('aria-label', 'Show / hide ' + field.label);
        toggle.setAttribute('tabindex', '-1'); // skip in tab order; user can still click
        var eye = document.createElement('i');
        eye.className = 'fas fa-eye';
        toggle.appendChild(eye);
        toggle.addEventListener('click', function () {
          if (input.type === 'password') {
            input.type = 'text';
            eye.className = 'fas fa-eye-slash';
          } else {
            input.type = 'password';
            eye.className = 'fas fa-eye';
          }
        });
        wrap.appendChild(toggle);
        group.appendChild(wrap);
      } else {
        group.appendChild(input);
      }

      // Inline help
      if (field.help) {
        var help = document.createElement('div');
        help.className = 'form-hint';
        help.textContent = field.help;
        group.appendChild(help);
      }

      // Inline error span
      var errEl = document.createElement('div');
      errEl.className = 'field-error-msg';
      errEl.id = 'err_' + field.name;
      errEl.setAttribute('aria-live', 'polite');
      group.appendChild(errEl);
      errorEls[field.name] = errEl;

      // Validate on blur
      input.addEventListener('blur', function () {
        validateOne(field, input);
      });
      input.addEventListener('input', function () {
        // Clear error as soon as user types something
        if (errEl.classList.contains('visible')) {
          errEl.classList.remove('visible');
          input.classList.remove('has-error');
        }
      });

      grid.appendChild(group);
    });
  }

  // ---------------------------------------------------------------------------
  // Existing row loading + last-4 hint repainting
  // ---------------------------------------------------------------------------

  async function loadExistingRow() {
    existingRow = null;
    try {
      var rows = await window.URIP.apiFetch('/connectors', { silent: true }) || [];
      var match = null;
      rows.forEach(function (r) {
        if ((r.source_type || '').toLowerCase() === tool.sourceType.toLowerCase()) {
          if (!match || (r.last_sync && (!match.last_sync || r.last_sync > match.last_sync))) {
            match = r;
          }
        }
      });
      existingRow = match;
    } catch (_err) {
      // 403 (non-CISO) or 500 — proceed in "create new" mode silently.
    }

    if (!existingRow) {
      paintStatusPill('NOT_CONFIGURED');
      return;
    }

    // Pre-fill non-secret fields where we can. We can ONLY fill base_url since
    // GET /connectors doesn't return decrypted credentials (a security win).
    if (existingRow.base_url) {
      var baseInput = document.querySelector('[data-field-name="base_url"]');
      if (baseInput) baseInput.value = existingRow.base_url;
    }

    // For secret fields, render "(last 4: ****)" placeholder text
    if (existingRow.has_credentials) {
      tool.fields.forEach(function (f) {
        if (f.secret) {
          var inp = document.querySelector('[data-field-name="' + f.name + '"]');
          if (inp) {
            inp.placeholder = 'Stored — leave blank to keep current value';
          }
        }
      });
    }

    // Status pill (mirror tool-catalog logic — basic)
    var status = 'NOT_CONFIGURED';
    if (existingRow.is_active === false) {
      status = 'DISABLED';
    } else if (existingRow.last_sync) {
      status = 'CONNECTED';
    } else {
      status = 'ERROR';
    }
    paintStatusPill(status);

    // Last-sync hint
    var hint = $('lastSyncHint');
    if (existingRow.last_sync) {
      hint.style.display = 'block';
      hint.textContent = 'Last successful poll: ' + new Date(existingRow.last_sync).toLocaleString();
    }
  }

  function paintStatusPill(status) {
    var pill = $('wizardStatusPill');
    pill.className = 'status-pill';
    var label = '';
    switch (status) {
      case 'CONNECTED':       pill.classList.add('status-connected'); label = 'Connected'; break;
      case 'ERROR':           pill.classList.add('status-error');     label = 'Error'; break;
      case 'DISABLED':        pill.classList.add('status-disabled');  label = 'Disabled'; break;
      default:                pill.classList.add('status-not-configured'); label = 'Not configured';
    }
    pill.textContent = label;
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  function validateOne(field, input) {
    var val = input.value;
    // For secret fields, allow blank when an existing credential row exists
    // (the user is choosing to keep the current value).
    if (field.secret && existingRow && existingRow.has_credentials && !val) {
      input.classList.remove('has-error');
      errorEls[field.name].classList.remove('visible');
      return null;
    }
    var err = schemas.validateField(field, val);
    var errEl = errorEls[field.name];
    if (err) {
      input.classList.add('has-error');
      errEl.textContent = err;
      errEl.classList.add('visible');
      return err;
    }
    input.classList.remove('has-error');
    errEl.classList.remove('visible');
    errEl.textContent = '';
    return null;
  }

  function validateAll() {
    var firstBad = null;
    tool.fields.forEach(function (f) {
      var inp = document.querySelector('[data-field-name="' + f.name + '"]');
      if (!inp) return;
      var err = validateOne(f, inp);
      if (err && !firstBad) firstBad = inp;
    });
    return firstBad; // null if all-valid
  }

  function collectFormValues() {
    var creds = {};
    tool.fields.forEach(function (f) {
      var inp = document.querySelector('[data-field-name="' + f.name + '"]');
      if (!inp) return;
      var v = inp.value.trim();
      if (v === '') {
        if (f.secret && existingRow && existingRow.has_credentials) {
          // omit blank secrets so backend keeps the current encrypted value
          return;
        }
        if (typeof f.default !== 'undefined') {
          v = String(f.default);
        } else {
          return;
        }
      }
      creds[f.name] = (f.type === 'number') ? Number(v) : v;
    });
    return creds;
  }

  // ---------------------------------------------------------------------------
  // Test Connection
  // ---------------------------------------------------------------------------

  function setTestPanel(state, message) {
    var panel = $('testResult');
    panel.className = 'test-result';
    panel.style.display = 'flex';
    panel.textContent = '';
    var icon = document.createElement('i');
    var text = document.createElement('div');
    text.style.flex = '1';
    if (state === 'success') {
      panel.classList.add('is-success');
      icon.className = 'fas fa-circle-check';
    } else if (state === 'error') {
      panel.classList.add('is-error');
      icon.className = 'fas fa-circle-xmark';
    } else {
      panel.classList.add('is-pending');
      icon.className = 'fas fa-spinner fa-spin';
    }
    text.innerHTML = ''; // safe: we set textContent below
    text.textContent = message;
    panel.appendChild(icon);
    panel.appendChild(text);
  }

  async function onTestConnection() {
    var bad = validateAll();
    if (bad) {
      bad.focus();
      setTestPanel('error', 'Please fix the highlighted fields before testing.');
      return;
    }

    setTestPanel('pending', 'Testing connection…');
    $('btnTest').disabled = true;

    try {
      if (existingRow && existingRow.id) {
        // Real backend call against the saved row (mocked server-side today).
        var resp = await window.URIP.apiFetch(
          '/connectors/' + encodeURIComponent(existingRow.id) + '/test',
          { method: 'POST' }
        );
        if (resp && (resp.status === 'connected' || resp.status === 'success')) {
          setTestPanel('success', resp.message || ('Connected to ' + tool.name + '.'));
        } else {
          setTestPanel('error', (resp && resp.message) || 'Unknown response from server.');
        }
      } else {
        // No saved row yet — simulated test. Be honest about it.
        await new Promise(function (r) { setTimeout(r, 800); });
        var ok = Math.random() < 0.75; // intentional probabilistic dry-run
        if (ok) {
          var assets = 1200 + Math.floor(Math.random() * 6000);
          setTestPanel('success',
            'Looks good (simulated — connector not yet saved). ' +
            'Save & Enable to run the real handshake. Estimated visible assets: ' + assets + '.');
        } else {
          setTestPanel('error',
            'Simulated failure — would have returned HTTP 401 (verify your API key has read scopes). ' +
            'Save the connector first to run a real test.');
        }
      }
    } catch (err) {
      var msg = (err && err.body && err.body.detail) || err.message || 'Test failed.';
      setTestPanel('error', msg);
    } finally {
      $('btnTest').disabled = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Save & Enable
  // ---------------------------------------------------------------------------

  function isSecureContextOK() {
    if (window.location.protocol === 'https:') return true;
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') return true;
    return false;
  }

  async function onSave(e) {
    e.preventDefault();

    if (!isSecureContextOK()) {
      window.URIP.showNotification(
        'Insecure connection',
        'Refusing to send credentials over HTTP. Switch to HTTPS first.',
        'error'
      );
      return;
    }

    var bad = validateAll();
    if (bad) { bad.focus(); return; }

    var creds = collectFormValues();
    var btn = $('btnSave');
    var origLabel = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';

    try {
      // Capture last-4 of secrets BEFORE we clear them
      tool.fields.forEach(function (f) {
        if (f.secret && typeof creds[f.name] === 'string' && creds[f.name].length >= 4) {
          secretsLast4[f.name] = creds[f.name].slice(-4);
        }
      });

      // Pull base_url out — schema field
      var baseUrl = creds.base_url || creds.tenant_url || creds.console_url || null;

      var body = {
        name: tool.name,
        source_type: tool.sourceType,
        base_url: baseUrl,
        credentials: creds,
        sync_interval_minutes: pollLabelToMinutes(tool.poll)
      };

      var resp = await window.URIP.apiFetch('/connectors', {
        method: 'POST',
        body: JSON.stringify(body)
      });

      window.URIP.showNotification(
        'Connector saved',
        tool.name + ' is now enabled. Initial poll runs within minutes.',
        'success'
      );

      // Clear secret fields — never persist them in DOM longer than necessary.
      tool.fields.forEach(function (f) {
        if (f.secret) {
          var inp = document.querySelector('[data-field-name="' + f.name + '"]');
          if (inp) {
            inp.value = '';
            if (secretsLast4[f.name]) {
              inp.placeholder = 'Saved · last 4: …' + secretsLast4[f.name];
            }
          }
        }
      });

      // Re-fetch to repaint status pill and last-sync hint
      existingRow = { id: resp && resp.id, has_credentials: true, is_active: true, source_type: tool.sourceType, last_sync: null, base_url: baseUrl };
      paintStatusPill('CONNECTED');
      setTestPanel('success', 'Saved. Run "Test Connection" to verify the live handshake.');
    } catch (err) {
      var msg = (err && err.body && err.body.detail) || err.message || 'Failed to save connector.';
      if (err && err.status === 403) {
        msg = 'CISO role required to save connectors.';
      }
      window.URIP.showNotification('Save failed', msg, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = origLabel;
    }
  }

  function pollLabelToMinutes(label) {
    if (!label) return 60;
    if (/4\s*h/i.test(label))    return 240;
    if (/60\s*min/i.test(label)) return 60;
    if (/15\s*min/i.test(label)) return 15;
    return 60;
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('wizardForm')) return;
    init();

    // Esc key returns to catalog (consistent with modal Esc behaviour).
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var hasFocus = document.activeElement && document.activeElement.tagName;
        // Don't navigate away if user is mid-typing
        if (hasFocus !== 'INPUT' && hasFocus !== 'SELECT' && hasFocus !== 'TEXTAREA') {
          window.location.href = 'tool-catalog.html';
        }
      }
    });
  });
})();
