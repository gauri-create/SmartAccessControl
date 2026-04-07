from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "sentricore_key"

DB = "backend/database/attendance.db"


# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


# ---------------- ACCESS CONTROL ----------------
def has_access(role, allowed_roles):
    return role in allowed_roles


# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND status='active'",
            (username, password)
        )

        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]

            role = user["role"]

            if role == "security":
                return redirect("/logs")
            elif role == "hr":
                return redirect("/hr")
            elif role == "owner":
                return redirect("/owner")
            else:
                return "No access assigned to this role"

        return "Invalid Credentials"

    return render_template("login.html")


# ---------------- HR PANEL ----------------
@app.route("/hr")
def hr():
    role = session.get("role")

    if not has_access(role, ["hr", "owner"]):
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    conn.close()

    return render_template("hr.html", users=users)


# ---------------- LOGS ----------------
@app.route("/logs")
def logs():
    role = session.get("role")

    if not has_access(role, ["security", "owner"]):
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM logs ORDER BY id DESC")
    logs = cur.fetchall()

    conn.close()

    return render_template("index_logs.html", logs=logs)


# ---------------- OWNER ----------------
@app.route("/owner")
def owner():
    role = session.get("role")

    if role != "owner":
        return "Access Denied"

    return render_template("owner.html")


# ---------------- REGISTER USER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    role = session.get("role")

    if not has_access(role, ["hr", "owner"]):
        return "Access Denied"

    if request.method == "POST":
        username = request.form["username"].strip().lower()
        name = request.form["name"].strip()
        password = request.form["password"]
        user_role = request.form["role"].strip().lower()

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO users (username, name, password, role, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (username, name, password, user_role)
            )
            conn.commit()

        except sqlite3.IntegrityError:
            return "Username already exists"

        finally:
            conn.close()

        return redirect("/hr")

    return render_template("register.html")


# ---------------- TOGGLE USER STATUS ----------------
@app.route("/toggle/<int:user_id>")
def toggle(user_id):
    role = session.get("role")

    if role != "owner":
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role, status FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return "User not found"

    if user["role"] == "owner":
        conn.close()
        return "Cannot modify owner"

    new_status = "inactive" if user["status"] == "active" else "active"

    cur.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))

    conn.commit()
    conn.close()

    return redirect("/hr")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)