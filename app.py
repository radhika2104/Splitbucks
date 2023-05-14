
from audioop import mul
from email import message
import re
import math
import email
from locale import currency
import sqlite3
from tkinter.tix import Select
from flask import Flask, jsonify, redirect, render_template, session, request
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import money, login_required, get_db_conn
from helpers import password_criteria
from helpers import check_and_add_friends, get_friendRows, get_DebtRows
from string import punctuation
from datetime import date, datetime
from werkzeug.utils import secure_filename
import os
import json
from flask import Flask
from flask_mail import Mail, Message

# Configure Application
app = Flask(__name__)

# By default flask reloads the python files if any changes made but not templates
# Ensure templates are auto-reloaded if they dont go through render_template
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Jinja filters enables on the go modification to the way data is presented, without having to touch back-end
app.jinja_env.filters["money"] = money

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Configure mail to use send email updates
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'dummy_mail'
app.config['MAIL_PASSWORD'] = 'dummy_password'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

# Uploads an image/pdf file to a static folder
app.config['UPLOAD_FOLDER'] = "static/images"

# Create objects of session and mail class
Session(app)
mail = Mail(app)

# Create database connection
db = get_db_conn()
# Create tables
# The columns indexes correspond to id - 0, username - 1, email - 2, hash - 3 when list/tuple is returned in SELECT query
db.execute('''CREATE TABLE IF NOT EXISTS users
          (id INTEGER PRIMARY KEY AUTOINCREMENT,
           username TEXT NOT NULL,
           email TEXT NOT NULL,
           hash TEXT NOT NULL);''')

db.execute('''CREATE TABLE IF NOT EXISTS friends
          (user_id INTEGER NOT NULL REFERENCES users(id),
           friend_id INTEGER NOT NULL REFERENCES users(id),
           PRIMARY KEY (user_id, friend_id) );''')

db.execute('''CREATE TABLE IF NOT EXISTS groups
          (group_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
           group_name TEXT NOT NULL );''')

db.execute('''CREATE TABLE IF NOT EXISTS groups_friends
          (group_id INTEGER NOT NULL REFERENCES groups(group_id),
           user_id INTEGER NOT NULL REFERENCES users(id),
           PRIMARY KEY (group_id,user_id)  );''')

db.execute('''CREATE TABLE IF NOT EXISTS transactions
            (trans_id INTEGER NOT NULL,
	        description TEXT NOT NULL,
            currency TEXT NOT NULL,
            time NUMERIC NOT NULL,
            date NUMERIC NOT NULL,
            notes TEXT,
            images BLOB,
            total_trans_value REAL NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            group_id INTEGER REFERENCES groups(group_id),
            paid_user_value REAL NOT NULL,
            split_user_value REAL NOT NULL,
            net_user_value REAL NOT NULL,
            PRIMARY KEY (trans_id,user_id) );''')

db.execute('''CREATE TABLE IF NOT EXISTS pay
            (trans_id INTEGER NOT NULL REFERENCES transactions(trans_id),
            group_id INTEGER REFERENCES groups(group_id),
            currency TEXT NOT NULL REFERENCES transactions(currency),
            lent_id INTEGER NOT NULL REFERENCES users(id),
            owe_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            lentowe TEXT NOT NULL,
            PRIMARY KEY (trans_id,lent_id,owe_id)  );''')

db.execute('''CREATE TABLE IF NOT EXISTS summary
            (group_id INTEGER REFERENCES groups(group_id),
            currency TEXT NOT NULL REFERENCES transactions(currency),
            lent_id INTEGER NOT NULL REFERENCES users(id),
            owe_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            lentowe TEXT NOT NULL,
            settle INTEGER DEFAULT 0 NOT NULL,
            PRIMARY KEY (group_id,currency,lent_id,owe_id)  );''')

# Activity types = [create_profile,add_friend,add_group,add_transaction,add_settlement]
# Not NULLS common for all activity-types
# No seperate columns needed for create_profile
db.execute('''CREATE TABLE IF NOT EXISTS activity
            (timestamp TIMESTAMP NOT NULL,
            doer_id INTEGER NOT NULL REFERENCES users(id),
            activity_type TEXT NOT NULL,
            involved_user_id INTEGER NOT NULL REFERENCES users(id),
            add_friend_id INTEGER REFERENCES users(id),
            add_group_id INTEGER REFERENCES groups(group_id),
            add_gf_id INTEGER REFERENCES groups(group_id),
            settle_group_id INTEGER REFERENCES summary(group_id),
            settle_lent_id INTEGER REFERENCES summary(lent_id),
            settle_owe_id INTEGER REFERENCES summary(owe_id),
            settle_currency TEXT REFERENCES summary(currency),
            settle_amount REAL REFERENCES summary(amount),
            trans_desc TEXT REFERENCES transactions(description),
            trans_group_id INTEGER REFERENCES transactions(group_id),
            trans_currency TEXT REFERENCES transactions(currency),
            trans_net_value REAL REFERENCES transactions(net_user_value) );''')

db.close()

# Valid currency_pairs for app
currency_pairs = {'USD':'$', 'GBP':'£', 'AED': 'د.إ', 'THB':'฿', 'CHF':'CHF',
                    'SGD':'SG$', 'JPY':'¥', 'INR':'₹', 'AUD':'A$', 'CAD':'CA$'}


