from flask import Flask, render_template, abort, session, request, flash, url_for
import sqlite3
import subprocess
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select, update, values
from werkzeug.security import check_password_hash, generate_password_hash
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
DATABASE = "study.db"

# in routes.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study.db"
app.config["GOOGLE_CLIENT_ID"] = "263142839019-j7p2ibefe1sm3vp1434dcr9m86butc3s.apps.googleusercontent.com"
app.config["GOOGLE_CLIENT_SECRET"] = "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"
app.secret_key = "tGmesA3v77abYK3Y1UkUMlWJny6KAA"

db = SQLAlchemy(app)
oauth = OAuth(app)


google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)


class Base(DeclarativeBase):
    pass

class Students(Base):
    __tablename__ = "students"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    name : Mapped[str] = mapped_column(String())
    email : Mapped[str] = mapped_column(String())


class Admins(Base):
    __tablename__ = "admins"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    password : Mapped[str] = mapped_column(String())


# GENERAL ROUTES
@app.route("/")
def home():
    return render_template("home.html", title="Home")


@app.route("/list")
def list():
    students = db.session().execute(select(Students)).scalars()
    return render_template(
        "list.html",
        title="Student List",
        students=students
    )


@app.route("/teacher-login")
def teacher_login():
    if "teacher" not in session:  # instantiate session
        session["teacher"] = False

    if session.get("teacher"):
        return app.redirect("/")

    return render_template("teacher-login.html", title="Teacher Login")


@app.route("/teacher-loginregister", methods=["GET", "POST"])
def teacherloginregister():
    code = request.form.get("username")
    password = request.form.get("password")
    # check for character limit
    if len(code) > 100 or len(password) > 100:
        flash("Too many characters entered.")
        return app.redirect("/teacher-login")

    user = db.session().execute(select(Admins).where(Admins.code == code)).scalar_one_or_none()
    if not user:
        flash("User does not exist.")
        return app.redirect("/teacher-login")
    
    if check_password_hash(user.password, password):
        session["teacher"] = user.code
        return app.redirect("/")
    else:
        flash("Incorrect password.")
        return app.redirect("/teacher-login")


@app.route("/student-login")
@app.route("/student-login")
def student_login():
    redirect_uri = url_for("google_callback", _external=True)
    print(redirect_uri)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user = token["userinfo"]

    email = user["email"]
    name = user["name"]

    # check if email is from burnside
    if not email.endswith("@burnside.school.nz"):
        flash("Please use your school Google account.")
        return app.redirect("/student-login")

    student = db.session.execute(
        select(Students).where(Students.email == email)
    ).scalar_one_or_none()

    if student is None:
        flash("No student account found.")
        return app.redirect("/student-login")

    session["student"] = student.code

    return app.redirect("/")


@app.route("/sign-out")
def sign_out():
    session.pop("teacher", None)
    session.pop("student", None)
    return app.redirect("/")


@app.route("/check-in")
def check_in():
    return render_template("check-in.html", title="Check-in")


@app.route("/check-register", methods=["GET", "POST"])
def checkinregister():
    wifi = subprocess.check_output(['netsh', 'WLAN', 'show', 'interfaces'])
    data = wifi.decode('utf-8')
    network_name = str()
    
    # Extract WiFi network name (SSID)
    for line in data.split('\n'):
        if 'SSID' in line:
            network_name = line.split(':')[1].strip()
            if network_name == "BHS_BYOD_alt":      # Connected to school Wifi
                flash(f"Logged into: {network_name}")
            else:                                   # Connected but not correct network
                flash("Please connect to school Wifi")
            break
    
    # Check if network name was extracted
    if not network_name:
        flash("Not connected to any network.")


    db.session().execute(update(Students).where(Students.code == session["student"]).values(check=1))
    return app.redirect("/check-in")


# error handling
@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", title="Error", error=error), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template("error.html", title="Error", error=error), 500


if __name__ == "__main__":
    app.run(debug=True)
