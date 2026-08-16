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
from threading import Thread
import random
import os
import pandas as pd

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
mail = Mail(app)

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

# Database setup
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


# Attendance list
@app.route("/attendance")
def calendar():
    current_date = date.today()

    # Catch non-teacher accounts
    if not session.get("teacher"):
        abort(401)

    students = db.session().execute(select(Calendar)).all()

    if not students:
        print(students)

    return render_template(
        "attendance.html", title="Calendar", students=students, current_date=current_date
        )


# Upload student rolls page
# @app.route('/calendar', methods=['GET', 'POST'])
# def index():
#     message = None
#     if request.method == 'POST':
#         file = request.files['file']
#         if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
#             # Secure the filename and clean it for table naming
#             filename = secure_filename(file.filename)
#             table_name = os.path.splitext(filename)[0].lower()
            
#             # Read spreadsheet using pandas
#             if filename.endswith('.csv'):
#                 df = pd.read_csv(file)
#             else:
#                 df = pd.read_excel(file)
            
#             # Save dataframe to database
#             # 'if_exists=replace' drops old table if it has the same name
#             # 'con=db.engine' connects pandas directly to your Flask database
#             df.to_sql(name=table_name, con=db.engine, if_exists='replace', index=False)
            
#             message = f"Successfully saved to database as table: '{table_name}'!"
            
#     return render_template('index.html', message=message)


# Send email function
def send_confirmation_email(app, recipient, confirmation_code):
    '''Function for sending the confirmation email'''
    with app.app_context():
        message = Message(
            subject="[StudyChecker] Confirmation Code",
            recipients=[recipient]
        )

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
        email = request.form.get("email")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")

        # Catch blank inputs
        if not email or not first_name or not last_name:
            flash("Please provide valid inputs")
            return app.redirect('/sign-up')
        # Catch non-burnside email addresses
        if not email.endswith("@burnside.school.nz"):
            flash("Please use your school Google account.")
            return app.redirect("/sign-up")
        # Catch user putting numbers in their name
        for letter in first_name:
            if letter.isnumeric():
                flash('Please provide a valid name length')
                return app.redirect('/sign-up')
        for letter in last_name:
            if letter.isnumeric():
                flash('Please provide a valid name length')
                return app.redirect('/sign-up')
        
        # Checking that this account doesn't already exist
        existing_users = db.session().execute(select(Students).where(Students.email == email)).scalar_one_or_none()
        if existing_users:
            return app.redirect('/sign-up')

        # Store the variables as a session for confirmation page
        session['email'] = email
        session["first_name"] = first_name
        session["last_name"] = last_name

        # Generate a random 6 digit code and store it as a session
        correct_number = random.randint(100000, 999999)
        session["correct_number"] = correct_number

        # Send the email
        try:
            Thread(
                target=send_confirmation_email,
                args=(app, email, correct_number),
                daemon=True
            ).start()
        except Exception as e:
            print("Email error:", e)
            flash("An error occurred, please try again later.")
            return app.redirect('/sign-up')

        return app.redirect('/confirm')
    return render_template('sign-up.html', title='Sign Up')


# Page for entering confirmation code
@app.route("/confirm", methods=['POST', 'GET'])
def confirm():
    # Getting variables from the session
    email = session.get("email")
    first_name = session.get("first_name")
    last_name = session.get("last_name")
    correct_number = session.get("correct_number")

    # prevents users from accessing the route if they are not making an account
    if correct_number is None:
        abort(401)

    if request.method == "POST":
        # Get user's confirmation number, and catch if it contains letters
        try:
            confirmation_number = int(
            request.form.get("confirmation_number", "").strip()
            )
        except ValueError:
            flash("Please enter a valid confirmation number")
            return app.redirect('/confirm')

        # Final confirmation
        if confirmation_number == correct_number:
            # Add the account into the database if confirmation is right
            db.session().add(Students(email=email))
            db.session().commit()

            session.clear()  # Clears the session variables
            # Logging in user after successful account creation
            
            return app.redirect('/')
        else:
            flash("Invalid confirmation number")
            return app.redirect('/confirm')

    return render_template("confirm.html", title="Confirm")


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
        return app.redirect("/")
    
    return render_template("student-login.html", title="Student Login")


# redirect to google login
@app.route("/student-loginregister")
def student_loginregister():
    # check if user is already logged in
    if not session.get("student"):
        return app.redirect("/")
    
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
    session.clear()
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
