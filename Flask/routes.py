from flask import Flask, render_template, abort, session, request
import sqlite3
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
    password : Mapped[str] = mapped_column(String())


class Admins(Base):
    __tablename__ = "admins"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    password : Mapped[str] = mapped_column(String())


# GENERAL ROUTES
@app.route("/")
def home():
    return render_template("home.html", title="Home")


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
        return app.redirect("/teacher-login")
    
    if check_password_hash(user.password, password):
        session["teacher"] = True
        return app.redirect("/")
    else:
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
        return app.redirect("/student-login")
    
    if check_password_hash(user.password, password):
        session["student"] = True
        return app.redirect("/")
    else:
        return app.redirect("/student-login")


@app.route("/signout")
def sign_out():
    if session["teacher"]:
        session["teacher"] = False
    if session["student"]:
        session["student"] = False

    return app.redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
