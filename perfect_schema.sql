-- ============================
-- PERFECT INFORADAR DATABASE
-- ============================

DROP TABLE IF EXISTS anomalies;
DROP TABLE IF EXISTS odds_history;
DROP TABLE IF EXISTS odds;
DROP TABLE IF EXISTS markets;
DROP TABLE IF EXISTS matches;
DROP TABLE IF EXISTS bookmakers;

-- -------------------------
-- 1. МАТЧИ
-- -------------------------
CREATE TABLE matches (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sport VARCHAR(64),
    league VARCHAR(128),
    home_team VARCHAR(128) NOT NULL,
    away_team VARCHAR(128) NOT NULL,
    start_time DATETIME,
    status VARCHAR(32) DEFAULT 'scheduled',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_league (league),
    INDEX idx_start (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -------------------------
-- 2. БУКМЕКЕРЫ
-- -------------------------
CREATE TABLE bookmakers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO bookmakers (code, name) VALUES
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
('betcity', 'BetCity'),
('tonybet', 'TonyBet'),
('betfair', 'Betfair'),
('leon', 'Leon'),
('winline', 'Winline'),
('orbit', 'OrbitExchange'),
('betboom', 'BetBoom'),
('m88', 'M88');


-- -------------------------
-- 3. ТИПЫ РЫНКОВ
-- -------------------------
CREATE TABLE markets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    bookmaker_id INT NOT NULL,
    market_type VARCHAR(64) NOT NULL,
    line_value VARCHAR(64),

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_match_book (match_id, bookmaker_id),
    INDEX idx_market (market_type),

    CONSTRAINT fk_markets_match
        FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,

    CONSTRAINT fk_markets_bookmaker
        FOREIGN KEY (bookmaker_id) REFERENCES bookmakers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -------------------------
-- 4. Текущие коэффициенты
-- -------------------------
CREATE TABLE odds (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    market_id BIGINT NOT NULL,
    outcome VARCHAR(32) NOT NULL,
    value DECIMAL(10,3) NOT NULL,
    limit_max DECIMAL(12,2),
    is_limited TINYINT(1) DEFAULT 0,
    is_blocked TINYINT(1) DEFAULT 0,
    removed_from_line TINYINT(1) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_market_outcome (market_id, outcome),

    CONSTRAINT fk_odds_market
        FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -------------------------
-- 5. История коэффициентов (всё самое важное!)
-- -------------------------
CREATE TABLE odds_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    market_id BIGINT NOT NULL,
    bookmaker_id INT NOT NULL,

    outcome VARCHAR(32) NOT NULL,
    value DECIMAL(10,3) NOT NULL,

    limit_max DECIMAL(12,2),
    is_limited TINYINT(1) DEFAULT 0,
    is_blocked TINYINT(1) DEFAULT 0,
    removed_from_line TINYINT(1) DEFAULT 0,

    timestamp DATETIME NOT NULL,

    INDEX idx_match_book (match_id, bookmaker_id),
    INDEX idx_market_time (market_id, timestamp),
    INDEX idx_time (timestamp),

    CONSTRAINT fk_hist_match
        FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,

    CONSTRAINT fk_hist_market
        FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE,

    CONSTRAINT fk_hist_bookmaker
        FOREIGN KEY (bookmaker_id) REFERENCES bookmakers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- -------------------------
-- 6. Аномалии (как в Inforadar, но лучше)
-- -------------------------
CREATE TABLE anomalies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id BIGINT NOT NULL,
    bookmaker_id INT,
    market_id BIGINT,
    outcome VARCHAR(32) NOT NULL,

    anomaly_type VARCHAR(32) NOT NULL,
    before_odd DECIMAL(10,3),
    after_odd DECIMAL(10,3),
    diff_abs DECIMAL(10,3),
    diff_pct DECIMAL(6,2),

    before_limit DECIMAL(12,2),
    after_limit DECIMAL(12,2),

    window_seconds INT,
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    comment VARCHAR(255),

    INDEX idx_match (match_id),
    INDEX idx_match_book (match_id, bookmaker_id),
    INDEX idx_type_time (anomaly_type, occurred_at),

    CONSTRAINT fk_anom_match FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
    CONSTRAINT fk_anom_book FOREIGN KEY (bookmaker_id) REFERENCES bookmakers(id) ON DELETE SET NULL,
    CONSTRAINT fk_anom_market FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
