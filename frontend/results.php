<?php
$symbol = strtoupper(trim($_GET['symbol'] ?? ''));
$api_base = 'http://localhost:5001';
$data = null;
$error = null;

include 'header.php';

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
    <div class="container">
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
<?php include 'footer.php'; ?>
