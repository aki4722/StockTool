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
        <form method="GET" action="results.php">
            <input type="text" name="symbol" placeholder="Enter stock symbol (e.g. AAPL)" required>
            <button type="submit">Look Up</button>
        </form>
    </div>
</body>
</html>
