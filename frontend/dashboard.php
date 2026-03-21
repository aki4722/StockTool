<?php
$raw     = trim($_GET['symbols'] ?? '');
$api_base = 'http://localhost:5001';
$stocks  = [];
$error   = null;

if ($raw) {
    $url      = $api_base . '/stocks?symbols=' . urlencode($raw);
    $response = @file_get_contents($url);
    if ($response !== false) {
        $decoded = json_decode($response, true);
        if (isset($decoded['error'])) {
            $error = $decoded['error'];
        } else {
            $stocks = $decoded;
        }
    } else {
        $error = 'Could not connect to backend. Make sure the Python server is running.';
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockTool Dashboard</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container dashboard-container">
        <h1><a href="index.php">StockTool</a></h1>

        <form method="GET" action="dashboard.php" class="dash-form" onsubmit="this.elements.symbols.value=normalizeSymbols(this.elements.symbols.value)">
            <input type="text" name="symbols" value="<?= htmlspecialchars($raw) ?>" placeholder="AAPL, MSFT, 6178.T" required>
            <button type="submit">Refresh</button>
        </form>

        <?php if ($error): ?>
            <p class="error"><?= htmlspecialchars($error) ?></p>
        <?php elseif ($stocks): ?>
            <table class="stock-table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Symbol</th>
                        <th>Company</th>
                        <th>Price</th>
                        <th>Change (¥)</th>
                        <th>Change (%)</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($stocks as $s): ?>
                        <?php if (isset($s['error'])): ?>
                            <tr class="row-error">
                                <td></td>
                                <td><?= htmlspecialchars($s['symbol']) ?></td>
                                <td colspan="5" class="error"><?= htmlspecialchars($s['error']) ?></td>
                            </tr>
                        <?php else: ?>
                            <?php
                                $up  = ($s['change'] ?? 0) >= 0;
                                $cls = $up ? 'positive' : 'negative';
                                $sign = $up ? '+' : '';
                                $sym = htmlspecialchars($s['symbol']);
                            ?>
                            <tr class="row-clickable" onclick="window.location='results.php?symbol=<?= urlencode($s['symbol']) ?>'">
                                <td class="star-cell">
                                    <button class="star-btn" id="star-<?= $sym ?>"
                                            data-symbol="<?= $sym ?>"
                                            onclick="event.stopPropagation(); toggleWatchlist(this)">☆</button>
                                </td>
                                <td class="sym"><?= $sym ?></td>
                                <td class="name-cell"><?= htmlspecialchars($s['name'] ?? '') ?></td>
                                <td class="price-cell">
                                    <?= htmlspecialchars(number_format((float)$s['price'], 2)) ?>
                                </td>
                                <td class="<?= $cls ?>">
                                    <?= $sign . '¥' . htmlspecialchars(number_format((float)$s['change'], 2)) ?>
                                </td>
                                <td class="<?= $cls ?>">
                                    <?= $sign . htmlspecialchars($s['change_percent']) ?>%
                                </td>
                            </tr>
                        <?php endif; ?>
                    <?php endforeach; ?>
                </tbody>
            </table>
        <?php elseif ($raw): ?>
            <p class="error">No data returned.</p>
        <?php endif; ?>

        <a href="index.php">← New search</a>
    </div>
<script>
function normalizeSymbols(input) {
    return input.split(',').map(s => {
        const t = s.trim();
        return /^\d{4}$/.test(t) ? t + '.T' : t;
    }).join(', ');
}

function getWatchlist() {
    return JSON.parse(localStorage.getItem('watchlist') || '[]');
}
function saveWatchlist(list) {
    localStorage.setItem('watchlist', JSON.stringify(list));
}
function toggleWatchlist(btn) {
    const symbol = btn.dataset.symbol;
    const list = getWatchlist();
    const idx = list.indexOf(symbol);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(symbol);
    }
    saveWatchlist(list);
    updateStar(btn, list);
}
function updateStar(btn, list) {
    const inList = list.includes(btn.dataset.symbol);
    btn.textContent = inList ? '★' : '☆';
    btn.classList.toggle('active', inList);
}
function updateAllStars() {
    const list = getWatchlist();
    document.querySelectorAll('.star-btn').forEach(btn => updateStar(btn, list));
}
document.addEventListener('DOMContentLoaded', updateAllStars);
</script>
</body>
</html>
