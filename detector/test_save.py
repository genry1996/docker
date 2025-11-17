from save_anomaly import save_anomaly

anomaly = {
    "match_id": 12001,
    "bookmaker": "22bet",
    "type": "ODDS_DROP",
    "severity": "HIGH",

    "market": {
        "category": "Asian Handicap",
        "subtype": "Home",
        "line_before": -6,
        "line_after": -6
    },

    "odds": {
        "before": 1.96,
        "after": 1.54,
        "diff_abs": -0.42,
        "diff_pct": -21.4
    },

    "status": {
        "market_removed": False,
        "match_removed": False,
        "line_removed": False,
        "line_added": False
    }
}

save_anomaly(anomaly)
