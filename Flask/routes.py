from flask import Flask, render_template, abort, session, request, flash, url_for
import sqlite3
import subprocess
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select, update, values
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
DATABASE = "study.db"

# in routes.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study.db"
app.secret_key = "tGmesA3v77abYK3Y1UkUMlWJny6KAA"
app.config["GOOGLE_CLIENT_ID"] = "263142839019-j7p2ibefe1sm3vp1434dcr9m86butc3s.apps.googleusercontent.com"
app.config["GOOGLE_CLIENT_SECRET"] = "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"

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
    name : Mapped[str] = mapped_column(String())
    email : Mapped[str] = mapped_column(String())

class Admins(Base):
    __tablename__ = "admins"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    password : Mapped[str] = mapped_column(String())

class Calendar(Base):
    __tablename__ = "calendar"
    id : Mapped[int] = mapped_column(primary_key=True)
    date : Mapped[str] = mapped_column(String())
    student_id : Mapped[int] = mapped_column(ForeignKey("students.id"))
    student : Mapped["Students"] = relationship()


# GENERAL ROUTES
@app.route("/")     
def home():
    return render_template("home.html", title="Home")


# students list for teachers
@app.route("/list")
def list():
    # catch non-teacher accounts
    if not session.get("teacher"):
        abort(401)
    
    students = db.session().execute(select(Students)).scalars()
    return render_template("list.html", title="Student List", students=students)


# attendance/calendar list
@app.route("/calendar")
def calendar():
    # catch non-teacher accounts
    if not session.get("teacher"):
        abort(401)

    students = db.session().execute(select(Calendar)).scalars()
    return render_template("calendar.html", title="Calendar", students=students)


# teacher login page
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
        # set student id and name
        session["teacher"] = user.id
        session["name"] = user.code
        return app.redirect("/")
    else:
        flash("Incorrect password.")
        return app.redirect("/teacher-login")


# student login page
@app.route("/student-login")
def student_login():
    # check if user is already logged in
    if not session.get("student"):
        app.redirect("/")
    # send user to google login
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


# google login functionality
@app.route("/auth/google/callback")
def google_callback():
    # get user information
    token = google.authorize_access_token()
    user = token["userinfo"]

    email = user["email"]
    name = user["name"]

    # check if email is from Burnside
    if not email.endswith("@burnside.school.nz"):
        flash("Please use your school Google account.")
        return app.redirect("/student-login")

    # get student based on email
    student = db.session.execute(
        select(Students).where(Students.email == email)
    ).scalar_one_or_none()

    # check if student exists
    if student is None:
        flash("No student account found.")
        return app.redirect("/student-login")

    session["student"] = student.code
    return app.redirect("/")


# removes student/teacher sessions
@app.route("/sign-out")
def sign_out():
    session.pop("teacher", None)
    session.pop("student", None)
    session.pop("name", None)
    return app.redirect("/")


# student-end attendance
@app.route("/check-in")
def check_in():
    double_counter = False
    current_date = date.today()

    # catch users that are not logged in
    if "student" not in session or not session["student"]:
            abort(401)

    # check if user already checked in
    attendance = db.session().execute(
        select(Calendar).
        where(Calendar.student_id == session["student"]).
        where(Calendar.date == current_date)
        ).one_or_none()

    # check if user has already checked in
    if attendance:
        double_counter = True

    return render_template("check-in.html", title="Check-in", double_counter=double_counter)


@app.route("/check-register", methods=["GET", "POST"])
def checkinregister():
    wifi = subprocess.check_output(['netsh', 'WLAN', 'show', 'interfaces'])
    data = wifi.decode('utf-8')
    network_name = str()
    current_date = date.today()
    user_id = session["student"]

    # extract wifi network name (SSID)
    for line in data.split('\n'):
        if 'SSID' in line:
            network_name = line.split(':')[1].strip()
            flash(f"Connected to: {network_name}")
            break
    
    # check if network name was extracted
    if not network_name:
        flash("Not connected to any network.")

    db.session().add(Calendar(date=current_date, student_id=user_id))
    db.session().commit()
    
    return app.redirect("/check-in")


# ERROR HANDLING
@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", title="Page Not Found", error=error), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template("error.html", title="Internal Server Error", error=error), 500

@app.errorhandler(401)
def session_not_found(error):
    return render_template("error.html", title="Unauthorised", error=error), 401


if __name__ == "__main__":
    app.run(debug=True)
