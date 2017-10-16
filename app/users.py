from flask import render_template, redirect, url_for, request, g, session
from app import webapp


import mysql.connector
import hashlib
import os

from app.config import db_config
from app.images import image_transformation, check_path


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
webapp.secret_key = '\x80\xa9s*\x12\xc7x\xa9d\x1f(\x03\xbeHJ:\x9f\xf0!\xb1a\xaa\x0f\xee'


def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db


@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


# Salt and Hash the password before accessing database
# Each user has a unique salt value, based on their name length and name
def salt_hash(password, username):
    salt = 'Ece1779' + username + str(len(username))
    hashed = hashlib.md5((salt + password).encode('utf-8')).hexdigest()
    return hashed


# ================== Users' Function ==================
@webapp.route('/user/sign_in', methods=['POST'])
# User Authentication
def user_signin():
    username = request.form.get('username', "")
    password = request.form.get('password', "")
    if username == "" or password == "":
        error_msg = "Error: All fields are required!"
        return render_template("main.html", title="Home Page", error_msg=error_msg, username=username)

    password = salt_hash(password, username)

    cnx = get_db()
    cursor = cnx.cursor()

    query = "SELECT * FROM userprofile WHERE username = %s"

    cursor.execute(query, (username,))

    row = cursor.fetchone()

    # Username doesn't exist in database
    if not row:
        error_msg = "Error! Incorrect username and/or password."
        return render_template("main.html", title="Home Page", error_msg=error_msg, username=username)

    dbpassword = row[2]
    user_id = row[0]

    # Username and password matches
    if password == dbpassword:
        # Go to User Image Profile Page
        session['authenticated_user_'+str(user_id)] = True
        return redirect(url_for('user_profile', user_id=user_id))

    # Incorrect Password
    else:
        error_msg = "Error! Incorrect username and/or password."
        return render_template("main.html", title="Home Page", error_msg=error_msg, username=username)


@webapp.route('/user/sign_up', methods=['GET'])
# Display user signup page to fill in username and password
def user_signup():
    return render_template("user/signup.html", title="Sign Up")


@webapp.route('/user/sign_up', methods=['POST'])
# Create a new user and save it in the database.
def user_signup_submit():
    username = request.form.get('username', "")
    password = request.form.get('password', "")

    # Check any empty field
    if username == "" or password == "":
        error_msg = "Error: All fields are required!"
        return render_template("user/signup.html", title="Sign Up", error_msg=error_msg, username=username)

    # Check if user with same username already exists
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM userprofile WHERE username = %s"
    cursor.execute(query, (username,))
    row = cursor.fetchone()

    if row is not None:
        error_msg = "Error! User: " + username + " already exists!"
        return render_template("user/signup.html", title="Sign Up", error_msg=error_msg, username=username)

    # If everything is fine, encrypt the password and save user info in database
    password = salt_hash(password, username)

    query = "INSERT INTO userprofile (username,password) VALUES (%s,%s)"

    cursor.execute(query, (username, password))
    cnx.commit()

    return redirect(url_for('main'))


# ================== Teaching Assistant Function ==================
@webapp.route('/ta/sign_up', methods=['GET'])
# Display user signup page to fill in username and password
def ta_config():
    return render_template("user/ta.html", title="TA Sign Up Page")


@webapp.route('/ta/reset', methods=['GET'])
def ta_reset():
    return render_template("user/ta.html", title="TA Sign Up Page")


@webapp.route('/ta/cancel', methods=['GET'])
def ta_cancel():
    return redirect(url_for('main'))


@webapp.route('/ta/submit', methods=['POST'])
# Create a new user and save it in the database.
def ta_submit():
    username = request.form.get('username', "")
    password = request.form.get('password', "")

    # Check any empty field
    if username == "" or password == "":
        error_msg = "Error: All fields are required!"
        return render_template("user/ta.html", title="Sign Up", error_msg=error_msg, username=username)

    # Check if user with same username already exists
    cnx = get_db()
    cursor = cnx.cursor()
    query = "SELECT * FROM userprofile WHERE username = %s"
    cursor.execute(query, (username,))
    row = cursor.fetchone()

    if row is not None:
        error_msg = "Error! User: " + username + " already exists!"
        return render_template("user/ta.html", title="Sign Up", error_msg=error_msg, username=username)

    # If everything is fine, encrypt the password and save user info in database
    password = salt_hash(password, username)

    query = "INSERT INTO userprofile (username,password) VALUES (%s,%s)"

    cursor.execute(query, (username, password))
    cnx.commit()

    query = "SELECT * FROM userprofile WHERE username = %s"
    cursor.execute(query, (username,))
    row = cursor.fetchone()
    user_id = row[0]

    # Create 'local_images' folder for storing uploaded images
    target = os.path.join(APP_ROOT, 'static/')

    # If local_image folder not exist
    if not os.path.isdir(target):
        os.mkdir(target)

    image_url_list = []

    # Process each image
    for file in request.files.getlist("file"):
        if not file:
            print('2222222222222')
            error_msg = 'No image detected, please try again.'

            # If no image detect, TA will be brought back to TA submit page, no TA info will be saved in database
            query = "DELETE FROM userprofile WHERE username = %s"
            cursor.execute(query, (username,))
            cnx.commit()

            return render_template("user/ta.html", title="Sign Up", error_msg=error_msg, username=username)
        # Get filename
        filename = file.filename
        print('=========== Dealing with ' + filename + ' ===========')

        # Save file to user's static folder
        destination = "".join([target, filename])
        file.save(destination)

        # Generate relative path for html display
        original_url = url_for('static', filename=filename)

        print(original_url)
        trans_url = image_transformation(filename)
        image_url_list.append(original_url)
        for each in trans_url:
            image_url_list.append(each)
        print(image_url_list)

        # Update/insert those urls into database
        check_path(image_url_list, user_id, filename)
        print('=========== ' + filename + ' has been saved to database successfully ===========')

        # Clear image_url_list before processing next image
        image_url_list = []

    session['authenticated_user_' + str(user_id)] = True
    return redirect(url_for('user_profile', user_id=user_id))
