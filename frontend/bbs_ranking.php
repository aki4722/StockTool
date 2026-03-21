<?php
$api_base = 'http://localhost:5001';

// Fetch available dates
$dates = [];
$dates_resp = @file_get_contents($api_base . '/api/bbs-dates');
if ($dates_resp !== false) {
    $dates = json_decode($dates_resp, true) ?: [];
}

// Selected date (default to most recent available, or today)
$selected_date = trim($_GET['date'] ?? '');
if (!$selected_date) {
    $selected_date = $dates[0] ?? date('Y-m-d');
}

// Fetch ranking for selected date
$rankings = [];
$error = null;
$url = $api_base . '/api/bbs-ranking?date=' . urlencode($selected_date);
$resp = @file_get_contents($url);
if ($resp === false) {
    $error = 'Could not connect to backend. Make sure the Python server is running.';
} else {
    $decoded = json_decode($resp, true);
    if (isset($decoded['error'])) {
        $error = $decoded['error'];
    } else {
        $rankings = $decoded ?: [];
    }
}

function sentiment_class(float $score): string {
    if ($score > 0.3)  return 'sent-positive';
    if ($score < -0.3) return 'sent-negative';
    return 'sent-neutral';
}

function sentiment_label(float $score): string {
    if ($score > 0.3)  return '🟢 ' . number_format($score, 2);
    if ($score < -0.3) return '🔴 ' . number_format($score, 2);
    return '🟡 ' . number_format($score, 2);
}

function status_badge(string $status): string {
    switch ($status) {
        case 'new':      return '<span class="badge badge-new">🟢 new</span>';
        case 'dropped':  return '<span class="badge badge-dropped">🔴 dropped</span>';
        default:         return '<span class="badge badge-existing">⚪ existing</span>';
    }
}

