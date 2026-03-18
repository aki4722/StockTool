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
    <div class="container index-container">
        <h1>StockTool</h1>

        <div id="watchlist-section" style="display:none" class="watchlist-section">
            <h2>Saved Watchlist</h2>
            <div id="watchlist-content"></div>
        </div>

        <form method="GET" action="dashboard.php">
            <input type="text" name="symbols" placeholder="AAPL, MSFT, 6178.T" required>
            <button type="submit">Look Up</button>
        </form>
        <p class="hint">Enter one or more comma-separated symbols</p>
    </div>
<script>
function getWatchlist() {
    return JSON.parse(localStorage.getItem('watchlist') || '[]');
}
function removeFromWatchlist(symbol) {
    const list = getWatchlist().filter(s => s !== symbol);
    localStorage.setItem('watchlist', JSON.stringify(list));
    loadWatchlist();
}
function esc(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function renderWatchlist(stocks) {
    const content = document.getElementById('watchlist-content');
    let html = '<table class="stock-table watchlist-table"><thead><tr>'
        + '<th>Symbol</th><th>Company</th><th>Price</th><th>Change %</th><th></th>'
        + '</tr></thead><tbody>';
    for (const s of stocks) {
        if (s.error) {
            html += `<tr class="row-error">`
                + `<td class="sym">${esc(s.symbol)}</td>`
                + `<td colspan="3" class="error">${esc(s.error)}</td>`
                + `<td><button class="remove-btn" data-symbol="${esc(s.symbol)}" onclick="removeFromWatchlist(this.dataset.symbol)">✕</button></td>`
                + `</tr>`;
        } else {
            const up = (parseFloat(s.change) || 0) >= 0;
            const cls = up ? 'positive' : 'negative';
            const sign = up ? '+' : '';
            html += `<tr class="row-clickable" onclick="window.location='results.php?symbol=${encodeURIComponent(s.symbol)}'">`
                + `<td class="sym">${esc(s.symbol)}</td>`
                + `<td class="name-cell">${esc(s.name ?? '')}</td>`
                + `<td class="price-cell">${parseFloat(s.price).toFixed(2)}</td>`
                + `<td class="${cls}">${sign}${esc(String(s.change_percent))}%</td>`
                + `<td><button class="remove-btn" data-symbol="${esc(s.symbol)}" onclick="event.stopPropagation();removeFromWatchlist(this.dataset.symbol)">✕</button></td>`
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
document.addEventListener('DOMContentLoaded', loadWatchlist);
</script>
</body>
</html>
