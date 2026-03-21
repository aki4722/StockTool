<?php
$api_base = 'http://localhost:5001';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockTool</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <!-- Alert Banner -->
    <div id="alert-banner" style="display:none" class="alert-banner">
        <span id="alert-banner-text"></span>
        <button class="alert-close-btn" onclick="document.getElementById('alert-banner').style.display='none'">✕</button>
    </div>

    <!-- Alert Settings Modal -->
    <div id="alert-modal" style="display:none" class="modal-overlay" onclick="if(event.target===this)closeAlertModal()">
        <div class="modal-box">
            <h3>Alert: <span id="modal-symbol"></span></h3>
            <div class="modal-field">
                <label for="alert-threshold">Threshold (±%)</label>
                <input type="number" id="alert-threshold" min="0.1" step="0.1" value="5">
            </div>
            <div class="modal-field">
                <label for="alert-interval">Poll interval (sec)</label>
                <input type="number" id="alert-interval" min="10" step="5" value="30">
            </div>
            <div class="modal-field">
                <label for="alert-lookback">Lookback (min)</label>
                <input type="number" id="alert-lookback" min="1" step="1" value="3">
            </div>
            <div class="modal-field">
                <label for="alert-enabled">Enabled</label>
                <input type="checkbox" id="alert-enabled">
            </div>
            <div class="modal-buttons">
                <button onclick="saveAlert()">Save</button>
                <button class="btn-cancel" onclick="closeAlertModal()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="container index-container">
        <h1>StockTool</h1>

        <div id="watchlist-section" style="display:none" class="watchlist-section">
            <h2>Saved Watchlist</h2>
            <div id="watchlist-content"></div>
            <small id="watchlist-updated" class="watchlist-updated-ts"></small>
        </div>

        <form method="GET" action="dashboard.php" onsubmit="this.elements.symbols.value=normalizeSymbols(this.elements.symbols.value)">
            <input type="text" name="symbols" placeholder="AAPL, MSFT, 6178.T" required>
            <button type="submit">Look Up</button>
        </form>
        <p class="hint">Enter one or more comma-separated symbols</p>
    </div>
<script>
function normalizeSymbols(input) {
    return input.split(',').map(s => {
        const t = s.trim();
        return /^\d{4}$/.test(t) ? t + '.T' : t;
    }).join(', ');
}

// ── Watchlist helpers ────────────────────────────────────────
function getWatchlist() {
    return JSON.parse(localStorage.getItem('watchlist') || '[]');
}
function removeFromWatchlist(symbol) {
    const list = getWatchlist().filter(s => s !== symbol);
    localStorage.setItem('watchlist', JSON.stringify(list));
    stopMonitoring(symbol);
    loadWatchlist();
}
function esc(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Alert settings ───────────────────────────────────────────
const ALERT_KEY = 'alertSettings';
function getAlertSettings() {
    return JSON.parse(localStorage.getItem(ALERT_KEY) || '{}');
}
function saveAlertSettings(settings) {
    localStorage.setItem(ALERT_KEY, JSON.stringify(settings));
}
function getSymbolAlert(symbol) {
    return getAlertSettings()[symbol] || { threshold: 5, interval: 30, lookback: 3, enabled: false };
}

// ── Alert Modal ──────────────────────────────────────────────
let modalSymbol = null;
function openAlertModal(symbol) {
    modalSymbol = symbol;
    const cfg = getSymbolAlert(symbol);
    document.getElementById('modal-symbol').textContent = symbol;
    document.getElementById('alert-threshold').value = cfg.threshold;
    document.getElementById('alert-interval').value = cfg.interval;
    document.getElementById('alert-lookback').value = cfg.lookback;
    document.getElementById('alert-enabled').checked = cfg.enabled;
    document.getElementById('alert-modal').style.display = 'flex';
}
function closeAlertModal() {
    document.getElementById('alert-modal').style.display = 'none';
    modalSymbol = null;
}
function saveAlert() {
    const sym = modalSymbol;
    const cfg = {
        threshold: parseFloat(document.getElementById('alert-threshold').value) || 5,
        interval: parseInt(document.getElementById('alert-interval').value) || 30,
        lookback: parseInt(document.getElementById('alert-lookback').value) || 3,
        enabled: document.getElementById('alert-enabled').checked
    };
    const settings = getAlertSettings();
    settings[sym] = cfg;
    saveAlertSettings(settings);
    closeAlertModal();
    stopMonitoring(sym);
    if (cfg.enabled) startMonitoring(sym);
    if (lastWatchlistData) renderWatchlist(lastWatchlistData);
}

// ── Price monitoring ─────────────────────────────────────────
const priceHistory = {};   // symbol -> [{time, price}]
const alertIntervals = {}; // symbol -> intervalId
let lastWatchlistData = null;

function startMonitoring(symbol) {
    if (alertIntervals[symbol]) return;
    const cfg = getSymbolAlert(symbol);
    checkAlert(symbol); // fetch immediately
    alertIntervals[symbol] = setInterval(() => checkAlert(symbol), cfg.interval * 1000);
}

function stopMonitoring(symbol) {
    if (alertIntervals[symbol]) {
        clearInterval(alertIntervals[symbol]);
        delete alertIntervals[symbol];
    }
}

async function checkAlert(symbol) {
    try {
        const resp = await fetch('watchlist_proxy.php?symbols=' + encodeURIComponent(symbol));
        const data = await resp.json();
        if (!Array.isArray(data) || !data[0] || data[0].error) return;
        const price = parseFloat(data[0].price);
        if (isNaN(price)) return;

        const now = Date.now();
        if (!priceHistory[symbol]) priceHistory[symbol] = [];
        priceHistory[symbol].push({ time: now, price });

        const cfg = getSymbolAlert(symbol);
        const lookbackMs = cfg.lookback * 60 * 1000;
        priceHistory[symbol] = priceHistory[symbol].filter(e => now - e.time <= lookbackMs);

        if (priceHistory[symbol].length >= 2) {
            const oldest = priceHistory[symbol][0];
            const changePct = (price - oldest.price) / oldest.price * 100;
            if (Math.abs(changePct) >= cfg.threshold) {
                const sign = changePct >= 0 ? '+' : '';
                triggerAlert(symbol, sign + changePct.toFixed(2) + '%', price, oldest.price, cfg.lookback);
            }
        }

        if (lastWatchlistData) {
            const entry = lastWatchlistData.find(s => s.symbol === symbol);
            if (entry) {
                entry.price = data[0].price;
                entry.change = data[0].change;
                entry.change_percent = data[0].change_percent;
            }
            renderWatchlist(lastWatchlistData, true);
        }
    } catch (e) { /* ignore network errors */ }
}

function triggerAlert(symbol, changePct, currentPrice, oldPrice, lookbackMin) {
    playAlertSound();
    const banner = document.getElementById('alert-banner');
    document.getElementById('alert-banner-text').textContent =
        `ALERT: ${symbol} changed ${changePct} over ${lookbackMin} min  (${parseFloat(oldPrice).toFixed(2)} \u2192 ${parseFloat(currentPrice).toFixed(2)})`;
    banner.style.display = 'flex';
    clearTimeout(banner._timer);
    banner._timer = setTimeout(() => { banner.style.display = 'none'; }, 15000);
}

function playAlertSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        osc.type = 'sine';
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.8);
    } catch (e) { /* no audio context */ }
}

