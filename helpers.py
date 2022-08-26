import sqlite3
from flask import redirect, session
from functools import wraps
from string import punctuation

# Using Pset9 function as is for current app
# If a user goes to the site and is not logged in, they should be redirected to the login page to access relevant pages of certain user

def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# Modifying Pset9 function for current app's use
def money(value, currency):
    """Format all values in relevant selected currency from database"""
    return "{}{:.2f}".format(currency, value)


def get_db_conn():
    """Creates database connection"""

    # Open a connection to use SQLite database, create database if not exist already
    db = sqlite3.connect('splitbucks.db', check_same_thread=False)
    # Database connection returns rows that behave as python dictionaries
    db.row_factory = sqlite3.Row
    # Create cursor to use database with python
    return db


def password_criteria(password):
    """check if password is strong"""
    if len(password) < 8:
        error = "\nYour password must contain 8 characters.\n"
        return (error)

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
            error = "\nYour password must contain 8 characters using atleast 1 uppercase, 1 lowercase, 1 digit and 1 special character\n"
            return error
    return 'success'


def get_friendRows(user_id):
    """Get friendIDs and names of logged in user"""
    maindb = get_db_conn()
    maincur = maindb.cursor()
    # Fetch friends data from users table for logged in user - autocomplete for addition to group
    fRows = maincur.execute(
        'SELECT u.id,u.username,u.email FROM users u INNER JOIN friends f ON u.id = f.friend_id WHERE f.user_id = ?',(user_id,)).fetchall()
    friendRows = {}
    for row in fRows:
        friendRows[row[0]] = row[1]
    maincur.close()
    maindb.close()
    return friendRows


def get_DebtRows(user_id):
    """Get friendIDs and names of logged in user along with group_id and groups for autocomplete"""
    friendRows = get_friendRows(user_id)
    maindb = get_db_conn()
    maincur = maindb.cursor()
    # DebtRows has both friend names and group names - both should in autocomplete for expense
    DebtRows = {}
    DebtRows['GROUPS'] = 'GROUPS'
    dRows = maincur.execute(
        'SELECT g.group_id,g.group_name FROM groups g INNER JOIN groups_friends gf ON g.group_id = gf.group_id WHERE gf.user_id = ?',(user_id,)).fetchall()
    for row in dRows:
        # Convert g_id format to g1,g2 instead of f1,f2 to avoid symantic error on receiving back
        key = "g-{}".format(row[0])
        DebtRows[key] = row[1]
    # Add header to list for user ease
    DebtRows['FRIENDS'] = 'FRIENDS'
    DebtRows.update(friendRows)
    maincur.close()
    maindb.close()
    return DebtRows


def check_and_add_friends(user_id, finalsharers):
    """ While adding transaction in table check if all members of transaction are friends of each other. If not - add them"""
    # Generate a list of finalsharers without user_id since user_id has all friends in transaction
    finalsharerlist = []
    flag = False
    for id in finalsharers.keys():
        if id != user_id:
            finalsharerlist.append(id)

    db = get_db_conn()
    cur = db.cursor()
    for index, id in enumerate(finalsharerlist):
        friends_of_friend = cur.execute('SELECT friend_id FROM friends WHERE user_id = ?', (id,)).fetchall()
        friends_of_friend = [row[0] for row in friends_of_friend]
        for user_id_friend in finalsharerlist[index+1:]:
            if user_id_friend not in friends_of_friend:
                cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (id, user_id_friend))
                cur.execute('INSERT INTO friends (user_id,friend_id) VALUES (?,?)', (user_id_friend, id))
                db.commit()
                flag = True
    cur.close()
    db.close()
    return flag