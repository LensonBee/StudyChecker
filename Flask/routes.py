from flask import Flask, render_template, abort, session, request, flash
import sqlite3
import subprocess
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select, update, values
from werkzeug.security import check_password_hash, generate_password_hash

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
    check : Mapped[int] = mapped_column(Integer())


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

    user = db.session().execute(select(Students).where(Students.code == code)).scalar_one_or_none()
    if not user:
        flash("User does not exist.")
        return app.redirect("/student-login")
    
    if check_password_hash(user.password, password):
        session["student"] = user.code
        return app.redirect("/")
    else:
        flash("Incorrect password.")
        return app.redirect("/student-login")


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
    
    # Extract WiFi network name (SSID)
    for line in data.split('\n'):
        if 'SSID' in line:
            network_name = line.split(':')[1].strip()
            print(f"Connected to WiFi: {network_name}")
            break

    db.session().execute(update(Students).where(Students.code == session["student"]).values(check=1))
    return app.redirect("/check-in")


if __name__ == "__main__":
    app.run(debug=True)