# To disable caching in Python Flask, we can set the response headers to disable cache.
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    """Render homepage if logged in"""
    if "user_id" in session:
        maindb = get_db_conn()
        maincur = maindb.cursor()
        user_id = session["user_id"]
        user_involved_summary = maincur.execute(
            'SELECT * FROM activity WHERE involved_user_id = ? ORDER BY timestamp DESC', (user_id,)).fetchall()
        user_involved_summary = list(user_involved_summary)
        # activity_list = [datetime,string1,string2(if applicable) else '']
        activity_list = []
        # Helper list to avoid duplication of group creation displayed
        check_group_displayed = []
        for entry in user_involved_summary:
            if entry:
                # Make desired date format
                current_date = datetime.now()
                activityDateTime = entry[0]
                displayDateTime = datetime.strptime(activityDateTime, "%Y-%m-%d %H:%M:%S.%f")
                if displayDateTime.year == current_date.year and displayDateTime.month == current_date.month and displayDateTime.day == current_date.day:
                    desired_date = 'Today, ' + displayDateTime.strftime("%I:%M %p")
                elif displayDateTime.year == current_date.year:
                    desired_date = displayDateTime.strftime("%b %d, %I:%M %p")
                else:
                    desired_date = displayDateTime.strftime("%m/%d/%y, %I:%M %p")
                doer_id = entry[1]
                if doer_id == user_id:
                    first_person = 'You'
                else:
                    first_person = maincur.execute('SELECT username FROM users WHERE id = ?', (doer_id,)).fetchone()
                    first_person = (first_person[0]).capitalize()

                activity_type = entry[2]
                # Activity types - [create_profile, add_friend,add_group,add_transaction,add_settlement]
                if activity_type == 'create_profile':
                    string1 = 'You created $plitbucks profile.'
                    string2 = ''
                    activity_list.append([desired_date, string1, string2])

                elif activity_type == 'add_friend':
                    add_friend_id = entry[4]
                    if add_friend_id == user_id:
                        second_person = 'you'
                    else:
                        second_person = maincur.execute('SELECT username FROM users WHERE id = ?', (add_friend_id,)).fetchone()
                        second_person = (second_person[0]).capitalize()
                    string1 = '{} added {} as a friend.'.format(first_person, second_person)
                    string2 = ''
                    activity_list.append([desired_date, string1, string2])

                elif activity_type == 'add_group':
                    # Add group_name
                    add_group_id = entry[5]
                    check_group_displayed.append(add_group_id)
                    if check_group_displayed.count(add_group_id) <= 1:
                        groupname = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (add_group_id ,)).fetchone()
                        groupname = (groupname[0]).capitalize()
                        string1 = '{} created a group "{}"'.format(first_person, groupname)
                        string2 = ''
                        activity_list.append([desired_date, string1, string2])
                    # Add activity of friends added in group excluding self did not add self
                    add_gf_id = entry[6]
                    if doer_id == user_id == add_gf_id:
                        pass
                    elif doer_id == user_id and doer_id != add_gf_id:
                        add_gf = maincur.execute('SELECT username FROM users WHERE id = ?', (add_gf_id,)).fetchone()
                        add_gf = (add_gf[0]).capitalize()
                        string3 = '{} added {} in group "{}"'.format(first_person, add_gf, groupname)
                        string4 = ''
                        activity_list.append([desired_date, string3, string4])
                    elif doer_id == add_gf_id and doer_id != user_id:
                        pass
                    elif user_id == add_gf_id and user_id != doer_id:
                        string3 = '{} added you in group "{}"'.format(first_person, groupname)
                        string4 = ''
                        activity_list.append([desired_date, string3, string4])
                    elif doer_id != add_gf_id != user_id:
                        add_gf = maincur.execute('SELECT username FROM users WHERE id = ?', (add_gf_id,)).fetchone()
                        add_gf = (add_gf[0]).capitalize()
                        string3 = '{} added {} in group "{}"'.format(first_person, add_gf, groupname)
                        string4 = ''
                        activity_list.append([desired_date, string3, string4])

                elif activity_type == 'add_transaction':
                    trans_desc = entry[12]
                    trans_group_id = entry[13]
                    trans_currency = entry[14]
                    currency = currency_pairs[trans_currency]
                    trans_net_value = round(entry[15], 2)

                    if trans_group_id != None:
                        groupname = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?',
                                                    (trans_group_id,)).fetchone()
                        groupname = (groupname[0]).capitalize()
                        string1 = '{} added "{}" in group "{}"'.format(first_person, trans_desc, groupname)
                    else:
                        string1 = '{} added "{}"'.format(first_person, trans_desc)
                    if trans_net_value > 0:
                        string2 = 'you get back {}{}'.format(currency, trans_net_value)
                    else:
                        trans_net_value = (trans_net_value * -1)
                        string2 = 'you owe {}{}'.format(currency, trans_net_value)
                    activity_list.append([desired_date, string1, string2])

                elif activity_type == 'add_settlement':
                    settle_group_id = entry[7]
                    settle_lent_id = entry[8]
                    settle_owe_id = entry[9]
                    settle_currency = entry[10]
                    currency = currency_pairs[settle_currency]
                    settle_amount = round(entry[11], 2)

                    if settle_lent_id == user_id:
                        settle_owe = maincur.execute('SELECT username FROM users WHERE id = ?',
                                                    (settle_owe_id,)).fetchone()
                        settle_owe = (settle_owe[0]).capitalize()
                        if settle_group_id != None:
                            groupname = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?',
                                                        (settle_group_id,)).fetchone()
                            groupname = (groupname[0]).capitalize()
                            string1 = '{} paid you in group "{}"'.format(settle_owe, groupname)
                        else:
                            string1 = 'You recorded a payment from {}'.format(settle_owe)
                        string2 = 'you received {}{}'.format(currency, settle_amount)
                    elif settle_owe_id == user_id:
                        settle_lent = maincur.execute('SELECT username FROM users WHERE id = ?', (settle_lent_id ,)).fetchone()
                        settle_lent = (settle_lent[0]).capitalize()
                        if settle_group_id != None:
                            groupname = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (settle_group_id ,)).fetchone()
                            groupname = (groupname[0]).capitalize()
                            string1 = 'You paid {} in group "{}"'.format(settle_lent, groupname)
                        else:
                            string1 = 'You sent a payment to {}'.format(settle_lent)
                        string2 = 'you paid {}{}'.format(currency, settle_amount)
                    activity_list.append([desired_date, string1, string2])

        maincur.close()
        maindb.close()
        if len(activity_list) == 0:
            act_message = 'No activity here! Get started by adding friends, groups or expenses with them.'
            return render_template("activity.html", message=act_message)
        return render_template("activity.html", activity_list=activity_list)
    return render_template("index.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()
    # Redirect user to login form
    return redirect("/")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Make changes in account of post changes made"""
    user_id = session["user_id"]
    # Query database for id and show user details
    db = get_db_conn()
    cur = db.cursor()
    row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    cur.close()
    db.close()

    if request.method == "POST":
        id = request.form.get("id")
        username = request.form.get("username")
        email = request.form.get("email")
        cpassword = request.form.get("current-password")
        npassword = request.form.get("new-password")
        emailerror = error = cperror = nperror = passworderror = None

        adb = get_db_conn()
        acur = adb.cursor()
        # If username is not None, change username in DB
        if username is not None:
            username = username.strip()
            acur.execute('UPDATE users SET username = ? WHERE id = ?', (username, user_id))
            adb.commit()
        # If email is not None and valid, change email in DB
        if email is not None:
            email = email.strip()
            # Check if email matches an email format, ideally execute this in JS but multiple seq event error
            regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            if(re.fullmatch(regex, email)):
                acur.execute('UPDATE users SET email = ? WHERE id = ?', (email, user_id))
                adb.commit()
            # If user attempts to change email and enters invalid email address, prompt user
            else:
                emailerror = '\nEmail not updated due to invalid email address!\n'
        # If user leaves newpassword blank, display current errors if any else show the update to user
        if npassword == "" or npassword == None:
            newrow = acur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if emailerror:
                error = emailerror
                acur.close()
                adb.close()
                return render_template('account.html', row=newrow, error=error)
            else:
                acur.close()
                adb.close()
                return render_template('account.html', row=newrow)
        # If user has not left newpassword blank that means user intends to change password
        else:
            npassword = npassword.strip()
            # Check password errors
            if (cpassword == "") or (cpassword is None):
                # Check current password None
                cperror = '\nPlease enter current password to set new password!\n'
                if emailerror:
                    error = emailerror + cperror
                else:
                    error = cperror
                newrow = acur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                acur.close()
                adb.close()
                return render_template('account.html', row=newrow, error=error)
            # Check if current password matches or new password valid
            else:
                cpassword = cpassword.strip()
                # Check if current password matches
                passwordRow = acur.execute('SELECT hash FROM users WHERE id = ?', (user_id,)).fetchone()
                password = passwordRow[0]
                # If password matches, check if new password is valid
                if not (check_password_hash(password, cpassword)):
                    passworderror = '\nCurrent password does not match.\n'
                    if emailerror:
                        error = emailerror + passworderror
                    else:
                        error = passworderror
                        newrow = acur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                        acur.close()
                        adb.close()
                        return render_template('account.html', row=newrow, error=error)
                # New password validity check
                else:
                    check = password_criteria(npassword)
                    if check != 'success':
                        nperror = check
                        if emailerror:
                            error = emailerror+nperror
                        else:
                            error = nperror
                        newrow = acur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                        acur.close()
                        adb.close()
                        return render_template('account.html', row=newrow, error=error)
                    # All password criteria match, update password
                    else:
                        newpassword = generate_password_hash(npassword)
                        acur.execute('UPDATE users SET hash = ? WHERE id = ?', (newpassword, user_id))
                        adb.commit()
                        # Need to show success statement for password change since it is not visible to user on page
                        success = 'Password updated successfully!'
                        newrow = acur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                        acur.close()
                        adb.close()
                        return render_template('account.html', row=newrow, success=success)
    else:
        # GET request without row changes
        return render_template('account.html', row=row)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("email"):
            error = 'Must provide email to login!'
            return render_template('login.html', error=error)
        # Ensure password was submitted
        elif not request.form.get("password"):
            error = 'Must provide password to login!'
            return render_template('login.html', error=error)

        # Query database for email
        db = get_db_conn()
        cur = db.cursor()
        row = cur.execute("SELECT * FROM users WHERE email = ?", (request.form.get("email"),)).fetchone()
        cur.close()
        db.close()

        # Ensure username exists and password is correct
        if row == None or (not check_password_hash(row[3], request.form.get("password"))):
            error = "Invalid username and/or password. Please try again."
            return render_template('login.html', error=error)

        # Remember which user has logged in
        session["user_id"] = row[0]

        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('login.html')


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup user"""
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db_conn()
        cur = db.cursor()
        if not email:
            error = 'Must provide email to signup.'
            return render_template('signup.html', error=error)
        elif not username:
            error = 'Must provide username to signup. Your friends will identify you with this name.'
            return render_template('signup.html', error=error)
        else:
            row = cur.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                error = 'Email_ID already exists. Try logging in if already registered or signup with a different email_ID.'
                return render_template('signup.html', error=error)

            elif not password:
                error = 'Must provide password to signup.'
                return render_template('signup.html', error=error)

            elif not request.form.get("confirmation"):
                error = 'Must provide password again'
                return render_template('signup.html', error=error)

            elif password != request.form.get("confirmation"):
                error = "Your password must match verification. Make sure you type same password again."
                return render_template('signup.html', error=error)

            elif len(password) < 8:
                error = "Your password must contain 8 characters."
                return render_template('signup.html', error=error)

            elif len(password) >= 8:
                l, u, d, s = 0, 0, 0, 0
                symbol = set(punctuation)

                for letter in password:
                    if letter.isupper():
                        u += 1
                    elif letter.islower():
                        l += 1
                    elif letter.isdigit():
                        d += 1
                    elif letter in symbol:
                        s += 1

                if l < 1 or u < 1 or d < 1 or s < 1:
                    error = "Your password must contain 8 characters using atleast 1 uppercase, 1 lowercase, 1 digit and 1 special character"
                    return render_template('signup.html', error=error)

        # If error checks pass, create hash and insert entry into database
        hash_password = generate_password_hash(password)

        cur.execute("INSERT INTO users (username,email,hash) VALUES (?,?,?)", (username, email, hash_password))
        db.commit()

        # Redirect to homepage after login
        row = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = row[0]
        user_id = row[0]

        # Insert activity of create_profile
        activity_type = 'create_profile'
        currentDateTime = datetime.now()
        cur.execute("INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id) VALUES (?,?,?,?)",
                    (currentDateTime, user_id, activity_type, user_id))
        db.commit()

        cur.close()
        db.close()

        # Send email update for successfull signup
        msg = Message(subject='Welcome to SplitBucks', sender='radhikamendiratta1994@gmail.com', recipients=[email])
        msg.body = ("Nice to meet you %s! You have been successfully registered to Splitbucks.\n\nGet started by adding friends and experience less stress while sharing any kind of expenses.\n\n If you have any questions or feedback, hit reply and let us know – we’d love to hear from you.\n\nHave a great day! \n\n-The SplitBucks team " % username.capitalize())
        mail.send(msg)
        return redirect("/")

    else:
        # GET method to render html page itself
        return render_template("signup.html")


@app.route('/expense_check_total', methods=["GET", "POST"])
@login_required
def expense_check_total():
    """check total value to be shared is same as total paid/shared by multiple payers"""
    if request.method == 'POST':
        total_value = request.form.get('total')
        total_value = float(total_value)
        # Syntax reference - https://stackoverflow.com/questions/23889107/sending-array-data-with-jquery-and-flask
        paidlist = request.form.getlist('paidlist[]', type=float)
        if round(sum(paidlist)) != round(total_value):
            error = 'Error: Individual values do not match the total expense.'
            return jsonify(error)
        else:
            return jsonify('success')


@app.route('/expense_check_percent', methods=["GET", "POST"])
@login_required
def expense_check_percent():
    """check total value to be shared is same as total paid by multiple payers"""
    if request.method == 'POST':
        # Syntax Reference - https://stackoverflow.com/questions/23889107/sending-array-data-with-jquery-and-flask
        paidlist = request.form.getlist('paidlist[]', type=float)
        if round(sum(paidlist)) != round(float(100)):
            error = 'Error: Individual values do not sum up to 100%'
            return jsonify(error)
        else:
            return jsonify('success')


@app.route('/expense_query', methods=["GET", "POST"])
@login_required
def expense_query():
    """ When user is represented with a query to confirm user to add as a friend in response to just username addition"""
    user_id = session["user_id"]
    if request.method == 'POST':
         # If user agrees to the friend to be added suggested by SQL query
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        friendID = int(request.form.get('friendID'))
        db = get_db_conn()
        cur = db.cursor()
        try:
            cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (user_id, friendID))
            cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (friendID, user_id))
            db.commit()
            # Insert activity
            activity_type = 'add_friend'
            currentDateTime = datetime.now()
            cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                        (currentDateTime, user_id, activity_type, user_id, friendID))
            cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                        (currentDateTime, user_id, activity_type, friendID, friendID))
            db.commit()
            cur.close()
            db.close()
            success = 'added friend!'
            friendRows = get_friendRows(user_id)
            DebtRows = get_DebtRows(user_id)
            return render_template("expense.html", success=success, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
        except sqlite3.IntegrityError:
            error = 'Friend already added!'
            cur.close()
            db.close()
            return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
    # GET method to render expense page itself
    else:
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        return render_template("expense.html", currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)


@app.route('/expense_addfriend', methods=["GET", "POST"])
@login_required
def expense_addfriend():
    """ Adds a friend"""
    user_id = session["user_id"]
    if request.method == 'POST':
        # If user posted add friend form
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        username = request.form.get('username')
        email = request.form.get('email')
        # Check for errors
        if not email and not username:
            error = 'must provide email or existing username'
            return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
        # Check if email matches correctly and add friend
        elif email and not username:
            db = get_db_conn()
            cur = db.cursor()
            row = cur.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if not row:
                error = 'must provide correct email or existing username'
                cur.close()
                db.close()
                return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
            else:
                try:
                    cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (user_id, row[0]))
                    cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (row[0], user_id))
                    db.commit()

                    # Insert activity
                    activity_type = 'add_friend'
                    currentDateTime = datetime.now()
                    cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                                (currentDateTime, user_id, activity_type, user_id, row[0]))
                    cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                                (currentDateTime, user_id, activity_type, row[0], row[0]))
                    db.commit()

                    cur.close()
                    db.close()
                    success = 'added friend ' + (row[1]).capitalize() + '!'
                    # Get friendRows and debtrows again since there is an update in DB
                    friendRows = get_friendRows(user_id)
                    DebtRows = get_DebtRows(user_id)
                    return render_template("expense.html", success=success, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                except sqlite3.IntegrityError:
                    error = 'Friend already added!'
                    cur.close()
                    db.close()
                    return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)

        # Check if email does not match but username is registered.
        # Send a pop message if user has mentioned intended username (this is 'yes' part of form submitted)
        elif username:
            db = get_db_conn()
            cur = db.cursor()
            row = cur.execute('SELECT * FROM users WHERE username = ? and email = ?', (username, email)).fetchone()
            # If both username and email do not fetch entry, just check email first and then username with suggested email from SQL database
            if not row:
                rowMail = cur.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                if not rowMail:
                    rowUsername = cur.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
                    if not rowUsername:
                        error = 'Email and/or username are not registered.'
                        cur.close()
                        db.close()
                        return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                    else:
                        query = 'Username exists but incorrect email. Did you mean \n %s with email %s' % (
                            username.capitalize(), rowUsername[2])
                        friendID = rowUsername[0]
                        cur.close()
                        db.close()
                        return render_template("expense.html", query=query, friendID=friendID, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                else:
                    query = 'Email exists but incorrect username. Did you mean \n %s with username %s' % (
                        email,(rowMail[1]).capitalize())
                    friendID = rowMail[0]
                    cur.close()
                    db.close()
                    return render_template("expense.html", query=query, friendID=friendID, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
            # If both username and email fetch an exact entry
            else:
                try:
                    cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (user_id, row[0]))
                    cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (row[0], user_id))
                    db.commit()

                    # Insert activity
                    activity_type = 'add_friend'
                    currentDateTime = datetime.now()
                    cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                                (currentDateTime, user_id, activity_type, user_id, row[0]))
                    cur.execute('INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_friend_id) VALUES (?,?,?,?,?)',
                                (currentDateTime, user_id, activity_type, row[0], row[0]))
                    db.commit()

                    cur.close()
                    db.close()
                    # Get FriendRows and debtrows again since there is new commit to DB
                    friendRows = get_friendRows(user_id)
                    DebtRows = get_DebtRows(user_id)
                    success = 'added friend '+username.capitalize() + '!'
                    return render_template("expense.html", success=success, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                except sqlite3.IntegrityError:
                    error = 'Friend already added!'
                    cur.close()
                    db.close()
                    return render_template("expense.html", error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
        # Just incase you missed a return condition
        return redirect("/expense")
    # GET method to render expense page itself
    else:
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        return render_template("expense.html", currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)


@app.route('/expense_addgroup', methods=["GET", "POST"])
@login_required
def expense_addgroup():
    """ Adds a group to share expenses with"""
    user_id = session["user_id"]
    if request.method == 'POST':
        # If user selected add group form
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        # Show error if group field is empty
        groupname = request.form.get('groupname')
        if not groupname:
            error = 'Must enter name for group.'
            return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
        friends = request.form.get('friendnames')
        if not friends:
            error = 'Must enter atleast one friend name.'
            return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
        friendIDlist = friends.split(', ')
        friendIDlist = [int(x) for x in friendIDlist]
        # Remove duplicates if any to avoid user mistake
        friendIDlist = [*set(friendIDlist)]
        for id_friend in friendIDlist:
            if id_friend not in friendRows:
                error = 'Username(s) does not exist in friends list. Either add a new friend or create a group with existing friends.'
                return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)

        maindb = get_db_conn()
        maincur = maindb.cursor()
        # If no error found insert group entry
        maincur.execute("INSERT INTO groups (group_name) VALUES (?)", (groupname,))
        maindb.commit()
        # Fetch the group_id generated
        group_id = maincur.execute('SELECT group_id FROM groups WHERE group_name = ?', (groupname,)).fetchone()
        group_id = group_id[0]
        # Insert user's id into group
        maincur.execute("INSERT INTO groups_friends (group_id,user_id) VALUES (?,?)", (group_id, user_id))
        maindb.commit()
        # Insert activity for self
        activity_type = 'add_group'
        currentDateTime = datetime.now()
        add_gf_id = user_id
        maincur.execute(
            'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_group_id,add_gf_id) VALUES (?,?,?,?,?,?)',
            (currentDateTime, user_id, activity_type, user_id, group_id, add_gf_id))
        maindb.commit()
        # Fetch friend's id and insert into groups_friends
        for id_friend in friendIDlist:
            maincur.execute("INSERT INTO groups_friends (group_id,user_id) VALUES (?,?)", (group_id, id_friend))
            maindb.commit()
            # Insert activity for friends
            for id_f in friendIDlist:
                add_gf_id = id_f
                maincur.execute(
                    'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_group_id,add_gf_id ) VALUES (?,?,?,?,?,?)',
                    (currentDateTime, user_id, activity_type, id_friend, group_id, add_gf_id))
                maindb.commit()
        # Activity - Loop for involved self with friends
        for id_f in friendIDlist:
            add_gf_id = id_f
            maincur.execute(
                'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,add_group_id,add_gf_id ) VALUES (?,?,?,?,?,?)',
                (currentDateTime, user_id, activity_type, user_id, group_id, add_gf_id))
            maindb.commit()

        success = 'Added group - ' + groupname.capitalize() + '!'
        maincur.close()
        maindb.close()
        # Get friendrows and debtrows again to fetch new entry inserted in DB
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        return render_template("expense.html", success=success, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)

    # GET method to render expense page itself
    else:
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        return render_template("expense.html", currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)


@app.route('/expense', methods=["GET", "POST"])
@login_required
def expense():
    """Adds expense transaction"""
    user_id = session["user_id"]

    if request.method == 'POST':
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        maindb = get_db_conn()
        maincur = maindb.cursor()
        # If post request recieved is of expense sharers - button click is 'who'
        if ('debtor' in request.form):
            sharers = request.form.get('debtor')
            sharelist = sharers.split(', ')
            sharelist = [*set(sharelist)]
            # Finalsharers to be a dictionary object of {id:name} of friends
            finalsharers = {}
            group_flag = False
            group_count = 0
            # Group to friend association for insert record into transaction table later {user_id:group_id}
            gp_fd_dic = {}

            for entry in sharelist:
                try:
                    entry = int(entry)
                    userdetail = maincur.execute('SELECT id,username FROM users WHERE id = ?', (entry,)).fetchone()
                    # If entry in list is a friend ID add it to final list
                    if userdetail:
                        entryID = userdetail[0]
                        finalsharers[entryID] = userdetail[1]

                # If entry is a groupid, find friends in group and add to final list
                except ValueError:
                    # group_id will be received as 'g-1'/'g-2'...
                    entry = entry.split('-')
                    entry = int(entry[1])
                    gID = maincur.execute('SELECT group_id FROM groups WHERE group_id = ?', (entry,)).fetchone()
                    if gID:
                        if group_count > 0:
                            error = 'Adding more than 1 group is not allowed.'
                            maincur.close()
                            maindb.close()
                            if 'save_expense' not in request.form:
                                return render_template('error.html', error=error)
                            else:
                                return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                        group_flag = True
                        gID = gID[0]

                        gfnames = maincur.execute(
                            'SELECT u.id,u.username FROM users u INNER JOIN groups_friends gf ON u.id = gf.user_id WHERE group_id = ?', (gID,)).fetchall()
                        for row in gfnames:
                            # If a friend has been added seperately in friend and in group both, reject transaction
                            if row[0] in finalsharers:
                                error = 'Having friend both inside and outside group will throw of balances in expense.'
                                maincur.close()
                                maindb.close()
                                # Check whether its a button request or a submit request
                                if 'save_expense' not in request.form:
                                    return render_template('error.html', error=error)
                                else:
                                    return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
                            finalsharers[row[0]] = row[1]
                            gp_fd_dic[row[0]] = gID
                            group_count = 1
                        group_flag = False

                    # If group_id or friends_id does not exist, send error to client
                    else:
                        error = 'Username or groupname does not exist'
                        maincur.close()
                        maindb.close()
                        if 'save_expense' not in request.form:
                            return render_template('error.html', error=error)
                        else:
                            return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)
            # If groupflag is false, add user's name to list, else it will be added through group itself
            if group_flag == False:
                username = maincur.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
                username = username[0]
                finalsharers[user_id] = username
            if ('paidby' in request.form):
                maincur.close()
                maindb.close()
                return render_template('paidby.html', finalsharers=finalsharers)
            if ('share' in request.form):
                maincur.close()
                maindb.close()
                return render_template('sharediv.html', finalsharers=finalsharers)
            if ('percent' in request.form):
                split_count = len(finalsharers)
                split_percent = round((100/split_count), 2)
                maincur.close()
                maindb.close()
                return render_template('percentdiv.html', finalsharers=finalsharers, split_percent=split_percent)
            else:
                currency = request.form.get('currency')
                currency_sign = currency[currency.find('(')+1:currency.find(')')]

                if ('equally' in request.form):
                    total_value = float(request.form.get('total'))
                    ind_share = (total_value / len(finalsharers))
                    individual_share = round(ind_share, 2)
                    equal_sharer = {}
                    for id, sharer in finalsharers.items():
                        equal_sharer[sharer] = str(currency_sign)+str(individual_share)
                    maincur.close()
                    maindb.close()
                    return render_template('equallydiv.html', equal_sharer=equal_sharer)
                elif ('amount' in request.form):
                    total_value = float(request.form.get('total'))
                    ind_share = (total_value / len(finalsharers))
                    individual_share = round(ind_share, 2)
                    maincur.close()
                    maindb.close()
                    return render_template('amountdiv.html', finalsharers=finalsharers, currency=currency_sign, individual_share=individual_share)
                # If user submitted expense form
                elif 'save_expense' in request.form:
                    multipay_data = multipayment = split_data = None
                    # Expense sharers are finalsharers and currency_sign is final currency used by them
                    trans_value = float(request.form.get("value"))
                    equal_share = (trans_value / len(finalsharers))
                    currency_name = currency[:currency.find('(')]
                    description = request.form.get("description")

                    # Checking for essential fields and error-proofing
                    ex_error = None
                    if finalsharers == {}:
                        ex_error = "Error: Add atleast 1 friend or group"
                    elif trans_value == '' or trans_value == None:
                        ex_error = "Error: Add value to be split"
                    elif description == '':
                        ex_error = "Error: Add description of expense"
                    if ex_error is not None:
                        maincur.close()
                        maindb.close()
                        return render_template('expense.html', finalsharers=finalsharers, error=ex_error)
                    trans_date = date.today().strftime("%m/%d/%y")
                    trans_time = datetime.now().strftime("%H:%M")
                    # There should be an attachment name or attachment, else no attachment is made
                    if 'attachment' not in request.files:
                        attachment = None
                        filename = None
                    else:
                        attachment = request.files["attachment"]
                        if attachment.filename != '':
                            # Filename is secured to prevent SQL injections - https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
                            filename = secure_filename(attachment.filename)
                            # Generate a file path in local directory with filename and save file - https://www.youtube.com/watch?v=Rcdk9QmB5Vg&ab_channel=Software%26WebTechnology
                            # Later save the file name into sqlite3 database to fetch it later for view
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            attachment.save(filepath)
                        else:
                            filename = None

                    textnotes = request.form.get("textnotes")
                    # If payer is multiple people then generate a multipay_data dictionary
                    who = request.form.get("who_input").strip()
                    multipay_data = {}
                    if who == "Multiple people":
                        multipayment = request.form.getlist("multipayment")
                        multipayment = [float(pay) if pay != "" else 0 for pay in multipayment]
                        # Dictionary is ordered and can get index - Will work with only python 3.6 onwards
                        for ind, id in enumerate(finalsharers.keys()):
                            multipay_data[id] = multipayment[ind]
                            if multipayment[ind] == "":
                                multipay_data[id] = 0
                    else:
                        if who == "you":
                            multipay_data[user_id] = trans_value
                        else:
                            multipay_data[int(who)] = trans_value
                        for id, sharer in finalsharers.items():
                            if id not in multipay_data:
                                multipay_data[id] = 0

                    # Cannot add expense with group and individuals if payer is not user_id
                    if len(gp_fd_dic) != 0:
                        # Check if there is an individual outside group
                        for id, value in multipay_data.items():
                            if value != 0 and id != user_id and (id not in gp_fd_dic):
                                error = 'Cannot add expense with both groups and individuals where you are not the only payer.'
                                if 'save_expense' not in request.form:
                                    return render_template('error.html', error=error)
                                else:
                                    return render_template('expense.html', error=error, currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)

                    # Generate a split data for all finalsharers
                    split_how = request.form.get("split_how_input")

                    split_data = {}
                    if split_how == 'equally':
                        for id, sharer in finalsharers.items():
                            split_data[id] = equal_share
                    else:
                        # Check which input boxes have values in them - shares,percent or amount?
                        splitinput = request.form.getlist("splitinput")
                        splitlist = [False if input == "" else True for input in splitinput]
                        splitbool = any(splitlist)
                        percentinput = request.form.getlist("percentinput")
                        percentlist = [False if input == "" else True for input in percentinput]
                        percentbool = any(percentlist)

                        shareinput = request.form.getlist("shareinput")
                        sharelist = [False if input == "" else True for input in shareinput]
                        sharebool = any(sharelist)
                        if sharebool:
                            shareinput = [float(val) for val in shareinput]

                        # Assign amounts to split data in any of the case
                        if splitbool:
                            for ind, id in enumerate(finalsharers.keys()):
                                if splitinput[ind] != "":
                                    split_data[id] = float(splitinput[ind])
                                else:
                                    split_data[id] = 0
                        elif percentbool:
                            for ind, id in enumerate(finalsharers.keys()):
                                if percentinput[ind] != "":
                                    split_data[id] = (float(percentinput[ind])*trans_value)/100
                                else:
                                    split_data[id] = 0
                        elif sharebool:
                            all_shares = sum(shareinput)
                            for ind, id in enumerate(finalsharers.keys()):
                                if shareinput[ind] != "":
                                    split_data[id] = ((shareinput[ind])*trans_value)/all_shares
                                else:
                                    split_data[id] = 0

                    # Net_borrowed or Net_Lent data for the user_in_current_transaction
                    net_data = {}
                    for key, val in split_data.items():
                        net_data[key] = multipay_data[key] - val

                    # If net_data for user is positive, user has lent, else user has borrowed
                    # All variables are ready to insert into transaction table
                    # Increment max_transaction_no and use it for current transaction
                    transaction_nos = maincur.execute('SELECT trans_id FROM transactions').fetchall()
                    max_trans = 0
                    try:
                        for trans_list in transaction_nos:
                            for trans in trans_list:
                                if trans > max_trans:
                                    max_trans = trans
                        trans_id = max_trans + 1
                        # If there is no transaction data, initialise trans_id as 1
                    except:
                        trans_id = 1

                    # Before committing the transaction, check if all finalsharers are friends of each other
                    if len(finalsharers) > 2:
                        add_friend = check_and_add_friends(user_id, finalsharers)

                    for id, net_value in net_data.copy().items():
                        g_id = gp_fd_dic.get(id)
                        # Populate transactions for every user involved in transaction
                        maincur.execute(
                            'INSERT INTO transactions (trans_id,description, currency, time, date, notes, images, total_trans_value, user_id, group_id, paid_user_value, split_user_value, net_user_value) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (trans_id, description, currency_name, trans_time, trans_date, textnotes, filename, trans_value, id, g_id, multipay_data[id], split_data[id], net_value))
                        maindb.commit()
                        # Insert activity
                        activity_type = 'add_transaction'
                        currentDateTime = datetime.now()
                        maincur.execute(
                            'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,trans_desc,trans_group_id,trans_currency,trans_net_value) VALUES (?,?,?,?,?,?,?,?)',
                            (currentDateTime, user_id, activity_type, id, description, g_id, currency_name, net_value))
                        maindb.commit()

                    # To populate pay table, create helper dictionaries
                    lent_data = {}
                    owe_data = {}
                    for id, net_value in net_data.items():
                        if net_value > 0:
                            lent_data[id] = abs(net_value)
                        elif net_value < 0:
                            owe_data[id] = abs(net_value)
                    # Create copies for summary update since we are altering the originals for pay table insertions
                    lent_data_copy = lent_data.copy()
                    owe_data_copy = owe_data.copy()
                    # relationship{'lent&owe':[amount,group_id} in this transaction will be used to simplify Lentowe and owelent in summary
                    relationship = {}

                    for id, value in owe_data.copy().items():
                        # If opposite values are present and user_id does not owe himself, find pay table data and delete entries so that they are not processed again
                        if value in lent_data.values():
                            for key, val in lent_data.items():
                                if (round(val) == round(value)) and (key != id):
                                    owe_id = id
                                    lent_id = key
                                    amount = val
                                    lentowe = (str(lent_id) + '&' + str(owe_id))
                                    # Group_id will be taken for ower because ower for the trans can be outside the group as well for which group_id will be null
                                    gr_id = gp_fd_dic.get(owe_id)
                                    relationship[lentowe] = [amount,gr_id]
                                    del lent_data[key]
                                    del owe_data[id]
                                    maincur.execute('INSERT INTO pay (trans_id,group_id,currency,lent_id,owe_id,amount,lentowe) VALUES (?,?,?,?,?,?,?)',
                                                    (trans_id, gr_id, currency_name, lent_id, owe_id, amount, lentowe))
                                    maindb.commit()
                                    break

                    # Match up owe values which do not exactly match using max function and add to pay table
                    while len(lent_data) != 0 and len(owe_data) != 0:
                        lentmax = max(zip(lent_data.values(), lent_data.keys()))
                        lentmax_value = lentmax[0]
                        lent_id = lentmax_key = lentmax[1]
                        owemax = max(zip(owe_data.values(), owe_data.keys()))
                        owemax_value = owemax[0]
                        owe_id = owemax_key = owemax[1]
                        parked = {}
                        # Lender and ower should not be the same person,park the ower and restart the algorithm
                        if lent_id == owe_id:
                            parked[owemax_key] = owemax_value
                            del owe_data[owemax_key]
                            continue
                        amount = lentmax_value - owemax_value
                        if amount == 0:
                            del lent_data[lentmax_key]
                            del owe_data[owemax_key]
                            trans_amount = lentmax_value
                        elif amount < 0:
                            del lent_data[lentmax_key]
                            owe_data[owemax_key] -= lentmax_value
                            trans_amount = lentmax_value
                        else:
                            del owe_data[owemax_key]
                            lent_data[lentmax_key] -= owemax_value
                            trans_amount = owemax_value
                        lentowe = str(lent_id) + '&' + str(owe_id)
                        # Group_id will be taken for ower because ower for the trans can be outside the group as well and hence expense should be outside group i.e. group_id is NULL
                        gr_id = gp_fd_dic.get(owemax_key)
                        relationship[lentowe] = [trans_amount, gr_id]
                        maincur.execute('INSERT INTO pay (trans_id,group_id,currency,lent_id,owe_id,amount,lentowe) VALUES (?,?,?,?,?,?,?)',
                                        (trans_id, gr_id, currency_name, lent_id, owe_id, trans_amount, lentowe))

                        maindb.commit()
                        # If any ower is parked, put it back in the dictionary
                        if len(parked) != 0:
                            owe_data.update(parked)

                    # Every time you do a transaction, insert or update summary table for those lent_id,owe_ids and reverse
                    # Select query will have results, bothways, A lent B, B lent A to be simplified in summary table
                    # This table should be summarized seperately 3 cases

                    # Relationship is of the form {'lent_id&owe_id':[amount,group_id]}
                    c = 0
                    for lentowe, details in relationship.items():
                        c += 1
                        relation = lentowe.split('&')
                        lent_id = int(relation[0])
                        owe_id = int(relation[1])
                        group_id = details[1]
                        amount = details[0]
                        # Case 1 where A lent to B in summary and current transaction
                        lentowe_summ = maincur.execute(
                            'SELECT amount,settle FROM summary WHERE lentowe = ? AND group_id IS ? AND currency = ?', (lentowe, group_id, currency_name)).fetchone()

                        try:
                            lentowe_amount = lentowe_summ[0]
                            settle = lentowe_summ[1]
                            if settle == 0:
                                new_amount = amount + lentowe_amount
                            else:
                                new_amount = amount
                            # Type error if lentowe_amount is blank/None/'\n' and Type error if we add integer to None
                            maincur.execute(
                                'UPDATE summary SET amount=?,settle=0 WHERE lentowe = ? AND group_id IS ? AND currency = ?', (new_amount, lentowe, group_id, currency_name))
                            maindb.commit()
                        except (IndexError, ValueError, TypeError):
                            # Case 2 where A lent to B in summary and B lent to A in current transaction

                            x = list(reversed(lentowe.split('&')))
                            owelent = '&'.join(x)
                            owelent_summ = maincur.execute(
                                'SELECT amount,settle FROM summary WHERE lentowe = ? AND group_id IS ? AND currency = ?', (owelent, group_id, currency_name)).fetchone()
                            try:
                                owelent_amount = owelent_summ[0]
                                settle = owelent_summ[1]
                                if settle == 0:
                                    new_amount = owelent_amount - amount
                                else:
                                    new_amount = amount
                                # 3 cases
                                if new_amount > 0:
                                    # Overall, A still lent B because new_amount is positive
                                    maincur.execute(
                                        'UPDATE summary SET amount = ?,settle = 0 WHERE lentowe = ? AND group_id IS ? AND currency = ?',
                                        (new_amount, owelent, group_id, currency_name))
                                    maindb.commit()
                                else:
                                    # Delete row if 0 or negative new amount because A no longer lent B, so delete record
                                    maincur.execute(
                                        'DELETE FROM summary WHERE lentowe = ? AND group_id IS ? AND currency = ?', (owelent, group_id, currency_name))
                                    maindb.commit()
                                    if new_amount < 0:
                                        # Now, B lent A overall, so insert a new record with absolute value
                                        new_amount = abs(new_amount)
                                        maincur.execute(
                                            'INSERT INTO summary (group_id, currency, lent_id, owe_id, amount, lentowe, settle) VALUES (?,?,?,?,?,?,?)',
                                            (group_id, currency_name, lent_id, owe_id, new_amount, lentowe, 0))
                                        maindb.commit()
                            except (IndexError, ValueError, TypeError):
                                # Case 3 where A-B / B-A relationship does not exist in summary table - insert record
                                maincur.execute(
                                    'INSERT INTO summary (group_id, currency, lent_id, owe_id, amount, lentowe, settle) VALUES (?,?,?,?,?,?,?)',
                                    (group_id, currency_name, lent_id, owe_id, amount, lentowe, 0))
                                maindb.commit()

                    maincur.close()
                    maindb.close()
                    return redirect("/")
        maincur.close()
        maindb.close()
        return redirect("/")
    # GET method to render expense page itself
    else:
        friendRows = get_friendRows(user_id)
        DebtRows = get_DebtRows(user_id)
        return render_template("expense.html", currency_pairs=currency_pairs, friendRows=friendRows, DebtRows=DebtRows)


@app.route('/dashboard')
@login_required
def dashboard():
    """ Renders summary of friends/group expenses dashboard"""
    user_id = session["user_id"]
    maindb = get_db_conn()
    maincur = maindb.cursor()
    group_expense_neg = None
    group_expense_pos = None
    friend_expense_neg = None
    friend_expense_pos = None
    overall_expense_neg = None
    overall_expense_pos = None
    # Fetching group total balance grouped by currency data
    pos_summary = maincur.execute(
        'SELECT currency,SUM(amount) FROM summary WHERE lent_id = ? AND group_id IS NOT NULL AND settle = 0 GROUP BY currency', (user_id,)).fetchall()
    neg_summary = maincur.execute(
        'SELECT currency,SUM(amount) FROM summary WHERE owe_id = ? AND group_id IS NOT NULL AND settle = 0 GROUP BY currency', (user_id,)).fetchall()
    group_result = []
    pos_summary_o = pos_summary.copy()
    neg_summary_o = neg_summary.copy()

    for pos_ind, pos_row in enumerate(pos_summary):
        for neg_ind, neg_row in enumerate(neg_summary):
            if pos_row[0] == neg_row[0]:
                currency = pos_row[0]
                currency_sign = currency_pairs[currency]
                net_value = round((pos_row[1] - neg_row[1]), 2)
                group_result.append([currency_sign, net_value])
                # Delete the values which have are being processed from lists for which we found net difference from lent and owe
                pos_summary_o.remove(pos_row)
                neg_summary_o.remove(neg_row)
    # Values for which we did not find did not find corresponding owe, add them into group
    for pos_row in pos_summary_o:
        currency = pos_row[0]
        currency_sign = currency_pairs[currency]
        net_value = round(pos_row[1], 2)
        group_result.append([currency_sign, net_value])

    # Values for which we did not find did not find corresponding LENT, add them into group
    for neg_row in neg_summary_o:
        currency = neg_row[0]
        currency_sign = currency_pairs[currency]
        net_value = round((neg_row[1])*(-1), 2)
        group_result.append([currency_sign, net_value])

    for row in group_result:
        currency_sign = row[0]
        # row[0] will be currency and row[1] will be value - positive or negative
        if row[1] > 0:
            if not group_expense_pos:
                group_expense_pos = {}
                overall_expense_pos = {}
            group_expense_pos[currency_sign] = round(row[1], 2)
            overall_expense_pos[currency_sign] = round(row[1], 2)

        elif row[1] < 0:
            if not group_expense_neg:
                group_expense_neg = {}
                overall_expense_neg = {}
            group_expense_neg[currency_sign] = (round(row[1], 2) * -1)
            overall_expense_neg[currency_sign] = (round(row[1], 2) * -1)

    # Fetching friends total balance grouped by currency data
    pos_summary_ng = maincur.execute(
        'SELECT currency,SUM(amount) FROM summary WHERE lent_id = ? AND group_id IS NULL AND settle = 0 GROUP BY currency', (user_id,)).fetchall()
    neg_summary_ng = maincur.execute(
        'SELECT currency,SUM(amount) FROM summary WHERE owe_id = ? AND group_id IS NULL AND settle = 0 GROUP BY currency', (user_id,)).fetchall()
    non_group_result = []
    pos_summary_o_ng = pos_summary_ng.copy()
    neg_summary_o_ng = neg_summary_ng.copy()

    for pos_ind, pos_row in enumerate(pos_summary_ng):
        for neg_ind, neg_row in enumerate(neg_summary_ng):
            if pos_row[0] == neg_row[0]:
                currency = pos_row[0]
                currency_sign = currency_pairs[currency]
                net_value = round((pos_row[1] - neg_row[1]), 2)
                non_group_result.append([currency_sign,net_value])
                # Delete the values which have are being processed from lists for which we found net difference from lent and owe
                pos_summary_o_ng.remove(pos_row)
                neg_summary_o_ng.remove(neg_row)

    # Values for which we did not find did not find corresponding owe, add them into group
    for pos_row in pos_summary_o_ng:
        currency = pos_row[0]
        currency_sign = currency_pairs[currency]
        net_value = round(pos_row[1], 2)
        non_group_result.append([currency_sign, net_value])

    # Values for which we did not find did not find corresponding LENT, add them into group
    for neg_row in neg_summary_o_ng:
        currency = neg_row[0]
        currency_sign = currency_pairs[currency]
        net_value = round((neg_row[1])*(-1), 2)
        non_group_result.append([currency_sign, net_value])
    for row in non_group_result:
        currency_sign = row[0]
        # row[0] will be currency and row[1] will be value - positive or negative
        if row[1] > 0:
            if not friend_expense_pos:
                friend_expense_pos = {}
            friend_expense_pos[currency_sign] = row[1]
            if not overall_expense_pos:
                overall_expense_pos = {}
            overall_expense_pos[currency_sign] = round((overall_expense_pos.get(currency_sign, 0) + row[1]), 2)
        elif row[1] < 0:
            if not friend_expense_neg:
                friend_expense_neg = {}
            friend_expense_neg[currency_sign] = (round(row[1], 2) * -1)
            if not overall_expense_neg:
                overall_expense_neg = {}
            overall_expense_neg[currency_sign] = round((overall_expense_neg.get(currency_sign, 0) + (row[1] * -1)), 2)

    if (not overall_expense_neg) and (not overall_expense_pos):
        no_trans = 'There are no expenses yet.'
        return render_template('dashboard.html', no_trans=no_trans)
    # If a currency is owed in one group and lent in another - simplify the difference
    for currency, sign in currency_pairs.items():
        if overall_expense_neg and overall_expense_pos and (sign in overall_expense_neg) and (sign in overall_expense_pos):
            x = overall_expense_pos[sign] - overall_expense_neg[sign]
            overall_expense_pos[sign] = round(x, 2)
            # If difference is negative in one dictionary, keep it in another and delete after simplifying
            if overall_expense_pos[sign] < 0:
                overall_expense_neg[sign] = (round(x, 2) * -1)
                del overall_expense_pos[sign]
                if overall_expense_pos == {}:
                    overall_expense_pos = None
            else:
                del overall_expense_neg[sign]
                if overall_expense_neg == {}:
                    overall_expense_neg = None

    return render_template("dashboard.html", group_expense_neg=group_expense_neg, group_expense_pos=group_expense_pos, friend_expense_neg=friend_expense_neg, friend_expense_pos=friend_expense_pos, overall_expense_neg=overall_expense_neg, overall_expense_pos=overall_expense_pos)


@app.route('/all_g', methods=["GET", "POST"])
@login_required
def all_g():
    """Renders data for groups depending upon request"""
    user_id = session["user_id"]
    if request.method == 'POST':
        maindb = get_db_conn()
        maincur = maindb.cursor()
        # Group {group_id:[[group_name,currency_sign,net_value],[group_name,currency_sign,net_value]]}
        group_details_owe = {}
        group_details_lent = {}
        group_details_outstanding = {}
        group_details = {}
        # Individual {group_id:[row1,row2,row3...]}
        individual_details = {}
        # settle_groups - {group_id:groupname}
        settled_groups = {}
        user_id_string = str(user_id)
        settled_result = maincur.execute(
            'SELECT group_id,settle FROM summary WHERE lentowe LIKE ? AND group_id IS NOT NULL', ('%'+user_id_string+'%',)).fetchall()
        # Helper lists for settled groups
        settled_list = set()
        unsettled_list = set()
        for result in settled_result:
            group_id = result[0]
            settle = result[1]
            if settle == 0:
                unsettled_list.add(group_id)
                if group_id in settled_list:
                    settled_list.remove(group_id)
            else:
                if group_id not in unsettled_list:
                    settled_list.add(group_id)
        for id in settled_list:
            group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (id,)).fetchone()
            if group_name:
                group_name = group_name[0]
            settled_groups[id] = group_name
        # Create dictionary of Summaries for all groups except settled up groups
        pos_summary = maincur.execute(
            'SELECT group_id,currency,SUM(amount),settle FROM summary WHERE lent_id = ? AND group_id IS NOT NULL AND settle = 0 GROUP BY group_id,currency', (user_id,)).fetchall()
        neg_summary = maincur.execute(
            'SELECT group_id,currency,SUM(amount),settle FROM summary WHERE owe_id = ? AND group_id IS NOT NULL AND settle = 0 GROUP BY group_id,currency', (user_id,)).fetchall()

        pos_summary_o = pos_summary.copy()
        neg_summary_o = neg_summary.copy()

        for pos_ind, pos_row in enumerate(pos_summary):
            for neg_ind, neg_row in enumerate(neg_summary):
                # Find the corresponding LENT OWE for a group/currency when none of them is settled
                if pos_row[0] == neg_row[0] and pos_row[1] == neg_row[1]:
                    group_id = pos_row[0]
                    currency = pos_row[1]
                    currency_sign = currency_pairs[currency]
                    net_value = round((pos_row[2] - neg_row[2]), 2)
                    settle_up = pos_row[3]
                    group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id IS ?', (group_id,)).fetchone()
                    if group_name:
                        group_name = group_name[0]

                    # Delete the values which have are being processed from lists for which we found net difference from lent and owe
                    pos_summary_o.remove(pos_row)
                    neg_summary_o.remove(neg_row)

                    if group_id not in group_details.keys():
                        group_details[group_id] = []

                    if group_id not in group_details_outstanding.keys():
                        group_details_outstanding[group_id] = []

                    # There might be more than 1 currency associated for a group_id, hence lists inside list
                    group_details[group_id].append([group_name, currency_sign, net_value, settle_up])
                    group_details_outstanding[group_id].append([group_name, currency_sign, net_value, settle_up])

                    if net_value < 0:
                        if group_id not in group_details_owe.keys():
                            group_details_owe[group_id] = []
                        group_details_owe[group_id].append([group_name, currency_sign, net_value, settle_up])
                    elif net_value > 0:
                        if group_id not in group_details_lent.keys():
                            group_details_lent[group_id] = []
                        group_details_lent[group_id].append([group_name, currency_sign, net_value, settle_up])

        # Values for which we did not find did not find corresponding owe, add them into group
        for pos_row in pos_summary_o:
            group_id = pos_row[0]
            currency = pos_row[1]
            currency_sign = currency_pairs[currency]
            net_value = round(pos_row[2], 2)
            settle_up = pos_row[3]
            group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id IS ?', (group_id,)).fetchone()
            if group_name:
                group_name = group_name[0]

            if settle_up != 1:
                if group_id not in group_details_outstanding.keys():
                    group_details_outstanding[group_id] = []
                group_details_outstanding[group_id].append([group_name, currency_sign, net_value, settle_up])
            if group_id not in group_details.keys():
                group_details[group_id] = []

            # There might be more than 1 currency associated for a group_id, hence lists inside list
            group_details[group_id].append([group_name, currency_sign, net_value, settle_up])
            if group_id not in group_details_lent.keys():
                group_details_lent[group_id] = []
            group_details_lent[group_id].append([group_name, currency_sign, net_value, settle_up])

        # Values for which we did not find did not find corresponding LENT, add them into group
        for neg_row in neg_summary_o:
            group_id = neg_row[0]
            currency = neg_row[1]
            currency_sign = currency_pairs[currency]
            net_value = round((neg_row[2])*(-1), 2)
            settle_up = neg_row[3]
            group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id IS ?', (group_id,)).fetchone()
            if group_name:
                group_name = group_name[0]
            if settle_up != 1:
                if group_id not in group_details_outstanding.keys():
                    group_details_outstanding[group_id] = []
                group_details_outstanding[group_id].append([group_name, currency_sign, net_value, settle_up])

            if group_id not in group_details.keys():
                group_details[group_id] = []

            # There might be more than 1 currency associated for a group_id, hence lists inside list
            group_details[group_id].append([group_name, currency_sign, net_value, settle_up])

            if group_id not in group_details_owe.keys():
                group_details_owe[group_id] = []
            group_details_owe[group_id].append([group_name, currency_sign, net_value, settle_up])

        # For every group_id in group_details , add individual details of owe/lent for that group
        for group_id in group_details.keys():
            # Make user id string as lentowe is a string that should contain user_id before or after '&'
            user_id_string = str(user_id)
            user_involved_summary = maincur.execute(
                'SELECT currency,lent_id,owe_id,amount,settle FROM summary WHERE lentowe LIKE ? AND group_id = ?', ('%'+user_id_string+'%', group_id)).fetchall()
            for payment in user_involved_summary:
                if payment:
                    currency_name = payment[0]
                    currency_symbol = currency_pairs[currency_name]
                    lent_id = payment[1]
                    owe_id = payment[2]
                    amount = payment[3]
                    rounded_amount = round(amount, 2)
                    settle_ind = payment[4]
                    if lent_id == user_id:
                        friendname = maincur.execute('SELECT username FROM users WHERE id = ?',(owe_id,)).fetchone()
                        friendname = friendname[0]
                        pay_string = '{} owes you {}{}'.format(friendname, currency_symbol, rounded_amount)

                    elif owe_id == user_id:
                        friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (lent_id,)).fetchone()
                        friendname = friendname[0]
                        pay_string = 'you owe {} {}{}'.format(friendname, currency_symbol, rounded_amount)

                    if group_id not in individual_details.keys():
                        individual_details[group_id] = []
                    if settle_ind != 1:
                        individual_details[group_id].append(pay_string)

        if len(group_details) == 0:
            message = 'There are no group expenses yet.'
            maincur.close()
            maindb.close()
            return render_template("all_g.html", message=message)
        if 'all' in request.form:
            maincur.close()
            maindb.close()
            return render_template("all_g.html", group_details=group_details, individual_details=individual_details, settled_groups=settled_groups)
        elif 'outstanding' in request.form:
            maincur.close()
            maindb.close()
            if len(group_details_outstanding) == 0:
                message = 'There are no outstanding balances.'
                return render_template("all_g.html", message=message)
            return render_template("all_g.html", group_details=group_details_outstanding, individual_details=individual_details)
        elif 'owe_to_g' in request.form:
            maincur.close()
            maindb.close()
            if len(group_details_owe) == 0:
                message = 'You dont owe any groups.'
                return render_template("all_g.html", message=message)
            return render_template("all_g.html", group_details=group_details_owe, individual_details=individual_details)
        elif 'lent_to_g' in request.form:
            maincur.close()
            maindb.close()
            if len(group_details_lent) == 0:
                message = 'None of the groups owe you.'
                return render_template("all_g.html", message=message)
            return render_template("all_g.html", group_details=group_details_lent, individual_details=individual_details)


