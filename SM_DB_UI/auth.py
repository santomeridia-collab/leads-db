from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from db import get_db_cursor  # import from our db module

auth_bp = Blueprint('auth', __name__)
login_manager = LoginManager()

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    with get_db_cursor() as cur:
        cur.execute("SELECT id, username FROM business_db.users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return User(id=user_data[0], username=user_data[1])
    return None

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        with get_db_cursor() as cur:
            cur.execute("SELECT id, password_hash FROM business_db.users WHERE username = %s", (username,))
            user_data = cur.fetchone()
            if user_data and check_password_hash(user_data[1], password):
                user = User(id=user_data[0], username=username)
                login_user(user)
                flash("Logged in successfully.")
                # Redirect to the page the user wanted, or home
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for("home"))
        flash("Invalid username or password.")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("auth.login"))