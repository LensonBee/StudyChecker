from flask import Flask, render_template, abort, session
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select

app = Flask(__name__)
DATABASE = "study.db"

# in routes.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///c:/2026/StudyChecker/instance/study.db"
db = SQLAlchemy(app)
app.secret_key = "tGmesA3v77abYK3Y1UkUMlWJny6KAA"

class Base(DeclarativeBase):
    pass

class Students(Base):
    __tablename__ = "students"
    id : Mapped[int] = mapped_column(primary_key=True)
    password : Mapped[str] = mapped_column(String())
    form : Mapped[str] = mapped_column(String())


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


@app.route("/student-login")
def student_login():
    if "student" not in session:  # instantiate session
        session["student"] = False

    if session.get("student"):
        return app.redirect("/")

    return render_template("student-login.html", title="Student Login")


if __name__ == "__main__":
    app.run(debug=True)
