from flask import Flask, render_template, abort, session, request, flash, url_for
import sqlite3
import subprocess
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, select, Table, Column, Select, update, values
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from authlib.integrations.flask_client import OAuth
import random
from flask_mail import Mail, Message
import random
import os
import auth
import csv
import io

app = Flask(__name__)
DATABASE = "study.db"

# SQLalchemy setup
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study.db"
app.secret_key = "tGmesA3v77abYK3Y1UkUMlWJny6KAA"

# Google login setup
app.config["GOOGLE_CLIENT_ID"] = "263142839019-j7p2ibefe1sm3vp1434dcr9m86butc3s.apps.googleusercontent.com"
app.config["GOOGLE_CLIENT_SECRET"] = "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"

# Telomeres
db = SQLAlchemy(app)
oauth = OAuth(app)

# Google login
google = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

# Mail setup
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = auth.sender_email
app.config["MAIL_PASSWORD"] = auth.sender_password
app.config["MAIL_DEFAULT_SENDER"] = auth.sender_email

mail = Mail(app)

# Database setup
class Base(DeclarativeBase):
    pass

class Students(Base):
    __tablename__ = "students"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    email : Mapped[str] = mapped_column(String())

class Admins(Base):
    __tablename__ = "admins"
    id : Mapped[int] = mapped_column(primary_key=True)
    code : Mapped[str] = mapped_column(String())
    password : Mapped[str] = mapped_column(String())

class Attendance(Base):
    __tablename__ = "attendance"
    id : Mapped[int] = mapped_column(primary_key=True)
    date : Mapped[str] = mapped_column(String())
    student_id : Mapped[int] = mapped_column(ForeignKey("students.id"))
    student : Mapped["Students"] = relationship()

class Timetables(Base):
    __tablename__ = "timetables"
    id : Mapped[int] = mapped_column(primary_key=True)
    day : Mapped[str] = mapped_column(String())
    code : Mapped[str] = mapped_column(String())
    last_name : Mapped[str] = mapped_column(String())
    first_name : Mapped[str] = mapped_column(String())


# GENERAL ROUTES
@app.route("/")     
def home():
    return render_template("home.html", title="Home")


# Attendance list
@app.route("/attendance")
def calendar():
    current_date = date.today()

    # Catch non-teacher accounts
    if not session.get("teacher"):
        abort(401)

    students = db.session().execute(select(Attendance)).all()

    return render_template(
        "attendance.html", title="Calendar", students=students, current_date=current_date
        )


# Upload student timetable page
@app.route("/upload-timetable", methods=["GET", "POST"])
def upload_timetable():
    if request.method == "POST":
        # Catch file not uploaded
        if "file" not in request.files:
            flash("No file was uploaded.")
            return app.redirect("/upload-timetable")

        # Get uploaded file and day
        file = request.files["file"]
        day = request.form.get("day")

        # Catch file not selected
        if file.filename == "":
            flash("Please select a file.")
            return app.redirect("/upload-timetable")

        # Catch if file is not .CSV
        if not file.filename.lower().endswith(auth.valid_filetype):
            flash("Please upload a .CSV file.")
            return app.redirect("/upload-timetable")

        try:
            # Read the uploaded file
            stream = io.TextIOWrapper(file.stream, encoding="utf-8-sig", newline="")
            csv_reader = csv.DictReader(stream)

            print("CSV HEADERS:", csv_reader.fieldnames)

            # Keep track of how many rows are added and skipped
            added = 0
            skipped = 0

            # Iterate through each row and add it to the database
            for row in csv_reader:
                print("ROW:", row)

                code = row.get("Student ID", "").strip()
                last_name = row.get("Last Name", "").strip()
                first_name = row.get("First Name", "").strip()

                if not code:
                    skipped += 1
                    continue

                existing_user = db.session.execute(
                select(Timetables).where(
                Timetables.code == code,
                Timetables.day == day
                )
                ).scalar_one_or_none()

                if existing_user:
                    skipped += 1
                    continue

                db.session.add(
                Timetables(
                day=day,
                code=code,
                last_name=last_name,
                first_name=first_name
                )
                )

                added += 1
            db.session().commit()

            flash(f"Successfully added {added} students. Skipped {skipped} rows.")
            return app.redirect("/upload-timetable")
        
        # Catch if CSV didn't upload properly
        except Exception as e:
            db.session.rollback()
            print("CSV upload error:", e)

            flash("An error occurred while importing.")
            return app.redirect("/upload-timetable")
    return render_template("upload-timetable.html", title="Upload Students")


# Send email function
def send_confirmation_email(app, recipient, confirmation_code):
    with app.app_context():
        message = Message(
            subject="[StudyChecker] Confirmation Code",
            recipients=[recipient]
        )

        # Email contents
        message.body = (
            f"Kia ora,\n\n"
            f"Here is your confirmation code: {confirmation_code}\n\n"
            f"If you did not request to create this account, you can ignore this email."
        )
        mail.send(message)