@app.route('/group_transactions', methods=["GET", "POST"])
@login_required
def group_transactions():
    """display transaction details for a paritcular group"""
    user_id = session["user_id"]
    group_id = request.form.get('group_id')
    arr = group_id.split('-')
    g_id = int(arr[1])
    maindb = get_db_conn()
    maincur = maindb.cursor()
    transaction_details = {}
    group_transactions = maincur.execute(
        'SELECT trans_id,description,currency,date,user_id,paid_user_value FROM transactions WHERE group_id = ?  AND paid_user_value > 0 ORDER BY date DESC,trans_id DESC', (g_id,)).fetchall()
    if group_transactions:
        group_transactions = list(group_transactions)
        for transaction in group_transactions:
            trans_id = transaction[0]
            description = transaction[1]
            currency = currency_pairs[transaction[2]]
            x_date = transaction[3]
            date = datetime.strptime(x_date, "%m/%d/%y")
            date = date.strftime("%b %d")
            user = transaction[4]
            # You borrowed you lent string for a transaction
            user_id_string = str(user_id)
            user_involved_summary = maincur.execute(
                'SELECT lent_id,owe_id,amount FROM pay WHERE lentowe LIKE ? AND group_id = ? AND trans_id = ?', ('%'+user_id_string+'%', g_id, trans_id)).fetchall()
            user_amount = 0
            for payment_row in user_involved_summary:
                if payment_row:
                    lent_id = payment_row[0]
                    owe_id = payment_row[1]
                    amount = payment_row[2]
                    if lent_id == user_id:
                        user_amount += amount
                    elif owe_id == user_id:
                        user_amount -= amount

            rounded_amount = round(user_amount, 2)
            if rounded_amount > 0:
                user_string = 'you lent {}{}'.format(currency, rounded_amount)
            elif rounded_amount < 0:
                user_string = 'you borrowed {}{}'.format(currency, ((rounded_amount)*-1))
            else:
                user_string = ''

            # Pay string - who paid for the transaction
            if user == user_id:
                username = 'you'
            else:
                username = maincur.execute('SELECT username FROM users WHERE id = ?', (user,)).fetchone()
                username = username[0]
            paid_user_value = round(transaction[5], 2)
            if trans_id not in transaction_details:
                c = 1
                payment = paid_user_value
                pay_string = '{} paid {}{}'.format(username, currency, paid_user_value)
                transaction_details[trans_id] = [date, description, pay_string, user_string]
            else:
                c += 1
                payment += paid_user_value
                pay_string = '{} people paid {}{}'.format(c,currency,payment)
                transaction_details[trans_id] = [date, description, pay_string, user_string]

        maincur.close()
        maindb.close()
        return render_template('group_transactions.html', group_id=group_id, transaction_details=transaction_details)
    else:
        maincur.close()
        maindb.close()
        message = "There are no transactions yet for this group."
        return render_template('group_transactions.html', message=message)


