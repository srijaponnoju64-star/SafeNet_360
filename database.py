"""
database.py
-----------
Handles SQLite database initialization and seeding.
Call init_db() once at application startup.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = "womens_safety.db"


def get_db():
    """Return a database connection with timeout to avoid locking errors."""
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables and seed default data."""
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    # Set WAL mode once — allows concurrent reads without locking
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ── Users table ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name         TEXT NOT NULL,
            username          TEXT UNIQUE NOT NULL,
            email             TEXT UNIQUE NOT NULL,
            phone             TEXT NOT NULL,
            address           TEXT,
            age               INTEGER,
            gender            TEXT,
            occupation        TEXT,
            emergency_contact TEXT,
            password_hash     TEXT NOT NULL,
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Staff table ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name       TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            phone           TEXT NOT NULL,
            age             INTEGER,
            gender          TEXT,
            address         TEXT,
            occupation      TEXT,
            aadhar_number   TEXT,
            id_proof_path   TEXT,
            experience      TEXT,
            password_hash   TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Admin table ───────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # ── Complaints table ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id         TEXT UNIQUE NOT NULL,
            user_id          INTEGER NOT NULL,
            type             TEXT,
            description      TEXT,
            incident_details TEXT,
            num_people       INTEGER DEFAULT 0,
            witness          TEXT DEFAULT 'No',
            witness_desc     TEXT,
            date_of_incident TEXT,
            media_path       TEXT,
            latitude         REAL,
            longitude        REAL,
            priority         TEXT DEFAULT 'LOW',
            status           TEXT DEFAULT 'Pending',
            assigned_staff_id INTEGER,
            is_sos           INTEGER DEFAULT 0,
            is_suspicious    INTEGER DEFAULT 0,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)          REFERENCES users(id),
            FOREIGN KEY (assigned_staff_id) REFERENCES staff(id)
        )
    """)

    # ── Locations table ───────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            latitude  REAL,
            longitude REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # ── Seed admin ────────────────────────────────────────────────────────────
    existing_admin = c.execute("SELECT id FROM admin WHERE email = 'admin@safety.com'").fetchone()
    if not existing_admin:
        c.execute(
            "INSERT INTO admin (username, email, password_hash) VALUES (?, ?, ?)",
            ("admin", "admin@safety.com", generate_password_hash("Admin@123"))
        )

    # ── Seed demo user ────────────────────────────────────────────────────────
    existing_user = c.execute("SELECT id FROM users WHERE email = 'demo@user.com'").fetchone()
    if not existing_user:
        c.execute("""
            INSERT INTO users
            (full_name, username, email, phone, address, age, gender,
             occupation, emergency_contact, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Demo User", "demouser", "demo@user.com",
            "9876543210", "123 Main Street, Chennai", 25,
            "Female", "Student", "9999988888",
            generate_password_hash("User@123")
        ))

    # ── Seed demo staff (auto-approved) ───────────────────────────────────────
    existing_staff = c.execute("SELECT id FROM staff WHERE email = 'staff@safety.com'").fetchone()
    if not existing_staff:
        c.execute("""
            INSERT INTO staff
            (full_name, email, phone, age, gender, address, occupation,
             aadhar_number, experience, password_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Demo Staff", "staff@safety.com", "9123456789", 30,
            "Male", "456 Police Lane, Chennai", "Police Officer",
            "1234-5678-9012", "5 years in law enforcement",
            generate_password_hash("Staff@123"), "approved"
        ))

    conn.commit()
    conn.close()
    print("[DB] Database initialized and seeded successfully.")
