"""
app.py
------
Main Flask application for the Smart Women Safety and Response System.
Run with: python app.py
Runs on:  http://127.0.0.1:5000
"""

import os
import sys
import uuid
import random
from datetime import datetime
from functools import wraps

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_db, init_db, DB_PATH
from ai_features import detect_priority, check_suspicious

# ── App Configuration ────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "wss_secret_2024_hackathon"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "avi"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_track_id():
    return "TRK" + str(uuid.uuid4())[:8].upper()


def auto_assign_staff(db, complaint_id):
    """Assigns the complaint to the least busy approved staff member."""
    staff = db.execute("""
        SELECT s.id, COUNT(c.id) as assigned_count
        FROM staff s
        LEFT JOIN complaints c ON s.id = c.assigned_staff_id AND c.status IN ('Assigned', 'Accepted', 'In Progress')
        WHERE s.status = 'approved'
        GROUP BY s.id
        ORDER BY assigned_count ASC
        LIMIT 1
    """).fetchone()

    if staff:
        db.execute(
            "UPDATE complaints SET assigned_staff_id = ?, status = 'Assigned' WHERE id = ?",
            (staff["id"], complaint_id)
        )
        return staff["id"]
    return None


# ── Auth Decorators ──────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session and "staff_id" not in session and "admin_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Access denied. Please login as a user.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "staff_id" not in session:
            flash("Access denied. Please login as staff.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            flash("Access denied. Admin login required.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ── Landing Page ─────────────────────────────────────────────────────────────
@app.route("/")
def landing():
    return render_template("landing.html")


# ── Registration ─────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register_select():
    return render_template("register_select.html")


@app.route("/register/user", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        full_name         = request.form.get("full_name", "").strip()
        username          = request.form.get("username", "").strip()
        email             = request.form.get("email", "").strip()
        phone             = request.form.get("phone", "").strip()
        address           = request.form.get("address", "").strip()
        age               = request.form.get("age", "").strip()
        gender            = request.form.get("gender", "").strip()
        occupation        = request.form.get("occupation", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()
        password          = request.form.get("password", "")
        confirm_password  = request.form.get("confirm_password", "")

        # Server-side validation
        errors = []
        if not all([full_name, username, email, phone, address, age, gender, occupation, emergency_contact, password]):
            errors.append("All fields are required.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if len(phone) != 10 or not phone.isdigit():
            errors.append("Phone number must be exactly 10 digits.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register_user.html")

        db = get_db()
        # Check duplicates
        existing = db.execute(
            "SELECT id FROM users WHERE email = ? OR username = ?", (email, username)
        ).fetchone()
        if existing:
            flash("Email or username already registered.", "danger")
            db.close()
            return render_template("register_user.html")

        db.execute("""
            INSERT INTO users
            (full_name, username, email, phone, address, age, gender,
             occupation, emergency_contact, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (full_name, username, email, phone, address, int(age), gender,
              occupation, emergency_contact, generate_password_hash(password)))
        db.commit()
        db.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register_user.html")


@app.route("/register/staff", methods=["GET", "POST"])
def register_staff():
    if request.method == "POST":
        full_name     = request.form.get("full_name", "").strip()
        email         = request.form.get("email", "").strip()
        phone         = request.form.get("phone", "").strip()
        age           = request.form.get("age", "").strip()
        gender        = request.form.get("gender", "").strip()
        address       = request.form.get("address", "").strip()
        occupation    = request.form.get("occupation", "").strip()
        aadhar_number = request.form.get("aadhar_number", "").strip()
        experience    = request.form.get("experience", "").strip()
        password      = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not all([full_name, email, phone, age, gender, address, occupation, aadhar_number, password]):
            errors.append("All required fields must be filled.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if len(phone) != 10 or not phone.isdigit():
            errors.append("Phone must be 10 digits.")

        # Handle file upload
        id_proof_path = None
        if "id_proof" in request.files:
            file = request.files["id_proof"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                id_proof_path = unique_name

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register_staff.html")

        db = get_db()
        existing = db.execute("SELECT id FROM staff WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("Email already registered.", "danger")
            db.close()
            return render_template("register_staff.html")

        db.execute("""
            INSERT INTO staff
            (full_name, email, phone, age, gender, address, occupation,
             aadhar_number, id_proof_path, experience, password_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (full_name, email, phone, int(age), gender, address, occupation,
              aadhar_number, id_proof_path, experience, generate_password_hash(password)))
        db.commit()
        db.close()

        flash("Registration submitted! Awaiting admin approval.", "info")
        return redirect(url_for("login"))

    return render_template("register_staff.html")


# ── Login ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        role       = request.form.get("role", "user")

        db = get_db()

        if role == "user":
            user = db.execute(
                "SELECT * FROM users WHERE email = ? OR username = ?",
                (identifier, identifier)
            ).fetchone()
            db.close()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"]   = user["id"]
                session["user_name"] = user["full_name"]
                session["role"]      = "user"
                return redirect(url_for("dashboard_user"))
            else:
                flash("Invalid credentials. Please try again.", "danger")

        elif role == "staff":
            staff = db.execute(
                "SELECT * FROM staff WHERE email = ?", (identifier,)
            ).fetchone()
            db.close()

            if staff and check_password_hash(staff["password_hash"], password):
                session.clear()
                session["staff_id"]   = staff["id"]
                session["staff_name"] = staff["full_name"]
                session["staff_status"] = staff["status"]
                session["role"]       = "staff"
                return redirect(url_for("dashboard_staff"))
            else:
                flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("landing"))


# ── Admin Login ───────────────────────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        admin = db.execute("SELECT * FROM admin WHERE email = ?", (email,)).fetchone()
        db.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"]   = admin["id"]
            session["admin_name"] = admin["username"]
            session["role"]       = "admin"
            return redirect(url_for("dashboard_admin"))
        else:
            flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


# ── User Dashboard ────────────────────────────────────────────────────────────
@app.route("/dashboard/user")
@user_required
def dashboard_user():
    db = get_db()
    complaints = db.execute(
        "SELECT * FROM complaints WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    db.close()
    return render_template("dashboard_user.html",
                           user_name=session["user_name"],
                           complaints=complaints)


# ── SOS / Emergency Alert ─────────────────────────────────────────────────────
@app.route("/sos", methods=["POST"])
@user_required
def sos():
    user_id  = session["user_id"]
    track_id = generate_track_id()
    lat      = round(random.uniform(10.0, 13.0), 6)
    lon      = round(random.uniform(77.0, 80.0), 6)

    db = get_db()
    db.execute("""
        INSERT INTO complaints
        (track_id, user_id, type, description, priority, status, latitude, longitude, is_sos)
        VALUES (?, ?, 'SOS', 'EMERGENCY SOS ALERT', 'HIGH', 'Pending', ?, ?, 1)
    """, (track_id, user_id, lat, lon))
    
    complaint_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Also log location
    db.execute(
        "INSERT INTO locations (user_id, latitude, longitude) VALUES (?, ?, ?)",
        (user_id, lat, lon)
    )
    
    # Auto-assign staff
    auto_assign_staff(db, complaint_id)
    
    db.commit()
    db.close()

    return jsonify({"success": True, "track_id": track_id,
                    "message": f"Emergency alert sent! Track ID: {track_id}"})


# ── Share Location ────────────────────────────────────────────────────────────
@app.route("/share-location", methods=["POST"])
@user_required
def share_location():
    user_id = session["user_id"]
    lat = round(random.uniform(10.0, 13.0), 6)
    lon = round(random.uniform(77.0, 80.0), 6)

    db = get_db()
    db.execute(
        "INSERT INTO locations (user_id, latitude, longitude) VALUES (?, ?, ?)",
        (user_id, lat, lon)
    )
    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "lat": lat, "lon": lon,
        "message": f"Location shared successfully! ({lat}, {lon})"
    })


# ── Report Incident ───────────────────────────────────────────────────────────
@app.route("/report", methods=["GET", "POST"])
@user_required
def report_incident():
    if request.method == "POST":
        user_id          = session["user_id"]
        issue_type       = request.form.get("issue_type", "Other")
        description      = request.form.get("description", "")
        incident_details = request.form.get("incident_details", "")
        num_people       = request.form.get("num_people", 0)
        witness          = request.form.get("witness", "No")
        witness_desc     = request.form.get("witness_desc", "")
        date_of_incident = request.form.get("date_of_incident", "")

        if not description:
            flash("Description is required.", "danger")
            return render_template("report_incident.html")

        # AI priority detection
        priority = detect_priority(description + " " + incident_details)

        # Suspicious check
        is_suspicious = 1 if check_suspicious(user_id, DB_PATH) else 0

        # Handle media upload
        media_path = None
        if "media" in request.files:
            file = request.files["media"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                media_path = unique_name

        track_id = generate_track_id()
        lat = round(random.uniform(10.0, 13.0), 6)
        lon = round(random.uniform(77.0, 80.0), 6)

        db = get_db()
        db.execute("""
            INSERT INTO complaints
            (track_id, user_id, type, description, incident_details, num_people,
             witness, witness_desc, date_of_incident, media_path, latitude, longitude,
             priority, status, is_suspicious)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (track_id, user_id, issue_type, description, incident_details,
              int(num_people) if str(num_people).isdigit() else 0,
              witness, witness_desc, date_of_incident, media_path,
              lat, lon, priority, is_suspicious))
              
        complaint_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Auto-assign staff
        auto_assign_staff(db, complaint_id)
        
        db.commit()
        db.close()

        flash(f"Complaint submitted successfully! Your Track ID is: {track_id}", "success")
        return redirect(url_for("dashboard_user"))

    return render_template("report_incident.html")


# ── Track Complaint ───────────────────────────────────────────────────────────
@app.route("/track", methods=["GET", "POST"])
def track_complaint():
    complaint = None
    staff_name = None

    if request.method == "POST":
        track_id = request.form.get("track_id", "").strip()
        if not track_id:
            flash("Please enter a Track ID.", "warning")
        else:
            db = get_db()
            complaint = db.execute(
                "SELECT * FROM complaints WHERE track_id = ?", (track_id,)
            ).fetchone()

            if complaint and complaint["assigned_staff_id"]:
                staff = db.execute(
                    "SELECT full_name FROM staff WHERE id = ?",
                    (complaint["assigned_staff_id"],)
                ).fetchone()
                if staff:
                    staff_name = staff["full_name"]
            db.close()

            if not complaint:
                flash("No complaint found with that Track ID.", "danger")

    return render_template("track_complaint.html",
                           complaint=complaint, staff_name=staff_name)


# ── Staff Dashboard ───────────────────────────────────────────────────────────
@app.route("/dashboard/staff")
@staff_required
def dashboard_staff():
    staff_id     = session["staff_id"]
    staff_status = session.get("staff_status", "pending")

    db = get_db()
    staff = db.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    session["staff_status"] = staff["status"]  # Refresh from DB

    complaints = []
    if staff["status"] == "approved":
        complaints = db.execute("""
            SELECT c.*, u.full_name as user_name, u.phone as user_phone
            FROM complaints c
            JOIN users u ON c.user_id = u.id
            WHERE c.assigned_staff_id = ?
            ORDER BY c.created_at DESC
        """, (staff_id,)).fetchall()
    db.close()

    return render_template("dashboard_staff.html",
                           staff=staff, complaints=complaints)


@app.route("/staff/update-status", methods=["POST"])
@staff_required
def update_complaint_status():
    complaint_id = request.form.get("complaint_id")
    new_status   = request.form.get("status")

    valid_statuses = ["Accepted", "In Progress", "Completed"]
    if new_status not in valid_statuses:
        flash("Invalid status.", "danger")
        return redirect(url_for("dashboard_staff"))

    db = get_db()
    db.execute(
        "UPDATE complaints SET status = ? WHERE id = ? AND assigned_staff_id = ?",
        (new_status, complaint_id, session["staff_id"])
    )
    db.commit()
    db.close()

    flash(f"Complaint status updated to '{new_status}'.", "success")
    return redirect(url_for("dashboard_staff"))


# ── Admin Dashboard ───────────────────────────────────────────────────────────
@app.route("/dashboard/admin")
@admin_required
def dashboard_admin():
    db = get_db()

    complaints = db.execute("""
        SELECT c.*, u.full_name as user_name, u.phone as user_phone,
               u.email as user_email, u.address as user_address,
               s.full_name as staff_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN staff s ON c.assigned_staff_id = s.id
        ORDER BY c.created_at DESC
    """).fetchall()

    staff_list = db.execute(
        "SELECT * FROM staff ORDER BY created_at DESC"
    ).fetchall()

    approved_staff = db.execute(
        "SELECT * FROM staff WHERE status = 'approved'"
    ).fetchall()

    # Stats
    total_complaints  = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending_complaints = db.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    total_users       = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    pending_staff     = db.execute("SELECT COUNT(*) FROM staff WHERE status='pending'").fetchone()[0]

    users_list = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

    db.close()

    return render_template("dashboard_admin.html",
                           complaints=complaints,
                           staff_list=staff_list,
                           approved_staff=approved_staff,
                           users_list=users_list,
                           stats={
                               "total_complaints":  total_complaints,
                               "pending_complaints": pending_complaints,
                               "total_users":       total_users,
                               "pending_staff":     pending_staff
                           })


@app.route("/admin/assign-staff", methods=["POST"])
@admin_required
def assign_staff():
    complaint_id = request.form.get("complaint_id")
    staff_id     = request.form.get("staff_id", "").strip()

    # Guard: no staff selected from dropdown
    if not staff_id:
        flash("Please select a staff member from the dropdown before clicking assign.", "warning")
        return redirect(url_for("dashboard_admin"))

    db = get_db()
    # Verify selected staff actually exists and is approved
    staff = db.execute(
        "SELECT id FROM staff WHERE id = ? AND status = 'approved'", (staff_id,)
    ).fetchone()

    if not staff:
        db.close()
        flash("Selected staff member is not approved or does not exist.", "danger")
        return redirect(url_for("dashboard_admin"))

    db.execute(
        "UPDATE complaints SET assigned_staff_id = ?, status = 'Assigned' WHERE id = ?",
        (staff_id, complaint_id)
    )
    db.commit()
    db.close()

    flash("Staff assigned successfully.", "success")
    return redirect(url_for("dashboard_admin"))


@app.route("/admin/approve-staff", methods=["POST"])
@admin_required
def approve_staff():
    staff_id = request.form.get("staff_id")
    action   = request.form.get("action")  # 'approve' or 'reject'

    new_status = "approved" if action == "approve" else "rejected"
    db = get_db()
    db.execute("UPDATE staff SET status = ? WHERE id = ?", (new_status, staff_id))
    db.commit()
    db.close()

    flash(f"Staff {'approved' if action == 'approve' else 'rejected'} successfully.", "success")
    return redirect(url_for("dashboard_admin"))


@app.route("/admin/change-status", methods=["POST"])
@admin_required
def admin_change_status():
    complaint_id = request.form.get("complaint_id")
    new_status   = request.form.get("status")

    db = get_db()
    db.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, complaint_id))
    db.commit()
    db.close()

    flash("Complaint status updated.", "success")
    return redirect(url_for("dashboard_admin"))


# ── API Routes (AJAX / Upgrades) ──────────────────────────────────────────────
@app.route("/api/complaints/status")
@user_required
def api_complaints_status():
    """Poll for complaint status changes on the user dashboard."""
    db = get_db()
    complaints = db.execute(
        "SELECT id, track_id, status FROM complaints WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()
    db.close()
    return jsonify([dict(c) for c in complaints])


@app.route("/api/admin/chart-data")
@admin_required
def api_chart_data():
    """Returns aggregated data for Chart.js in admin dashboard."""
    db = get_db()
    
    # Priority distribution
    priority_rows = db.execute(
        "SELECT priority, COUNT(*) as count FROM complaints GROUP BY priority"
    ).fetchall()
    priorities = {r["priority"]: r["count"] for r in priority_rows}
    
    # Type distribution
    type_rows = db.execute(
        "SELECT type, COUNT(*) as count FROM complaints WHERE type IS NOT NULL GROUP BY type"
    ).fetchall()
    types = {r["type"]: r["count"] for r in type_rows}
    
    db.close()
    return jsonify({
        "priorities": priorities,
        "types": types
    })


@app.route("/api/admin/locations")
@admin_required
def api_locations():
    """Returns lat/lons for the Heatmap."""
    db = get_db()
    # Limit to latest 100 locations for performance
    locations = db.execute(
        "SELECT latitude, longitude FROM complaints WHERE latitude IS NOT NULL"
    ).fetchall()
    db.close()
    return jsonify([dict(l) for l in locations])


@app.route("/api/complaint/<int:complaint_id>")
@admin_required
def api_complaint_detail(complaint_id):
    """Returns full complaint details for the modal."""
    db = get_db()
    c = db.execute("""
        SELECT c.*, u.full_name as user_name, u.phone as user_phone, u.email as user_email,
               s.full_name as staff_name, s.phone as staff_phone
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN staff s ON c.assigned_staff_id = s.id
        WHERE c.id = ?
    """, (complaint_id,)).fetchone()
    db.close()
    
    if not c:
        return jsonify({"error": "Not found"}), 404
        
    return jsonify(dict(c))



# ── Serve Uploads ─────────────────────────────────────────────────────────────
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("\n" + "="*50)
    print("  Smart Women Safety and Response System")
    print("  Running at: http://127.0.0.1:5000")
    print("="*50)
    print("\n  SAMPLE CREDENTIALS:")
    print("  Admin  -> admin@safety.com   / Admin@123")
    print("  User   -> demo@user.com      / User@123")
    print("  Staff  -> staff@safety.com   / Staff@123")
    print("="*50 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
