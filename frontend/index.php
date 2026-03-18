<?php
$api_base = 'http://localhost:5000';
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
    <div class="container">
        <h1>StockTool</h1>
        <form method="GET" action="dashboard.php">
            <input type="text" name="symbols" placeholder="AAPL, MSFT, 6178.T" required>
            <button type="submit">Look Up</button>
        </form>
        <p class="hint">Enter one or more comma-separated symbols</p>
    </div>
</body>
</html>
