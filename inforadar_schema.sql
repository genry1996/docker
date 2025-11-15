-- ================================
-- INFORADAR PRO — FULL DATABASE SCHEMA
-- v3.1 (supports C+ anomaly engine)
-- ================================

CREATE TABLE IF NOT EXISTS bookmakers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id BIGINT PRIMARY KEY,
    sport VARCHAR(64) NULL,
    league VARCHAR(128) NULL,
    home_team VARCHAR(128) NOT NULL,
    away_team VARCHAR(128) NOT NULL,
    start_time DATETIME NULL,
    status VARCHAR(32) DEFAULT 'scheduled',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS markets (
    id BIGINT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    bookmaker_id INT NOT NULL,
    market_type VARCHAR(64) NOT NULL,
    line_value VARCHAR(64) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id),
    FOREIGN KEY (bookmaker_id) REFERENCES bookmakers(id),
    KEY idx_match_book (match_id, bookmaker_id)
);

CREATE TABLE IF NOT EXISTS odds (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    market_id BIGINT NOT NULL,
    outcome VARCHAR(32) NOT NULL,
    value DECIMAL(10,3) NOT NULL,
    limit_max DECIMAL(12,2) NULL,
    is_limited TINYINT(1) DEFAULT 0,
    is_blocked TINYINT(1) DEFAULT 0,
    removed_from_line TINYINT(1) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES markets(id),
    KEY idx_market (market_id)
);

CREATE TABLE IF NOT EXISTS odds_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    market_id BIGINT NOT NULL,
    bookmaker_id INT NOT NULL,
    match_id BIGINT NOT NULL,
    outcome VARCHAR(32) NOT NULL,
    value DECIMAL(10,3) NOT NULL,
    limit_max DECIMAL(12,2) NULL,
    is_limited TINYINT(1) DEFAULT 0,
    is_blocked TINYINT(1) DEFAULT 0,
    removed_from_line TINYINT(1) DEFAULT 0,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (market_id) REFERENCES markets(id),
    FOREIGN KEY (bookmaker_id) REFERENCES bookmakers(id),
    FOREIGN KEY (match_id) REFERENCES matches(id),
    KEY idx_match_book (match_id, bookmaker_id),
    KEY idx_time (timestamp)
);

CREATE TABLE IF NOT EXISTS anomalies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    bookmaker_id INT NULL,
    outcome VARCHAR(32) NOT NULL,
    anomaly_type VARCHAR(64) NOT NULL,
    before_odd DECIMAL(10,3) NULL,
    after_odd DECIMAL(10,3) NULL,
    diff_abs DECIMAL(10,3) NULL,
    diff_pct DECIMAL(6,2) NULL,
    before_limit DECIMAL(12,2) NULL,
    after_limit DECIMAL(12,2) NULL,
    window_seconds INT NULL,
    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comment VARCHAR(255) NULL,
    KEY idx_match (match_id),
    KEY idx_match_book (match_id, bookmaker_id),
    KEY idx_type_time (anomaly_type, occurred_at)
);

-- Fill bookmakers
INSERT IGNORE INTO bookmakers (code, name) VALUES
('1xbet', '1xBet'),
('22bet', '22Bet'),
('bet365', 'Bet365'),
('pinnacle', 'Pinnacle'),
('marathon', 'Marathon'),
('melbet', 'Melbet'),
('fonbet', 'Fonbet'),
('sbobet', 'Sbobet'),
('parimatch', 'PariMatch'),
('olimp', 'Olimp'),
('crown', 'Crown'),
('vcbet', 'Vcbet'),
('williamhill', 'William Hill'),
('bwin', 'Bwin'),
('12bet', '12Bet'),
('slotv', 'SlotV'),
('betcity', 'Betcity'),
('tonybet', 'TonyBet'),
('betfair', 'Betfair'),
('leon', 'Леон'),
('winline', 'Винлайн'),
('orbit', 'OrbitExchange'),
('betboom', 'BetBoom'),
('m88', 'M88');