// ── Watchlist render ─────────────────────────────────────────
function renderWatchlist(stocks, showUpdated = false) {
    lastWatchlistData = stocks;
    const content = document.getElementById('watchlist-content');
    if (showUpdated) {
        const ts = document.getElementById('watchlist-updated');
        if (ts) ts.textContent = 'Updated ' + new Date().toLocaleTimeString();
    }
    const alertSettings = getAlertSettings();
    let html = '<table class="stock-table watchlist-table"><thead><tr>'
        + '<th>Symbol</th><th>Company</th><th>Price</th><th>Change (¥)</th><th>Change (%)</th><th></th>'
        + '</tr></thead><tbody>';
    for (const s of stocks) {
        const alertCfg = alertSettings[s.symbol] || {};
        const isActive = alertCfg.enabled ? ' alert-active' : '';
        const alertBtn = `<button class="alert-btn${isActive}" data-symbol="${esc(s.symbol)}" onclick="event.stopPropagation();openAlertModal(this.dataset.symbol)" title="Alert settings">\uD83D\uDD14</button>`;
        if (s.error) {
            html += `<tr class="row-error">`
                + `<td class="sym">${esc(s.symbol)}</td>`
                + `<td colspan="4" class="error">${esc(s.error)}</td>`
                + `<td class="action-cell">${alertBtn}<button class="remove-btn" data-symbol="${esc(s.symbol)}" onclick="removeFromWatchlist(this.dataset.symbol)">✕</button></td>`
                + `</tr>`;
        } else {
            const up = (parseFloat(s.change) || 0) >= 0;
            const cls = up ? 'positive' : 'negative';
            const sign = up ? '+' : '';
            const changeAmt = parseFloat(s.change) || 0;
            const changeSign = changeAmt >= 0 ? '+' : '';
            html += `<tr class="row-clickable" onclick="window.location='results.php?symbol=${encodeURIComponent(s.symbol)}'">`
                + `<td class="sym">${esc(s.symbol)}</td>`
                + `<td class="name-cell">${esc(s.name ?? '')}</td>`
                + `<td class="price-cell">${parseFloat(s.price).toFixed(2)}</td>`
                + `<td class="${cls}">${changeSign}¥${Math.abs(changeAmt).toFixed(2)}</td>`
                + `<td class="${cls}">${sign}${esc(String(s.change_percent))}%</td>`
                + `<td class="action-cell">${alertBtn}<button class="remove-btn" data-symbol="${esc(s.symbol)}" onclick="event.stopPropagation();removeFromWatchlist(this.dataset.symbol)">✕</button></td>`
                + `</tr>`;
        }
    }
    html += '</tbody></table>';
    content.innerHTML = html;
}

async function loadWatchlist() {
    const list = getWatchlist();
    const section = document.getElementById('watchlist-section');
    if (list.length === 0) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';
    document.getElementById('watchlist-content').innerHTML = '<p class="hint">Loading&hellip;</p>';
    try {
        const resp = await fetch('watchlist_proxy.php?symbols=' + encodeURIComponent(list.join(',')));
        const data = await resp.json();
        if (Array.isArray(data)) {
            renderWatchlist(data);
        } else {
            document.getElementById('watchlist-content').innerHTML = '<p class="error">Could not load watchlist data.</p>';
        }
    } catch (e) {
        document.getElementById('watchlist-content').innerHTML = '<p class="error">Could not load watchlist data.</p>';
    }
}

function initAlertMonitoring() {
    const settings = getAlertSettings();
    for (const [symbol, cfg] of Object.entries(settings)) {
        if (cfg.enabled) startMonitoring(symbol);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadWatchlist();
    initAlertMonitoring();
});
</script>
</body>
</html>
