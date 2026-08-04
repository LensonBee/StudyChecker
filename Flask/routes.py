from flask import Flask, render_template, abort, session, request, flash
import sqlite3
import subprocess
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select, update, values
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date

app = Flask(__name__)
DATABASE = "study.db"

# in routes.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study.db"
db = SQLAlchemy(app)
app.secret_key = "tGmesA3v77abYK3Y1UkUMlWJny6KAA"

class Base(DeclarativeBase):
    pass

class Students(Base):
    __tablename__ = "students"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    name : Mapped[str] = mapped_column(String())
    password : Mapped[str] = mapped_column(String())

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
@app.route("/")     # home page
def home():
    return render_template("home.html", title="Home")

@app.route("/list")     # students list for teachers
def list():
    # catch non-teacher account users
    if "teacher" not in session or not session["teacher"]:
        abort(401)
    
    students = db.session().execute(select(Students)).scalars()
    return render_template(
        "list.html",
        title="Student List",
        students=students
    )


@app.route("/teacher-login")    # teacher login page
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


@app.route("/student-login")       # student login page
def student_login():
    if "student" not in session:  # instantiate session
        session["student"] = False

    if session.get("student"):
        return app.redirect("/")

    return render_template("student-login.html", title="Student Login")


@app.route("/student-loginregister", methods=["GET", "POST"])
def studentloginregister():
    code = request.form.get("username")
    password = request.form.get("password")
    if len(code) > 100 or len(password) > 100:
        flash("Too many characters entered.")
        return app.redirect("/student-login")

    user = db.session().execute(select(Students).where(Students.code == code)).scalar_one_or_none()
    if not user:
        flash("User does not exist.")
        return app.redirect("/student-login")
    
    if check_password_hash(user.password, password):
        # set student id and name
        session["student"] = user.id
        session["name"] = user.name
        return app.redirect("/")
    else:
        flash("Incorrect password.")
        return app.redirect("/student-login")


@app.route("/sign-out")     # removes student/teacher sessions
def sign_out():
    session.pop("teacher", None)
    session.pop("student", None)
    session.pop("name", None)
    return app.redirect("/")


@app.route("/check-in")     # check-in for students
def check_in():
    if "student" not in session or not session["student"]:
            abort(401)

    return render_template("check-in.html", title="Check-in")


@app.route("/check-register", methods=["GET", "POST"])
def checkinregister():
    wifi = subprocess.check_output(['netsh', 'WLAN', 'show', 'interfaces'])
    data = wifi.decode('utf-8')
    network_name = str()
    current_date = date.today()
    user_id = session["student"]
    # Extract WiFi network name (SSID)
    for line in data.split('\n'):
        if 'SSID' in line:
            network_name = line.split(':')[1].strip()
            flash(f"Connected to: {network_name}")
            break
    
    # Check if network name was extracted
    if not network_name:
        flash("Not connected to any network.")

    db.session().add(Calendar(date=current_date, student_id=user_id))
    db.session().commit()
    
    return app.redirect("/check-in")


# error handling
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
