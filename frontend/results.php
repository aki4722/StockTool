<?php
$symbol = strtoupper(trim($_GET['symbol'] ?? ''));
$api_base = 'http://localhost:5001';
$data = null;
$error = null;

if ($symbol) {
    $url = $api_base . '/stock/' . urlencode($symbol);
    $response = @file_get_contents($url);
    if ($response !== false) {
        $data = json_decode($response, true);
        if (isset($data['error'])) {
            $error = $data['error'];
            $data = null;
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
    <title>StockTool - <?= htmlspecialchars($symbol) ?></title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="container">
        <h1><a href="index.php">StockTool</a></h1>
        <?php if ($error): ?>
            <p class="error"><?= htmlspecialchars($error) ?></p>
        <?php elseif ($data): ?>
            <div class="stock-card">
                <h2><?= htmlspecialchars($data['symbol']) ?></h2>
                <p class="price">$<?= htmlspecialchars($data['price'] ?? 'N/A') ?></p>
                <p class="change">
                    <?= htmlspecialchars($data['change'] ?? 'N/A') ?>
                    (<?= htmlspecialchars($data['change_percent'] ?? 'N/A') ?>)
                </p>
            </div>
        <?php endif; ?>
        <a href="index.php">← Back</a>
    </div>
</body>
</html>