# Sign up page
@app.route("/sign-up", methods=["POST", "GET"])
def sign_up(): 
    '''
    Thanks to Alex Yao for helping with this function.
    '''
    # Prevent logged in users from accessing the page
    if session.get("student") or session.get("teacher"):
        abort(401)
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        # Catch blank inputs
        if not email:
            flash("Please provide a valid email")
            return app.redirect('/sign-up')
        # Catch non-burnside email addresses
        if not email.endswith(auth.domain_name):
            flash("Please use your school Email address.")
            return app.redirect("/sign-up")
        
        # Catch accounts that already exist
        existing_users = db.session().execute(
            select(Students).where(Students.email == email)
            ).scalar_one_or_none()
        if existing_users:
            flash("An account is already registered under this Email.")
            return app.redirect('/sign-up')

        # Generate a random 6 digit code
        correct_number = random.randint(100000, 999999)

        # Store variables as sessions for confirmation page
        session['email'] = email
        session["correct_number"] = correct_number

        # Send email with confirmation number to recipient
        try:
            send_confirmation_email(app, email, correct_number)
        except Exception as e:
            print("Email error:", repr(e))
            flash("An error occurred, please try again later.")
            return app.redirect('/sign-up')

        return app.redirect('/confirm')
    return render_template('sign-up.html', title='Sign Up')


# Page for entering confirmation code
@app.route("/confirm", methods=['POST', 'GET'])
def confirm():
    # Getting variables from sign-up page sessions
    email = session.get("email")
    correct_number = session.get("correct_number")

    # Prevents users from accessing the route if they are not making an account
    if not correct_number or not email:
        abort(401)

    if request.method == "POST":
        # Get user's confirmation number
        try:
            confirmation_number = int(
            request.form.get("confirmation_number", "").strip()
            )
        except ValueError:      # Catch users inputting letters into the field
            flash("Please enter a valid confirmation number")
            return app.redirect('/confirm')

        # Final confirmation
        if confirmation_number == correct_number:
            # Add the account into the database if confirmation is right
            db.session().add(Students(email=email))
            db.session().commit()

            session.clear()  # Clears the session variables
            
            # Redirect user to student login
            return app.redirect("/student-login")
        else:
            flash("Invalid confirmation number")
            return app.redirect("/confirm")

    return render_template("confirm.html", title="Confirm")


# Teacher login page
@app.route("/teacher-login")
def teacher_login():
    if "teacher" not in session:  # Instantiate session
        session["teacher"] = False

    if session.get("teacher"):
        return app.redirect("/")

    return render_template("teacher-login.html", title="Teacher Login")


@app.route("/teacher-loginregister", methods=["GET", "POST"])
def teacherloginregister():
    code = request.form.get("username")
    password = request.form.get("password")
    # Catch if user exceeds character limit
    if len(code) > auth.max_characters or len(password) > auth.max_characters:
        flash("Too many characters entered.")
        return app.redirect("/teacher-login")

    user = db.session().execute(select(Admins).where(Admins.code == code)).scalar_one_or_none()
    if not user:
        flash("User does not exist.")
        return app.redirect("/teacher-login")
    
    if check_password_hash(user.password, password):
        # Set account sessions
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
    if session.get("student"):
        return app.redirect("/")
    
    return render_template("student-login.html", title="Student Login")


# Redirect to google login
@app.route("/student-loginregister")
def student_loginregister():
    # Catch users that are already logged in
    if session.get("student"):
        return app.redirect("/")
    
    # Send user to google login
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


# Google login functionality
@app.route("/auth/google/callback")
def google_callback():
    # Get user information
    token = google.authorize_access_token()
    user = token["userinfo"]

    email = user["email"]

    # Check if email is from Burnside
    if not email.endswith(auth.domain_name):
        flash("Please use your school Google account.")
        return app.redirect("/student-login")

    # Get student based on email
    student = db.session.execute(
        select(Students).where(Students.email == email)
    ).scalar_one_or_none()

    # Catch if student account isn't registered
    if student is None:
        flash("No student account found.")
        return app.redirect("/student-login")

    # Get student code
    student_code = student.email[:5]

    # Set account sessiosn
    session["student"] = student.email
    session["name"] = student_code
    return app.redirect("/")


# Removes all sessions and returns home
@app.route("/sign-out")
def sign_out():
    session.clear()
    return app.redirect("/")


# Student-end attendance
@app.route("/check-in")
def check_in():
    double_counter = False
    current_date = date.today()

    # Catch users that are not logged in
    if "student" not in session or not session["student"]:
            abort(401)

    # Catch if user already checked in
    attendance = db.session().execute(
        select(Calendar).
        where(Calendar.student_id == session["student"]).
        where(Calendar.date == current_date)
        ).one_or_none()

    if attendance:
        double_counter = True

    return render_template("check-in.html", title="Check-in", double_counter=double_counter)


@app.route("/check-register", methods=["GET", "POST"])
def checkin_register():
    wifi = subprocess.check_output(['netsh', 'WLAN', 'show', 'interfaces'])
    data = wifi.decode('utf-8')
    network_name = str()
    current_date = date.today()
    user_id = session["student"]

    print(data)

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
