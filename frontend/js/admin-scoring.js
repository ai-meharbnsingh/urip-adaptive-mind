/**
 * URIP — Per-Tenant Scoring Weights UI (P1.9)
 *
 * Loads the active scoring formula from GET /api/settings/scoring, lets the
 * admin tune the weights, and PATCHes them back.
 *
 * Backend gap (honest note)
 * -------------------------
 * Today only GET /api/settings/scoring exists. There is NO PATCH /scoring
 * route in backend/routers/settings.py. We POST/PATCH against
 * /api/settings/scoring; if the backend returns 404/405 we surface a clear
 * error and keep the form in dirty state (no silent failure). When the
 * backend lands the route this UI works unchanged.
 *
 * Depends on: api.js, theming.js
 */
(function () {
  'use strict';

  // Initial config from server (used for reset + dirty detection)
  var initialConfig = null;
  // Server defaults (matches backend/services/scoring_config.py)
  var HARD_DEFAULTS = {
    cvss: 0.55,
    epss: 2.5,
    kev_bonus: 2.0,
    tier_1: 1.0,
    tier_2: 0.5,
    tier_3: 0.0,
    tier_4: -0.5
  };

  // ---------------------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------------------
  function $(id) { return document.getElementById(id); }

  function showError(msg) {
    $('scoringLoading').style.display = 'none';
    $('scoringError').style.display = 'flex';
    $('scoringErrorMsg').textContent = msg;
  }

  function hideError() {
    $('scoringError').style.display = 'none';
  }

  function showContent() {
    $('scoringLoading').style.display = 'none';
    hideError();
    $('scoringContent').style.display = 'block';
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  function setFormValues(weights, tierBonuses) {
    $('w_cvss').value = formatNum(weights.cvss);
    $('w_epss').value = formatNum(weights.epss);
    $('w_kev').value = formatNum(weights.kev_bonus);
    $('t_1').value = formatNum(tierBonuses['1']);
    $('t_2').value = formatNum(tierBonuses['2']);
    $('t_3').value = formatNum(tierBonuses['3']);
    $('t_4').value = formatNum(tierBonuses['4']);
  }

  function formatNum(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '0';
    var num = Number(n);
    return Number.isInteger(num) ? String(num) : num.toFixed(2).replace(/\.?0+$/, '');
  }

  function readForm() {
    function num(id) {
      var v = $(id).value;
      var parsed = parseFloat(v);
      return Number.isNaN(parsed) ? 0 : parsed;
    }
    return {
      weights: {
        cvss: num('w_cvss'),
        epss: num('w_epss'),
        kev_bonus: num('w_kev')
      },
      tier_bonuses: {
        '1': num('t_1'),
        '2': num('t_2'),
        '3': num('t_3'),
        '4': num('t_4')
      }
    };
  }

  function renderFormulaText(version, formula) {
    $('formulaVersion').textContent = 'v' + (version || '?');
    $('formulaText').textContent = formula || '';
  }

  /**
   * Plug current weights into the formula string for a live preview.
   * Example output:
   *   max(0, min(10, 0.55*CVSS + 2.5*EPSS + 2 + asset_bonus))
   */
  function renderPreview() {
    var f = readForm();
    var w = f.weights;
    var preview =
      'max(0, min(10, ' +
      formatNum(w.cvss) + ' * CVSS  +  ' +
      formatNum(w.epss) + ' * EPSS  +  ' +
      'KEV_bonus(' + formatNum(w.kev_bonus) + ')  +  ' +
      'tier_bonus(' +
        'T1=' + formatNum(f.tier_bonuses['1']) + ', ' +
        'T2=' + formatNum(f.tier_bonuses['2']) + ', ' +
        'T3=' + formatNum(f.tier_bonuses['3']) + ', ' +
        'T4=' + formatNum(f.tier_bonuses['4']) +
      ')))';
    $('formulaPreview').textContent = preview;

    // Dirty indicator
    var dirty = isDirty();
    var ind = $('dirtyIndicator');
    if (dirty) {
      ind.textContent = 'Unsaved changes';
      ind.style.color = '#E67E22';
    } else {
      ind.textContent = 'Saved';
      ind.style.color = '#27AE60';
    }
  }

  function renderReadOnly(cfg) {
    var epss = cfg.epss_defaults || {};
    $('epssDefaults').textContent =
      'critical=' + (epss.critical ?? '–') +
      '  high=' + (epss.high ?? '–') +
      '  medium=' + (epss.medium ?? '–') +
      '  low=' + (epss.low ?? '–');

    var ex = cfg.exploit_thresholds || {};
    $('exploitThresholds').textContent =
      'active≥' + (ex.active ?? '–') + '   poc≥' + (ex.poc ?? '–');

    var sla = cfg.sla_hours || {};
    $('slaHours').textContent =
      'critical=' + (sla.critical ?? '–') + 'h   ' +
      'high=' + (sla.high ?? '–') + 'h   ' +
      'medium=' + (sla.medium ?? '–') + 'h   ' +
      'low=' + (sla.low ?? '–') + 'h';
  }

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  function validateForm() {
    var errors = [];
    var f = readForm();

    function check(name, val, min, max) {
      if (Number.isNaN(val)) errors.push(name + ' must be a number.');
      else if (val < min) errors.push(name + ' must be ≥ ' + min + '.');
      else if (val > max) errors.push(name + ' must be ≤ ' + max + '.');
    }

    check('CVSS weight', f.weights.cvss, 0, 10);
    check('EPSS weight', f.weights.epss, 0, 10);
    check('KEV bonus', f.weights.kev_bonus, 0, 10);
    check('Tier 1 bonus', f.tier_bonuses['1'], -2, 10);
    check('Tier 2 bonus', f.tier_bonuses['2'], -2, 10);
    check('Tier 3 bonus', f.tier_bonuses['3'], -2, 10);
    check('Tier 4 bonus', f.tier_bonuses['4'], -2, 10);

    return errors;
  }

  function isDirty() {
    if (!initialConfig) return false;
    var cur = readForm();
    var w = initialConfig.weights || {};
    var t = initialConfig.tier_bonuses || {};
    return (
      cur.weights.cvss !== Number(w.cvss) ||
      cur.weights.epss !== Number(w.epss) ||
      cur.weights.kev_bonus !== Number(w.kev_bonus) ||
      cur.tier_bonuses['1'] !== Number(t['1']) ||
      cur.tier_bonuses['2'] !== Number(t['2']) ||
      cur.tier_bonuses['3'] !== Number(t['3']) ||
      cur.tier_bonuses['4'] !== Number(t['4'])
    );
  }

  // ---------------------------------------------------------------------------
  // API
  // ---------------------------------------------------------------------------

  async function loadConfig() {
    $('scoringLoading').style.display = 'flex';
    $('scoringContent').style.display = 'none';
    hideError();

    try {
      var cfg = await window.URIP.apiFetch('/settings/scoring');
      initialConfig = cfg;
      renderFormulaText(cfg.formula_version, cfg.formula);
      setFormValues(cfg.weights || {}, cfg.tier_bonuses || {});
      renderReadOnly(cfg);
      renderPreview();
      showContent();
    } catch (err) {
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) ||
                'Unknown error loading scoring configuration.';
      if (err && err.status === 403) {
        msg = 'You do not have permission to view scoring configuration.';
      }
      showError(msg);
    }
  }

  async function saveConfig() {
    var errors = validateForm();
    if (errors.length) {
      window.URIP.showNotification('Validation Error', errors.join(' '), 'error');
      return;
    }

    var f = readForm();
    var btn = $('btnSave');
    var originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      // Backend route may be PATCH /settings/scoring (planned). Try PATCH first.
      var updated = await window.URIP.apiFetch('/settings/scoring', {
        method: 'PATCH',
        body: JSON.stringify({
          weights: f.weights,
          tier_bonuses: f.tier_bonuses
        })
      });
      if (updated) {
        initialConfig = updated;
        renderFormulaText(updated.formula_version, updated.formula);
        setFormValues(updated.weights || {}, updated.tier_bonuses || {});
        renderReadOnly(updated);
      } else {
        // Some servers return 204 No Content — re-fetch to confirm
        await loadConfig();
      }
      renderPreview();
      window.URIP.showNotification('Saved', 'Scoring weights updated successfully.', 'success');
    } catch (err) {
      var msg = (err && err.body && err.body.detail) ||
                (err && err.message) ||
                'Failed to save scoring weights.';
      if (err && (err.status === 404 || err.status === 405)) {
        msg = 'Backend gap: PATCH /settings/scoring is not yet implemented. ' +
              'Your changes were not persisted. Notify the backend team.';
      } else if (err && err.status === 403) {
        msg = 'You do not have permission to update scoring weights.';
      }
      window.URIP.showNotification('Save Failed', msg, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    }
  }

  // ---------------------------------------------------------------------------
  // Event wiring
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('scoringForm')) return; // not on this page

    loadConfig();

    // Live preview on input
    var inputs = document.querySelectorAll('#scoringForm input[type="number"]');
    inputs.forEach(function (inp) {
      inp.addEventListener('input', renderPreview);
    });

    $('btnReload').addEventListener('click', function (e) {
      e.preventDefault();
      loadConfig();
    });

    $('btnReset').addEventListener('click', function (e) {
      e.preventDefault();
      setFormValues(
        { cvss: HARD_DEFAULTS.cvss, epss: HARD_DEFAULTS.epss, kev_bonus: HARD_DEFAULTS.kev_bonus },
        { '1': HARD_DEFAULTS.tier_1, '2': HARD_DEFAULTS.tier_2, '3': HARD_DEFAULTS.tier_3, '4': HARD_DEFAULTS.tier_4 }
      );
      renderPreview();
    });

    $('btnCancel').addEventListener('click', function (e) {
      e.preventDefault();
      if (initialConfig) {
        setFormValues(initialConfig.weights || {}, initialConfig.tier_bonuses || {});
        renderPreview();
      }
    });

    $('scoringForm').addEventListener('submit', function (e) {
      e.preventDefault();
      saveConfig();
    });

    // Warn on unload if dirty
    window.addEventListener('beforeunload', function (e) {
      if (isDirty()) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  });
})();
