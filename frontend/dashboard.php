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

        <form method="GET" action="dashboard.php" class="dash-form">
            <input type="text" name="symbols" value="<?= htmlspecialchars($raw) ?>" placeholder="AAPL, MSFT, 6178.T" required>
            <button type="submit">Refresh</button>
        </form>

        <?php if ($error): ?>
            <p class="error"><?= htmlspecialchars($error) ?></p>
        <?php elseif ($stocks): ?>
            <table class="stock-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Change</th>
                        <th>Change %</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($stocks as $s): ?>
                        <?php if (isset($s['error'])): ?>
                            <tr class="row-error">
                                <td><?= htmlspecialchars($s['symbol']) ?></td>
                                <td colspan="3" class="error"><?= htmlspecialchars($s['error']) ?></td>
                            </tr>
                        <?php else: ?>
                            <?php
                                $up  = ($s['change'] ?? 0) >= 0;
                                $cls = $up ? 'positive' : 'negative';
                                $sign = $up ? '+' : '';
                            ?>
                            <tr class="row-clickable" onclick="window.location='results.php?symbol=<?= urlencode($s['symbol']) ?>'">
                                <td class="sym"><?= htmlspecialchars($s['symbol']) ?></td>
                                <td class="price-cell">
                                    <?= htmlspecialchars(number_format((float)$s['price'], 2)) ?>
                                </td>
                                <td class="<?= $cls ?>">
                                    <?= $sign . htmlspecialchars($s['change']) ?>
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
</body>
</html>