@app.route('/friend_transactions', methods=["GET", "POST"])
@login_required
def friend_transactions():
    """display transaction details for a paritcular friend"""
    user_id = session["user_id"]
    friend_id = int(request.form.get('friend_id'))
    maindb = get_db_conn()
    maincur = maindb.cursor()
    ng_transaction_details = {}
    g_transaction_details = {}
    # Show seperate transaction for associated group expense and non-group expense for this friend
    # Non-group : Find transactions,amount where you and this friend is involved where group is NULL(pay table), pick date and desc of this transaction from transactions
    non_group_lent = maincur.execute(
        'SELECT trans_id,currency,lent_id,owe_id,amount FROM pay WHERE group_id IS NULL AND lent_id = ? AND owe_id = ? ORDER BY trans_id DESC', (user_id, friend_id)).fetchall()
    non_group_lent = list(non_group_lent)
    non_group_owe = maincur.execute(
        'SELECT trans_id,currency,lent_id,owe_id,amount FROM pay WHERE group_id IS NULL AND lent_id = ? AND owe_id = ? ORDER BY trans_id DESC', (friend_id, user_id)).fetchall()
    non_group_owe = list(non_group_owe)

    for trans in non_group_lent:
        trans_id = trans[0]
        currency = currency_pairs[trans[1]]
        lent_id = trans[2]
        owe_id = trans[3]
        amount = round(trans[4], 2)
        lent_string = 'you lent {}{}'.format(currency, amount)
        transaction_details = maincur.execute(
            'SELECT date,description,user_id,paid_user_value FROM transactions WHERE trans_id = ? AND paid_user_value > 0', (trans_id,)).fetchall()
        if transaction_details:
            transaction_details = list(transaction_details)
        for transaction in transaction_details:
            paid_user_value = round(transaction[3], 2)
            description = transaction[1]
            x_date = transaction[0]
            date = datetime.strptime(x_date, "%m/%d/%y")
            date = date.strftime("%b %d")
            user = transaction[2]
            # Pay string - who paid for the transaction
            if user == user_id:
                username = 'you'
            else:
                username = maincur.execute('SELECT username FROM users WHERE id = ?', (user,)).fetchone()
                username = username[0]

            if trans_id not in ng_transaction_details:
                c = 1
                payment = paid_user_value
                pay_string = '{} paid {}{}'.format(username, currency, paid_user_value)
                ng_transaction_details[trans_id] = [date, description, pay_string, lent_string]
            else:
                c += 1
                payment += paid_user_value
                pay_string = '{} people paid {}{}'.format(c, currency, payment)
                ng_transaction_details[trans_id] = [date, description, pay_string, lent_string]

    for trans in non_group_owe:
        trans_id = trans[0]
        currency = currency_pairs[trans[1]]
        lent_id = trans[2]
        owe_id = trans[3]
        amount = round(trans[4], 2)
        owe_string = 'you owe {}{}'.format(currency,amount)
        transaction_details = maincur.execute(
            'SELECT date,description,user_id,paid_user_value FROM transactions WHERE trans_id = ? AND paid_user_value > 0', (trans_id,)).fetchall()
        if transaction_details:
            transaction_details = list(transaction_details)
        for transaction in transaction_details:
            paid_user_value = round(transaction[3],2)
            description = transaction[1]
            x_date = transaction[0]
            date = datetime.strptime(x_date, "%m/%d/%y")
            date = date.strftime("%b %d")
            user = transaction[2]
            # Pay string - who paid for the transaction
            if user == user_id:
                username = 'you'
            else:
                username = maincur.execute('SELECT username FROM users WHERE id = ?', (user,)).fetchone()
                username = username[0]

            if trans_id not in ng_transaction_details:
                c = 1
                payment = paid_user_value
                pay_string = '{} paid {}{}'.format(username, currency, paid_user_value)
                ng_transaction_details[trans_id] = [date, description, pay_string, owe_string]
            else:
                c += 1
                payment += paid_user_value
                pay_string = '{} people paid {}{}'.format(c, currency, payment)
                ng_transaction_details[trans_id] = [date, description, pay_string, owe_string]

    # Group : Find common-group; last transaction date and trans_id in this group where you were user, (summary)group_name , your status with this friend(borrowed/lent/settled)
    # g_transaction_details {group_id:[groupname,trans_id,date,status]}
    g_transaction_details = {}
    g_owe_transactions = maincur.execute(
        'SELECT * FROM summary WHERE group_id IS NOT NULL AND lent_id = ? AND owe_id = ?', (friend_id, user_id)).fetchall()
    g_owe_transactions = list(g_owe_transactions)
    g_lent_transactions = maincur.execute(
        'SELECT * FROM summary WHERE group_id IS NOT NULL AND lent_id = ? AND owe_id = ?', (user_id, friend_id)).fetchall()
    g_lent_transactions = list(g_lent_transactions)
    g_transactions = g_lent_transactions + g_owe_transactions
    for element in g_transactions:
        group_id = element[0]
        currency = currency_pairs[element[1]]
        lent_id = element[2]
        owe_id = element[3]
        amount = round(element[4], 2)
        settle = element[6]
        group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (group_id,)).fetchone()
        if group_name:
            group_name = group_name[0]
        if settle != 1:
            if owe_id == user_id:
                status = 'you owe {}{}'.format(currency, amount)
            elif lent_id == user_id:
                status = 'you lent {}{}'.format(currency, amount)
        else:
            status = 'settled up in {}'.format(currency)
        t_details = maincur.execute(
            'SELECT MAX(trans_id),MAX(date) FROM transactions WHERE group_id IS ? AND user_id = ?', (group_id, user_id)).fetchone()
        t_details = list(t_details)
        trans_id = t_details[0]
        x_date = t_details[1]
        date = datetime.strptime(x_date, "%m/%d/%y")
        date = date.strftime("%b %d")
        if group_id not in g_transaction_details:
            g_transaction_details[group_id] = [[group_name, trans_id, date, status]]
        else:
            g_transaction_details[group_id].append([group_name, trans_id, date, status])

    maincur.close()
    maindb.close()
    if len(g_transaction_details) == 0 and len(ng_transaction_details) == 0:
        message = "There are no transactions yet for this friend."
        return render_template('friend_transactions.html', message=message)
    return render_template('friend_transactions.html', friend_id=friend_id, g_transaction_details=g_transaction_details, ng_transaction_details=ng_transaction_details)


