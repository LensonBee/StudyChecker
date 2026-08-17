import smtplib

try:
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
    server.ehlo()
    server.starttls()
    server.ehlo()

    print("SMTP CONNECTION SUCCESSFUL")

    server.quit()

except Exception as e:
    print("SMTP ERROR:", repr(e))