<?php
// Common header with navigation menu
$current_page = basename($_SERVER['PHP_SELF']);
?>
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockTool - BBS Sentiment Analysis</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
        }
        
        /* Navigation Menu */
        nav.navbar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            padding: 0 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
        }
        
        nav.navbar .container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
        }
        
        nav.navbar .logo {
            color: white;
            font-size: 24px;
            font-weight: bold;
            padding: 15px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        nav.navbar .logo span {
            font-size: 28px;
        }
        
        nav.navbar ul {
            list-style: none;
            display: flex;
            gap: 0;
        }
        
        nav.navbar ul li {
            margin: 0;
        }
        
        nav.navbar ul li a {
            display: block !important;
            color: white !important;
            text-decoration: none !important;
            padding: 20px 20px !important;
            transition: background 0.3s ease !important;
            font-weight: 500 !important;
            background: transparent !important;
        }
        
        nav.navbar ul li a:hover {
            background: rgba(255,255,255,0.2);
        }
        
        nav.navbar ul li a.active {
            background: rgba(255,255,255,0.3);
            border-bottom: 3px solid white;
        }
        
        /* Main container */
        .main-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
    </style>
</head>
<body>
    <!-- Navigation Menu -->
    <nav class="navbar">
        <div class="container">
            <div class="logo">
                StockTool
            </div>
            <ul>
                <li><a href="index.php" class="<?= $current_page === 'index.php' ? 'active' : '' ?>">Home</a></li>
                <li><a href="dashboard.php" class="<?= $current_page === 'dashboard.php' ? 'active' : '' ?>">Dashboard</a></li>
                <li><a href="bbs_ranking.php" class="<?= $current_page === 'bbs_ranking.php' ? 'active' : '' ?>">BBS Ranking</a></li>
                <li><a href="results.php" class="<?= $current_page === 'results.php' ? 'active' : '' ?>">Search</a></li>
            </ul>
        </div>
    </nav>
    
    <div class="main-content">
