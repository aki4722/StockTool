CREATE DATABASE IF NOT EXISTS stocktool_bbs
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE stocktool_bbs;

CREATE TABLE IF NOT EXISTS bbs_rankings (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    date         DATE         NOT NULL,
    symbol       VARCHAR(20)  NOT NULL,
    company_name VARCHAR(255),
    post_count   INT,
    status       ENUM('new', 'existing', 'dropped'),
    price        DECIMAL(12,2),
    `change`     DECIMAL(12,2),
    change_percent DECIMAL(8,4),
    INDEX idx_date (date),
    UNIQUE KEY uk_date_symbol (date, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bbs_posts (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    ranking_id   INT,
    symbol       VARCHAR(20),
    post_content TEXT,
    created_at   DATETIME,
    INDEX idx_symbol (symbol),
    CONSTRAINT fk_ranking FOREIGN KEY (ranking_id)
        REFERENCES bbs_rankings(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bbs_sentiment (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    symbol          VARCHAR(20)  NOT NULL,
    date            DATE         NOT NULL,
    sentiment_score FLOAT,
    key_topics      TEXT,
    risk_level      ENUM('low', 'medium', 'high'),
    analyzed_at     DATETIME,
    price           DECIMAL(12,2),
    `change`        DECIMAL(12,2),
    change_percent  DECIMAL(8,4),
    UNIQUE KEY uk_symbol_date (symbol, date),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
