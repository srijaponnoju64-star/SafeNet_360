"""
ai_features.py
--------------
Simple AI-like features for the Women Safety System.
No external ML libraries needed — pure Python logic.
"""

import sqlite3
from datetime import datetime, timedelta


def detect_priority(description: str) -> str:
    """
    Detect complaint priority based on keywords in description.
    HIGH   → immediate danger words
    MEDIUM → harassment / unsafe words
    LOW    → everything else
    """
    text = description.lower()

    high_keywords = ["help", "danger", "attack", "follow", "followed",
                     "assault", "kidnap", "rape", "kill", "stabbed", "hurt"]
    medium_keywords = ["harassment", "harass", "unsafe", "uncomfortable",
                       "threatening", "threat", "scared", "afraid"]

    for kw in high_keywords:
        if kw in text:
            return "HIGH"
    for kw in medium_keywords:
        if kw in text:
            return "MEDIUM"
    return "LOW"


def check_suspicious(user_id: int, db_path: str) -> bool:
    """
    Returns True if the user has submitted 3 or more complaints
    in the last 10 minutes (suspicious behavior).
    """
    cutoff = datetime.now() - timedelta(minutes=10)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM complaints WHERE user_id = ? AND created_at >= ?",
        (user_id, cutoff_str)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count >= 3