function risk_class(string $risk): string {
    switch ($risk) {
        case 'high': return 'risk-high';
        case 'low':  return 'risk-low';
        default:     return 'risk-medium';
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BBS Ranking – StockTool</title>
    <link rel="stylesheet" href="css/style.css">
    <style>
        .bbs-container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px 16px;
        }

        .bbs-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }

        .bbs-header h1 {
            margin: 0;
            font-size: 1.4rem;
            color: #e2e8f0;
        }

        .bbs-header h1 a {
            color: #38bdf8;
            text-decoration: none;
        }

        .date-picker-form {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: auto;
        }

        .date-picker-form label {
            color: #94a3b8;
            font-size: 0.85rem;
        }

        .date-picker-form select {
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 0.9rem;
            cursor: pointer;
        }

        .date-picker-form select:focus {
            outline: none;
            border-color: #38bdf8;
        }

        .bbs-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }

        .bbs-table th {
            background: #1e293b;
            color: #94a3b8;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #334155;
            white-space: nowrap;
        }

        .bbs-table th.right { text-align: right; }

        .bbs-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #1e293b;
            vertical-align: top;
        }

        .bbs-table tr:hover td {
            background: #1e293b;
        }

        .bbs-table tr.row-detail-open td {
            background: #162032;
        }

        .col-rank {
            color: #64748b;
            font-size: 0.8rem;
            width: 36px;
            text-align: center;
        }

        .col-symbol {
            font-weight: 700;
            color: #38bdf8;
            white-space: nowrap;
        }

        .col-company .company-name {
            color: #e2e8f0;
            margin-bottom: 4px;
        }

        .col-company .topics {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 4px;
        }

        .topic-tag {
            background: #1e3a5f;
            color: #7dd3fc;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 0.72rem;
            white-space: nowrap;
        }

        .col-posts {
            text-align: right;
            font-variant-numeric: tabular-nums;
            color: #e2e8f0;
        }

        .col-sentiment {
            text-align: right;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
        }

        .sent-positive { color: #4ade80; }
        .sent-neutral  { color: #fbbf24; }
        .sent-negative { color: #f87171; }
        .sent-none     { color: #64748b; }

        .col-risk {
            text-align: center;
        }

        .risk-high   { color: #f87171; font-weight: 600; }
        .risk-medium { color: #fbbf24; }
        .risk-low    { color: #4ade80; }

        .col-price, .col-change {
            text-align: right;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
        }

        .positive { color: #4ade80; }
        .negative { color: #f87171; }

        .col-status { text-align: center; white-space: nowrap; }

        .badge {
            display: inline-block;
            font-size: 0.75rem;
            padding: 2px 7px;
            border-radius: 10px;
        }

        .badge-new      { background: #14532d; color: #86efac; }
        .badge-existing { background: #1e293b; color: #94a3b8; }
        .badge-dropped  { background: #450a0a; color: #fca5a5; }

        .detail-row td {
            background: #0d1f35;
            padding: 12px 16px;
        }

        .detail-content {
            font-size: 0.85rem;
            color: #94a3b8;
        }

        .detail-content strong {
            color: #cbd5e1;
        }

        .empty-msg {
            text-align: center;
            color: #64748b;
            padding: 40px;
        }

        .summary-bar {
            display: flex;
            gap: 20px;
            margin-bottom: 16px;
            font-size: 0.85rem;
            color: #94a3b8;
            flex-wrap: wrap;
        }

        .summary-bar span strong {
            color: #e2e8f0;
        }

        .row-clickable { cursor: pointer; }
    </style>
</head>
<body>
<div class="bbs-container">
    <div class="bbs-header">
        <h1><a href="index.php">StockTool</a> / BBS Ranking</h1>
        <form class="date-picker-form" method="GET" action="bbs_ranking.php" id="date-form">
            <label for="date-select">Date:</label>
            <?php if ($dates): ?>
                <select name="date" id="date-select" onchange="this.form.submit()">
                    <?php foreach ($dates as $d): ?>
                        <option value="<?= htmlspecialchars($d) ?>"
                            <?= ($d === $selected_date) ? 'selected' : '' ?>>
                            <?= htmlspecialchars($d) ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            <?php else: ?>
                <input type="date" name="date" id="date-select"
                       value="<?= htmlspecialchars($selected_date) ?>"
                       max="<?= date('Y-m-d') ?>"
                       onchange="this.form.submit()"
                       style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:6px 10px;">
            <?php endif; ?>
        </form>
    </div>

    <?php if ($error): ?>
        <p class="error"><?= htmlspecialchars($error) ?></p>
    <?php elseif (empty($rankings)): ?>
        <p class="empty-msg">No BBS ranking data found for <?= htmlspecialchars($selected_date) ?>.</p>
    <?php else: ?>
        <?php
            $total = count($rankings);
            $new_count = count(array_filter($rankings, fn($r) => $r['status'] === 'new'));
            $dropped_count = count(array_filter($rankings, fn($r) => $r['status'] === 'dropped'));
            $analyzed = count(array_filter($rankings, fn($r) => $r['sentiment_score'] !== null));
        ?>
        <div class="summary-bar">
            <span>Total: <strong><?= $total ?></strong></span>
            <span>New: <strong style="color:#4ade80"><?= $new_count ?></strong></span>
            <span>Dropped: <strong style="color:#f87171"><?= $dropped_count ?></strong></span>
            <span>Analyzed: <strong style="color:#38bdf8"><?= $analyzed ?></strong></span>
        </div>

        <table class="bbs-table" id="bbs-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th>Company / Topics</th>
                    <th class="right">Posts</th>
                    <th class="right">Sentiment</th>
                    <th>Risk</th>
                    <th class="right">Price</th>
                    <th class="right">Change</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($rankings as $i => $r): ?>
                    <?php
                        $sym    = htmlspecialchars($r['symbol']);
                        $up     = ($r['change'] ?? 0) >= 0;
                        $cls    = $up ? 'positive' : 'negative';
                        $sign   = $up ? '+' : '';
                        $has_s  = $r['sentiment_score'] !== null;
                        $s_score = (float)($r['sentiment_score'] ?? 0);
                        $row_id = 'row-' . $i;
                        $detail_id = 'detail-' . $i;
                        $topics = $r['key_topics'] ?? [];
                    ?>
                    <tr class="row-clickable" id="<?= $row_id ?>"
                        onclick="toggleDetail(<?= $i ?>)">
                        <td class="col-rank"><?= $i + 1 ?></td>
                        <td class="col-symbol"><?= $sym ?></td>
                        <td class="col-company">
                            <div class="company-name"><?= htmlspecialchars($r['company_name']) ?></div>
                            <?php if ($topics): ?>
                                <div class="topics">
                                    <?php foreach ($topics as $t): ?>
                                        <span class="topic-tag"><?= htmlspecialchars($t) ?></span>
                                    <?php endforeach; ?>
                                </div>
                            <?php endif; ?>
                        </td>
                        <td class="col-posts"><?= $r['post_count'] !== null ? number_format((int)$r['post_count']) : '—' ?></td>
                        <td class="col-sentiment <?= $has_s ? sentiment_class($s_score) : 'sent-none' ?>">
                            <?= $has_s ? sentiment_label($s_score) : '—' ?>
                        </td>
                        <td class="col-risk <?= $r['risk_level'] ? risk_class($r['risk_level']) : '' ?>">
                            <?= $r['risk_level'] ? htmlspecialchars(ucfirst($r['risk_level'])) : '—' ?>
                        </td>
                        <td class="col-price">
                            <?= $r['price'] !== null ? number_format((float)$r['price'], 2) : '—' ?>
                        </td>
                        <td class="col-change <?= $r['change'] !== null ? $cls : '' ?>">
                            <?php if ($r['change'] !== null && $r['change_percent'] !== null): ?>
                                <?= $sign . number_format((float)$r['change'], 2) ?>
                                <br><small><?= $sign . number_format((float)$r['change_percent'], 2) ?>%</small>
                            <?php else: ?>
                                —
                            <?php endif; ?>
                        </td>
                        <td class="col-status"><?= status_badge($r['status']) ?></td>
                    </tr>
                    <tr class="detail-row" id="<?= $detail_id ?>" style="display:none">
                        <td colspan="9">
                            <div class="detail-content">
                                <?php if ($has_s): ?>
                                    <strong>Sentiment Score:</strong>
                                    <span class="<?= sentiment_class($s_score) ?>"><?= number_format($s_score, 4) ?></span>
                                    &nbsp;&nbsp;
                                    <strong>Risk:</strong>
                                    <span class="<?= risk_class($r['risk_level'] ?? 'medium') ?>"><?= htmlspecialchars(ucfirst($r['risk_level'] ?? 'medium')) ?></span>
                                    <?php if ($topics): ?>
                                        <br><strong>Key Topics:</strong>
                                        <?php foreach ($topics as $t): ?>
                                            <span class="topic-tag"><?= htmlspecialchars($t) ?></span>
                                        <?php endforeach; ?>
                                    <?php endif; ?>
                                <?php else: ?>
                                    Sentiment not yet analyzed for this stock.
                                <?php endif; ?>
                                <br>
                                <strong>Posts scraped:</strong> <?= $r['post_count'] !== null ? (int)$r['post_count'] : 'N/A' ?>
                                &nbsp;&nbsp;
                                <strong>Status:</strong> <?= htmlspecialchars($r['status']) ?>
                            </div>
                        </td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    <?php endif; ?>
</div>
<script>
function toggleDetail(idx) {
    const detail = document.getElementById('detail-' + idx);
    const row    = document.getElementById('row-' + idx);
    if (!detail) return;
    const open = detail.style.display !== 'none';
    detail.style.display = open ? 'none' : 'table-row';
    row.classList.toggle('row-detail-open', !open);
}
</script>
</body>
</html>