@app.route('/settle_payment', methods=["GET", "POST"])
@login_required
def settle_payment():
    """confirms settle up of a payment"""
    user_id = session["user_id"]
    maindb = get_db_conn()
    maincur = maindb.cursor()
    primary_key = request.form.get('id')
    group_id,currency,lent_id,owe_id = primary_key.split('&')
    lent_id = int(lent_id)
    owe_id = int(owe_id)
    # Insert activity
    activity_type = 'add_settlement'
    currentDateTime = datetime.now()

    try:
        # Group_id can be None or int - but both are string when split
        group_id = int(group_id)
        try:
            maincur.execute(
                'UPDATE summary SET settle = 1 WHERE group_id = ? AND currency = ? AND lent_id = ? AND owe_id= ?',
                (group_id, currency, lent_id, owe_id))
            maindb.commit()
            settle_amount = maincur.execute(
                'SELECT amount FROM summary WHERE group_id = ? AND currency = ? AND lent_id = ? AND owe_id= ?', (group_id, currency, lent_id, owe_id)).fetchone()
            settle_amount = settle_amount[0]

            # 2 way activity insertion for 1 settlement where involved user in first will be lent_id and in second will be owe_id
            maincur.execute(
                'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                (currentDateTime, user_id, activity_type, lent_id, group_id, lent_id, owe_id, currency, settle_amount))
            maincur.execute(
                'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                (currentDateTime, user_id, activity_type, owe_id, group_id, lent_id, owe_id, currency, settle_amount))
            maindb.commit()

            maincur.close()
            maindb.close()
            return redirect("/")
        except:
            maincur.close()
            maindb.close()
            return 'Error: could not settle transaction.'
    except ValueError:
        # Group_id is None
        group_id = None
        try:
            maincur.execute(
                'UPDATE summary SET settle = 1 WHERE group_id IS NULL AND currency = ? AND lent_id = ? AND owe_id= ?', (currency, lent_id, owe_id))
            maindb.commit()
            # 2 way activity insertion for 1 settlement where involved user in first will be lent_id and in second will be owe_id
            settle_amount = maincur.execute(
                'SELECT amount FROM summary WHERE group_id IS NULL AND currency = ? AND lent_id = ? AND owe_id= ?', (currency, lent_id, owe_id)).fetchone()
            settle_amount = settle_amount[0]

            maincur.execute(
                'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                (currentDateTime, user_id, activity_type, lent_id, group_id, lent_id, owe_id, currency, settle_amount))
            maincur.execute(
                'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                (currentDateTime, user_id, activity_type, owe_id, group_id, lent_id, owe_id, currency, settle_amount))
            maindb.commit()

            maincur.close()
            maindb.close()
            return redirect("/")
        except:
            maincur.close()
            maindb.close()
            return 'Error: could not settle transaction.'


@app.route('/settle_all_payment', methods=["GET", "POST"])
@login_required
def settle_all_payment():
    """settles up all payments for a friend at once"""
    maindb = get_db_conn()
    maincur = maindb.cursor()
    primary_key_list = request.form.get('id')
    remove = "[']\" "
    for char in remove:
        primary_key_list = primary_key_list.replace(char, '')
    clean_primary_key_list = primary_key_list.split(',')
    # Insert activity variables
    user_id = session["user_id"]
    activity_type = 'add_settlement'
    currentDateTime = datetime.now()
    for primary_key in clean_primary_key_list:
        pk_list = primary_key.split('&')
        group_id = pk_list[0]
        currency = pk_list[1]
        lent_id = int(pk_list[2])
        owe_id = int(pk_list[3])

        try:
            # Group_id can be None or int - but both are string when split
            group_id = int(group_id)
            try:
                maincur.execute(
                    'UPDATE summary SET settle = 1 WHERE group_id = ? AND currency = ? AND lent_id = ? AND owe_id= ?', (group_id, currency, lent_id, owe_id))
                maindb.commit()
                # for activity insertion
                settle_amount = maincur.execute(
                    'SELECT amount FROM summary WHERE group_id IS ? AND currency = ? AND lent_id = ? AND owe_id= ?', (group_id, currency, lent_id,owe_id)).fetchone()
                settle_amount = settle_amount[0]

                # 2 way activity insertion for 1 settlement where involved user in first will be lent_id and in second will be owe_id
                maincur.execute(
                    'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                    (currentDateTime, user_id, activity_type, lent_id, group_id, lent_id, owe_id, currency, settle_amount))
                maincur.execute(
                    'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                    (currentDateTime, user_id, activity_type, owe_id, group_id, lent_id, owe_id, currency, settle_amount))
                maindb.commit()

            except:
                maincur.close()
                maindb.close()
                return 'Error: could not settle transaction.'
        except ValueError:
            # Group_id is None
            group_id = None
            try:
                maincur.execute(
                    'UPDATE summary SET settle = 1 WHERE group_id IS NULL AND currency = ? AND lent_id = ? AND owe_id= ?',(currency, lent_id, owe_id))
                maindb.commit()
                # for activity insertion
                settle_amount = maincur.execute(
                    'SELECT amount FROM summary WHERE group_id IS NULL AND currency = ? AND lent_id = ? AND owe_id= ?', (currency, lent_id, owe_id)).fetchone()
                settle_amount = settle_amount[0]
                # 2 way activity insertion for 1 settlement where involved user in first will be lent_id and in second will be owe_id
                maincur.execute(
                    'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                    (currentDateTime, user_id, activity_type, lent_id, group_id, lent_id, owe_id, currency, settle_amount))
                maincur.execute(
                    'INSERT INTO activity (timestamp,doer_id,activity_type,involved_user_id,settle_group_id,settle_lent_id,settle_owe_id,settle_currency,settle_amount) VALUES (?,?,?,?,?,?,?,?,?)',
                    (currentDateTime, user_id, activity_type, owe_id, group_id, lent_id, owe_id, currency, settle_amount))
                maindb.commit()
            except:
                maincur.close()
                maindb.close()
                return 'Error: could not settle transaction.'
    maincur.close()
    maindb.close()
    return redirect('/')


@app.route('/settle_up', methods=["GET", "POST"])
@login_required
def settle_up():
    """shows balances which involve user for settle up of particular group"""
    user_id = session["user_id"]
    user_id_string = str(user_id)
    send_group_id = request.form.get('send_group_id')
    arr = send_group_id.split('-')
    g_id = int(arr[1])
    maindb = get_db_conn()
    maincur = maindb.cursor()
    settle_dic = {}
    user_involved_summary = maincur.execute(
        'SELECT currency,lent_id,owe_id,amount,settle FROM summary WHERE lentowe LIKE ? AND group_id = ?', ('%'+user_id_string+'%', g_id)).fetchall()
    for payment in user_involved_summary:
        if payment:
            currency_name = payment[0]
            currency_symbol = currency_pairs[currency_name]
            lent_id = payment[1]
            owe_id = payment[2]
            amount = payment[3]
            rounded_amount = round(amount, 2)
            settle = payment[4]
            primary_key = str(g_id)+'&'+str(currency_name)+'&'+str(lent_id)+'&'+str(owe_id)
            # If not settled, send it to front end
            if settle == 0:
                if lent_id == user_id:
                    friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (owe_id,)).fetchone()
                    friendname = (friendname[0]).capitalize()
                    pay_string = '{} paid you {}{}'.format(friendname, currency_symbol, rounded_amount)

                elif owe_id == user_id:
                    friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (lent_id,)).fetchone()
                    friendname = (friendname[0]).capitalize()
                    pay_string = 'You paid {} {}{}'.format(friendname, currency_symbol, rounded_amount)

                settle_dic[primary_key] = pay_string

    maincur.close()
    maindb.close()
    if len(settle_dic) == 0:
        settle_message = 'You are all settled up in this group!'
        return render_template('settle.html', settle_message=settle_message)
    else:
        return render_template('settle.html', settle_dic=settle_dic)


@app.route('/friend_settle_up', methods=["GET", "POST"])
@login_required
def friend_settle_up():
    """shows balances which involve user for settle up of particular friend"""
    user_id = session["user_id"]
    user_id_string = str(user_id)
    friend_id = request.form.get('friend_id')
    maindb = get_db_conn()
    maincur = maindb.cursor()
    friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (friend_id,)).fetchone()
    friendname = (friendname[0]).capitalize()
    # Will only show 1 settle up option including group expenses, when these expenses are settled up - update summary table for multiple settled
    settle_dic = {}
    user_lent_summary = maincur.execute(
        'SELECT group_id,currency,lent_id,owe_id,amount,settle FROM summary WHERE lent_id = ? AND owe_id = ?', (user_id, friend_id)).fetchall()
    user_owe_summary = maincur.execute(
        'SELECT group_id,currency,lent_id,owe_id,amount,settle FROM summary WHERE lent_id = ? AND owe_id = ?', (friend_id, user_id)).fetchall()
    user_lent_summary = list(user_lent_summary)
    user_owe_summary = list(user_owe_summary)
    user_involved_summary = user_lent_summary + user_owe_summary
    for payment in user_involved_summary:
        if payment:
            group_id = payment[0]
            currency_name = payment[1]
            currency_symbol = currency_pairs[currency_name]
            lent_id = payment[2]
            owe_id = payment[3]
            amount = payment[4]
            rounded_amount = round(amount, 2)
            settle = payment[5]
            primary_key = str(group_id)+'&'+str(currency_name)+'&'+str(lent_id)+'&'+str(owe_id)
            # If not settled, send it to front end
            if settle == 0:
                if lent_id == user_id:
                    if group_id is None:
                        pay_string = 'In non-group expenses, {} paid you {}{}'.format(
                            friendname, currency_symbol, rounded_amount)
                    else:
                        group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (group_id,)).fetchone()
                        if group_name:
                            group_name = (group_name[0]).capitalize()
                            pay_string = 'In shared group {}, {} paid you {}{} '.format(
                                group_name, friendname, currency_symbol, rounded_amount)

                elif owe_id == user_id:
                    if group_id is None:
                        pay_string = 'In non-group expenses, You paid {} {}{}'.format(friendname, currency_symbol, rounded_amount)
                    else:
                        group_name = maincur.execute('SELECT group_name FROM groups WHERE group_id = ?', (group_id,)).fetchone()
                        if group_name:
                            group_name = (group_name[0]).capitalize()
                            pay_string = 'In shared group {}, You paid {} {}{} '.format(
                                group_name, friendname, currency_symbol, rounded_amount)

                settle_dic[primary_key] = pay_string

    maincur.close()
    maindb.close()
    if len(settle_dic) == 0:
        settle_message = 'You are all settled up with {}!'.format(friendname)
        return render_template('settle.html', settle_message=settle_message)
    else:
        # Make a list of all primarykeys to settle all balances at once
        pk_list = []
        for primary_key in settle_dic.keys():
            pk_list.append(primary_key)
        return render_template('settle.html', settle_dic=settle_dic, pk_list=pk_list)


@app.route('/balances', methods=["GET", "POST"])
@login_required
def balances():
    """shows balances or settle up for a particular group"""
    user_id = session["user_id"]
    send_group_id = request.form.get('send_group_id')
    arr = send_group_id.split('-')
    g_id = int(arr[1])
    maindb = get_db_conn()
    maincur = maindb.cursor()
    balances_list = []
    settle_balances = []
    user_involved_summary = maincur.execute(
        'SELECT currency,lent_id,owe_id,amount,settle FROM summary WHERE group_id = ?', (g_id,)).fetchall()
    for payment in user_involved_summary:
        if payment:
            balance_string = None
            settle_string = None
            currency_name = payment[0]
            currency_symbol = currency_pairs[currency_name]
            lent_id = payment[1]
            owe_id = payment[2]
            amount = payment[3]
            rounded_amount = round(amount, 2)
            settle = payment[4]
            # If not settled, send it to front end

            if lent_id == user_id:
                friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (owe_id,)).fetchone()
                friendname = (friendname[0]).capitalize()
                if settle == 0:
                    balance_string = '{} owes you {}{}'.format(friendname, currency_symbol, rounded_amount)
                else:
                    settle_string = '{} is settled up with you'.format(friendname)
            elif owe_id == user_id:
                friendname = maincur.execute('SELECT username FROM users WHERE id = ?', (lent_id,)).fetchone()
                friendname = (friendname[0]).capitalize()
                if settle == 0:
                    balance_string = 'you owe {} {}{}'.format(friendname, currency_symbol, rounded_amount)
                else:
                    settle_string = 'you are settled up with {}'.format(friendname)
            else:
                lentname = maincur.execute('SELECT username FROM users WHERE id = ?', (lent_id,)).fetchone()
                owename = maincur.execute('SELECT username FROM users WHERE id = ?', (owe_id,)).fetchone()
                lentname = (lentname[0]).capitalize()
                owename = (owename[0]).capitalize()
                if settle == 0:
                    balance_string = '{} owes {} {}{}'.format(owename, lentname, currency_symbol, rounded_amount)
                else:
                    settle_string = '{} is settled up with {}'.format(owename, lentname)
            if balance_string:
                balances_list.append(balance_string)
            elif settle_string:
                settle_balances.append(settle_string)

    maincur.close()
    maindb.close()
    if len(balances_list) == 0 and len(settle_balances) == 0:
        balance_message = 'There are no balances to show!'
        return render_template('balances.html', balance_message=balance_message)
    return render_template('balances.html', balances_list=balances_list, settle_balances=settle_balances)


@app.route('/totals', methods=["GET", "POST"])
@login_required
def totals():
    """shows totals for a particular group"""
    user_id = session["user_id"]
    send_group_id = request.form.get('send_group_id')
    arr = send_group_id.split('-')
    g_id = int(arr[1])
    maindb = get_db_conn()
    maincur = maindb.cursor()
    total_group_spending = 0
    total_you_paid = 0
    your_total_share = 0
    # Helper dic
    group_totals_dic = {}
    # Find transaction values to sum up for total spending
    group_totals = maincur.execute(
        'SELECT trans_id,AVG(total_trans_value),currency FROM transactions WHERE group_id = ? GROUP BY trans_id', (g_id,)).fetchall()
    # Minus individual share from group+individual edge case
    group_totals = list(group_totals)

    for lis in group_totals:
        trans_id = lis[0]
        total_value = lis[1]
        currency = lis[2]
        if currency not in group_totals_dic.keys():
            group_totals_dic[currency] = []
        group_totals_dic[currency].append([trans_id, total_value])

    if len(group_totals) == 0:
        maincur.close()
        maindb.close()
        return render_template('totals.html', total_group_spending=total_group_spending, total_you_paid=total_you_paid, your_total_share=your_total_share)
    # Find paid_user_value for user
    paid_totals = maincur.execute(
        'SELECT trans_id,paid_user_value,currency FROM transactions WHERE group_id = ? AND user_id = ?', (g_id, user_id)).fetchall()
    paid_totals = list(paid_totals)
    # Helper dic
    paid_totals_dic = {}
    for lis in paid_totals:
        trans_id = lis[0]
        paid_value = lis[1]
        currency = lis[2]
        if currency not in paid_totals_dic.keys():
            paid_totals_dic[currency] = []
        paid_totals_dic[currency].append([trans_id, paid_value])

    # Find split_user_value for user
    split_totals = maincur.execute(
        'SELECT trans_id,split_user_value,currency FROM transactions WHERE group_id = ? AND user_id = ?', (g_id, user_id)).fetchall()
    split_totals = list(split_totals)
    # Helper dic
    split_totals_dic = {}
    for lis in split_totals:
        trans_id = lis[0]
        split_value = lis[1]
        currency = lis[2]
        if currency not in split_totals_dic.keys():
            split_totals_dic[currency] = []
        split_totals_dic[currency].append([trans_id, split_value])

    minus_edges = maincur.execute('SELECT trans_id,net_user_value FROM transactions WHERE group_id IS NULL').fetchall()
    minus_edges = list(minus_edges)
    for lis in minus_edges:
        t_id = lis[0]
        net_user_value = lis[1]
        for det in group_totals_dic.values():
            for d in det:
                id = d[0]
                value = d[1]
                # Since net_user_value will always be negative, add it to remove it from group_spending
                if id == t_id:
                    value += net_user_value
        for det in paid_totals_dic.values():
            for d in det:
                id = d[0]
                value = d[1]
                if id == t_id:
                    # Since net_user_value will always be negative, add it to remove it from paid_values for that trans
                    value += net_user_value

    #  totals_dic of the form {currency:[total_group_spending,total_you_paid,your_total_share]}
    totals_dic = {}
    # Sum all values
    for currency, details in group_totals_dic.items():
        for det in details:
            total_group_spending += det[1]
        # Sum all values of group_totals_dic for total group spending
        total_group_spending = round(total_group_spending, 2)
        currency_sign = currency_pairs[currency]
        totals_dic[currency_sign] = [total_group_spending]
        total_group_spending = 0

    for currency, details in paid_totals_dic.items():
        for det in details:
            total_you_paid += det[1]
        # Sum all values of group_totals_dic for total_you_paid
        total_you_paid = round(total_you_paid, 2)
        currency_sign = currency_pairs[currency]
        if currency_sign in totals_dic.keys():
            totals_dic[currency_sign].append(total_you_paid)
        total_you_paid = 0

    for currency, details in split_totals_dic.items():
        for det in details:
            your_total_share += det[1]
        # sum all values of split_totals_dic for your_total_share
        your_total_share = round(your_total_share, 2)
        currency_sign = currency_pairs[currency]
        if currency_sign in totals_dic.keys():
            totals_dic[currency_sign].append(your_total_share)
        your_total_share = 0

    maincur.close()
    maindb.close()
    return render_template('totals.html', totals_dic=totals_dic)


@app.route('/all_f', methods=["GET", "POST"])
@login_required
def all_f():
    """Renders data for friends depending upon request of all/outstanding/owed/lent"""
    user_id = session["user_id"]
    if request.method == 'POST':
        maindb = get_db_conn()
        maincur = maindb.cursor()
        # Friend {friend_id:[[friend_name,currency_sign,net_value],[friend_name,currency_sign,net_value]]}
        friend_details_owe = {}
        friend_details_lent = {}
        friend_details_outstanding = {}
        friend_details = {}

        # settle_friends - {friend_id:friendname}
        settled_friends = {}
        user_id_string = str(user_id)
        settled_result = maincur.execute('SELECT lentowe,settle FROM summary WHERE lentowe LIKE ?',
                                        ('%'+user_id_string+'%',)).fetchall()
        # Helper lists for settled groups
        settled_list = set()
        unsettled_list = set()
        for result in settled_result:
            lentowe = result[0]
            settle = result[1]
            if settle == 0:
                unsettled_list.add(lentowe)
                if lentowe in settled_list:
                    settled_list.remove(lentowe)

            else:
                if lentowe not in unsettled_list:
                    settled_list.add(lentowe)

        # Now check if reverse lentowe in settled list is in unsettled list or not (ex:: '5&7' and '7&5')
        for lentowe in settled_list.copy():
            reverse_relation = list(reversed(lentowe.split('&')))
            for lo in unsettled_list:
                re = lo.split('&')
                if reverse_relation == re:
                    settled_list.remove(lentowe)

        # Now that we have clean settled_list, keep only friend_ids and not relations
        settled_flist = set()
        for relation in settled_list:
            relation_list = relation.split('&')
            for idstr in relation_list:
                if int(idstr) != user_id:
                    settled_flist.add(int(idstr))

        for id in settled_flist:
            friend_name = maincur.execute('SELECT username FROM users WHERE id = ?', (id,)).fetchone()
            if friend_name:
                friend_name = friend_name[0]
            settled_friends[id] = friend_name

        # Create dictionary of Summaries for all friends except settled up friends
        pos_summary = maincur.execute(
            'SELECT owe_id,currency,SUM(amount),settle FROM summary WHERE lent_id = ? AND settle = 0 GROUP BY owe_id,currency', (user_id,)).fetchall()
        neg_summary = maincur.execute(
            'SELECT lent_id,currency,SUM(amount),settle FROM summary WHERE owe_id = ? AND settle = 0 GROUP BY lent_id,currency', (user_id,)).fetchall()
        pos_summary_o = pos_summary.copy()
        neg_summary_o = neg_summary.copy()

        for pos_ind, pos_row in enumerate(pos_summary):
            for neg_ind, neg_row in enumerate(neg_summary):
                # Find the corresponding LENT OWE for a friend/currency when none of them is settled
                if pos_row[0] == neg_row[0] and pos_row[1] == neg_row[1]:
                    friend_id = pos_row[0]
                    currency = pos_row[1]
                    currency_sign = currency_pairs[currency]
                    # Net value will be positive if lent_value is less than owe_value else negative for self
                    net_value = round((pos_row[2] - neg_row[2]), 2)
                    settle_up = pos_row[3]
                    friend_name = maincur.execute('SELECT username FROM users WHERE id = ?', (friend_id,)).fetchone()
                    if friend_name:
                        friend_name = friend_name[0]
                    pos_summary_o.remove(pos_row)
                    neg_summary_o.remove(neg_row)

                    if friend_id not in friend_details.keys():
                        friend_details[friend_id] = []

                    if friend_id not in friend_details_outstanding.keys():
                        friend_details_outstanding[friend_id] = []

                    # There might be more than 1 currency associated for a friend_id, hence lists inside list
                    friend_details[friend_id].append([friend_name, currency_sign, net_value, settle_up])
                    friend_details_outstanding[friend_id].append([friend_name, currency_sign, net_value, settle_up])

                    if net_value < 0:
                        if friend_id not in friend_details_owe.keys():
                            friend_details_owe[friend_id] = []
                        friend_details_owe[friend_id].append([friend_name, currency_sign, net_value, settle_up])
                    elif net_value > 0:
                        if friend_id not in friend_details_lent.keys():
                            friend_details_lent[friend_id] = []
                        friend_details_lent[friend_id].append([friend_name, currency_sign, net_value, settle_up])

        # Values for which we did not find did not find corresponding owe, add them into group
        for pos_row in pos_summary_o:
            friend_id = pos_row[0]
            currency = pos_row[1]
            currency_sign = currency_pairs[currency]
            net_value = round(pos_row[2], 2)
            settle_up = pos_row[3]
            friend_name = maincur.execute('SELECT username FROM users WHERE id = ?', (friend_id,)).fetchone()
            if friend_name:
                friend_name = friend_name[0]

            if settle_up != 1:
                if friend_id not in friend_details_outstanding.keys():
                    friend_details_outstanding[friend_id] = []
                friend_details_outstanding[friend_id].append([friend_name, currency_sign, net_value, settle_up])
            if friend_id not in friend_details.keys():
                friend_details[friend_id] = []

            # There might be more than 1 currency associated for a friend_id, hence lists inside list
            friend_details[friend_id].append([friend_name, currency_sign, net_value, settle_up])
            if friend_id not in friend_details_lent.keys():
                friend_details_lent[friend_id] = []
            friend_details_lent[friend_id].append([friend_name, currency_sign, net_value, settle_up])

        # Values for which we did not find did not find corresponding LENT, add them into friend_details
        for neg_row in neg_summary_o:
            friend_id = neg_row[0]
            currency = neg_row[1]
            currency_sign = currency_pairs[currency]
            net_value = round((neg_row[2])*(-1), 2)
            settle_up = neg_row[3]
            friend_name = maincur.execute('SELECT username FROM users WHERE id = ?', (friend_id,)).fetchone()
            if friend_name:
                friend_name = friend_name[0]
            if settle_up != 1:
                if friend_id not in friend_details_outstanding.keys():
                    friend_details_outstanding[friend_id] = []
                friend_details_outstanding[friend_id].append([friend_name, currency_sign, net_value, settle_up])

            if friend_id not in friend_details.keys():
                friend_details[friend_id] = []

            # There might be more than 1 currency associated for a friend_id, hence lists inside list
            friend_details[friend_id].append([friend_name, currency_sign, net_value, settle_up])

            if friend_id not in friend_details_owe.keys():
                friend_details_owe[friend_id] = []
            friend_details_owe[friend_id].append([friend_name, currency_sign,net_value, settle_up])

        if len(friend_details) == 0:
            message = 'There are no expenses yet.'
            maincur.close()
            maindb.close()
            return render_template("all_f.html", message=message)
        if 'all' in request.form:
            maincur.close()
            maindb.close()
            return render_template("all_f.html", friend_details=friend_details, settled_friends=settled_friends)
        elif 'outstanding' in request.form:
            maincur.close()
            maindb.close()
            if len(friend_details_outstanding) == 0:
                message = 'There are no outstanding balances.'
                return render_template("all_f.html", message=message)
            return render_template("all_f.html", friend_details=friend_details_outstanding)
        elif 'owe_to_f' in request.form:
            maincur.close()
            maindb.close()
            if len(friend_details_owe) == 0:
                message = 'You dont owe any friends.'
                return render_template("all_f.html", message=message)
            return render_template("all_f.html", friend_details=friend_details_owe)
        elif 'lent_to_f' in request.form:
            maincur.close()
            maindb.close()
            if len(friend_details_lent) == 0:
                message = 'None of the friends owe you.'
                return render_template("all_f.html", message=message)
            return render_template("all_f.html", friend_details=friend_details_lent)
