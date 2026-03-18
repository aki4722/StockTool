<?php
header('Content-Type: application/json');
$symbols = trim($_GET['symbols'] ?? '');
if (!$symbols) {
    echo json_encode([]);
    exit;
}
$api_base = 'http://localhost:5001';
$url      = $api_base . '/stocks?symbols=' . urlencode($symbols);
$response = @file_get_contents($url);
if ($response === false) {
    echo json_encode(['error' => 'Could not connect to backend']);
    exit;
}
echo $response;
