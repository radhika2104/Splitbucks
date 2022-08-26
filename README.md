# Split bucks
#### Video Demo:  <https://youtu.be/bMv6fa_Cwyk>
#### Description: A responsive web app for keeping track of shared expenses. It removes hassle by grouping payments with other individuals and groups.

## Features and App Design

Once user **login/ signup** is done on homepage, below Navigation tabs will be visible in header.

#### Split Bucks Homepage 

- Shows all activity where user was involved including creating groups, adding friends, adding expenses and settling balances with others.
- In any settlement activity, shows whether user paid/received a certain amount.
- In any expense activity, shows whether user lent/borrowed a certain amount.
- Activity is sorted by recent.


#### Dashboard

- **Summary**
    
     Shows total expenses in all groups, all friends outside groups and overall total expenses.

- **Groups**
    
    Groups tab shows below reports of expenses with relevant groups.
    - *All groups*

        Shows group wise friend wise lent/owed amount, and overall amount user lent/owed in that group for all groups including groups where all expenses are settled.
    - *Outstanding Balances*
        
        Shows group wise friend wise lent/owed amount, and overall amount user lent/owed in that group for groups excluding settled groups.
    - *Groups you owe*

        Shows group wise friend wise amount where user owe, and overall user is owed in that group for all groups user owes to.
    - *Groups that owe you*

        Shows group wise friend wise amount that user lent, and overall user lent in that group for all groups that user lent to.

    For every group in above reports, user can see:
        
    - each expense view(who paid and how much user owe/lent in that transaction)
    - Group totals: total group expenditure, total user paid in a group, user's total share in a group
    - Group Balances: Who owes whom in a group and who all are settled with each other
    - Settle: Using settle, User can settle expenses with friends involved in this group
- **Friends**

    Friends tab shows below reports of expenses with relevant option selected.

    - *All friends*

        Shows friend wise amount amount lent or owed including friends with whom all expenses are settled. This includes (group + non-group ) total expense with particular friend.
    - *Outstanding Balances*

        Shows friend wise amount amount lent or owed excluding friends with whom all expenses are settled. This includes (group + non-group ) total expense with particular friend.
    - *Friends you owe*

        Shows friends that user owes amount to. This includes (group + non-group ) total expense with particular friend.
    - *Friends that owe you*

        Shows friends that user lent amount to. This includes (group + non-group ) total expense with particular friend.

    For every friend in above reports, user can see:
        
    - each expense view(who paid and how much user owe/lent to that friend in that transaction) and total expense of a shared group if any
    - Settle: Using settle, User can settle expenses with this friend for all non-group and group expenses or both together wherever user was involved with this friend.


#### Add Expense

- Allows adding friends to split expenses.
- Allows adding groups to split expenses with multiple people at once like a trip/ flatmates group.
- Add expense with a group/ multiple friends/ a group and friend both at once with notes, images, description.
- Expense can be added in any currency.
- Expense can be paid and shared by multiple people involved in expense.
- Expenses can be split equally or unequally by percentage, shares or exact amount allocation.

#### Your Account

- Displays user account details including user username and email.
- Allows users to change username, email or password.


## Contents

This section contains essence of folders & file in the project.

### app.py

app.py is the logic design to render templates for each of the front end HTML pages while working with the database.

At beginning of app.py, the modules make required imports and configures flask application, flask sessions and flask mail.

Multiple table creation requests for database are entered here which are only implemented the first time i.e. when tables dont exist by virtue of CREATE TABLE IF NOT EXISTS.

A global currency_pairs dictionary is declared which is used throughout the app for working with currencies.

Below are the functions in app.py:

- **after_request(response)**: To disable caching in Python Flask, sets the response headers to disable cache

- **("/")** routes to **index()**: if user_id is in session, app renders to activity.html, else it renders index.html
    - before routing to activity.html, this function queries the entire activity table for the user_id as involved_user_id
    - based on filter of 5 types of activities: create_profile, add_friend, add_group, add_transaction and add_settlement, it queries database to send activity_description to activity.html

- **"(/login")** routes to **login()**:
    - GET request: renders login.html with email and password inputs
    - POST request: when user fills login credentials, validates emailID and password from database to render user account

- **("/logout")** routes to **logout()**: clears session dictionary of flask to logout a user

- **("/signup")** routes to **signup()**: 
    - GET request: renders signup.html to sign up a user with username, valid email, and password
    - POST request: validates if email is unique, password matches strength criteria and registers user into users table. Also, sends an email to user on successful registeration.

- **("/account")** routes to **account()**: 
    - GET request: renders account details of user (name/email) and option to change password
    - POST request: fetches changes made by user at frontend, validates changes such as email, current password, new password strength and makes changes in database if a valid edit is made by user

- **("/expense_addfriend")** routes to **expense_addfriend()**: 
    - GET request: renders friend names for autocomplete of adding friends on ajax request from expense.html
    - POST request: adds a friend. Fetches and validates username and email entered by user for a friend, adds friend into database and activity type
        - **("/expense_query")** routes to **expense_query()**: adds a friend in database when user is represented with a query to confirm user with display of emailID of a friend to add as a friend. This happens in response to when user enters a username only to add as a friend.
        
- **("/expense_addgroup")** routes to **expense_addgroup()**: 
    - GET request: renders friend names for autocomplete of adding groups and existing friends on ajax request from expense.html
    - POST request: adds a multiple friendnames using bootstrap tokenfield and creates a group with groupname and friendnames fetched from client. Fetches and validates usernames entered by user for a friend and IDs , adds groupname to groups table and friends associated in that group to groups_friends into database and activity type for 'add_group' in activity table

- **("/expense")** routes to **expense()**: 
    - GET request: renders friend names, groupnames for autocomplete of adding existing friends, groups to an expense on ajax request from expense.html
    - POST request: 
        - grabs final sharers in an expense from friends and groups entered in an expense 
        - renders relevant html page on ajax request if 'paid by','split by shares','split by percentages','split by exact amount' and 'split equally' is selected on expense form
        - **("/expense_check_total")** routes to **expense_check_total()**: ajax request sent to check value/amount paid/split for each user to match sum total paid
        - **("/expense_check_percent")** routes to **expense_check_percent()**: ajax request sent to check percent allocation for each user totals to 100%
        - if 'save' is selected by on expense form, all information of expense is fetched from client including expense value, paid amounts by all users, split value for all users, net value for all users if owed or lent and all relevant data is entered into transaction table
        - data is also entered into activity table to later render in activity.html
        - data is made in form of relationship dictionary in form of lender and ower for that transaction to insert into pay table which is used to update summary table for net amount lent/owed among friends group_wise where all non-group transaction are grouped together under NULL.
        
- **("/dashboard")** routes to **dashboard()**: 
    - GET request: renders dashboard.html which displays:
        - group expenses: summary table is queried for sum of amount where user is lent_id or owed_id where group_id is not null. Queries is processed for lent/owe seperately for net amounts.
        - non-group expenses: summary table is queried similarly as group expenses but group_id is NULL
        - total expenses: both the group_expenses and non-expenses are summed up.
        - **("/all_g")** routes to **all_g()**:
            - renders relevant html page on ajax request if 'all groups','outstanding balances','groups you owe' and 'groups that owe you' is selected from side navigation on dashboard.html
            - for all such pages dictionary is created for relavant groups in form of net lent/owed amount for each group and net lent/owed amount for each individual with you in that group
            - all such pages, render group_wise details, when one such group is selected, it renders **'/group_transactions'** which routes to **group_transactions()**
            - **group_transactions()**: renders individual expenses for that group with amount user lent/borrowed
        - **("/all_f")** routes to **all_f()**:
            - renders relevant html page on ajax request if 'all friends','outstanding balances','friends you owe' and 'friends that owe you' is selected from side navigation on dashboard.html
            - for all such pages dictionary is created for relavant friends in form of net lent/owed amount for each friend including any group expenses where friend and user are involved
            - all such pages, render friend_wise details, when one such friend is selected, it renders **'/friend_transactions'** which routes to **friend_transactions()**
            - **friend_transactions()**: renders individual expenses for that friend with amount user lent/borrowed and a total lent/borrowed in each common group
            - for group and non-group transactions for a friend are fetched seperately, lent/owed are fetched seperately and processed to front end as display for both are different
            - Design choice made: it was decided to pull in group and non-group transactions seperately since they had different user interface at front end. However, it is still felt that all should have been fed together to client for sort by recent expense, irrespective of group or non-group. Same is mentioned in scope of project later.

- **("/settle_up")** routes to **settle_up()**:
    - shows balances which involve user for settle up of particular group by quering summary table in '/group_transactions' on '/dashboard'
    - renders settle.html page which includes a 'settle now' button which leads to '/settle_payment'

- **("/friend_settle_up")** routes to **friend_settle_up()**:
    - shows balances which involve user for settle up of particular friend by quering summary table in '/friend_transactions' on '/dashboard'
    - displays balances seperately for particular groups, and together for non-group expenses with that friend
    - renders settle.html page which includes a 'settle now' button which leads to '/settle_payment'
    - Here, settle.html page also includes a 'settle all at once' button which leads to '/settle_all_payment'. User can settle all payments with that friends at once.

- **("/settle_payment")** routes to **settle_payment()**: 
    - settles payment for a friend (lent/owed) by fetching primary key of relationship from client for which settle request is made.
    - settlement is made in summary table for that primary key (primary_key is saved as a unqiue relationship of group_id&currency&lent_id&owe_id)
    - activity is saved as a settlement twice for both involved users

- **("/settle_all_payment")** routes to **settle_all_payment()**: 
    - works in same way as settle_payment() except it settles all payments in settlediv for a particular friend all at once by sending a list of id's to backend instead of a single id.

- **("/balances")** routes to **balances()**: 
    - shows outstanding balances or settled up balances for all users of particular group in '/group_transactions' on '/dashboard'
    - queries summary table for results 

- **("/totals")** routes to **totals()**: 
    - For a particular group, shows currency wise total expenditure, total paid by user, total share of a user in '/group_transactions' on '/dashboard'
    - queries transactions table for results 

### /templates/

Templates contains html pages.

- **expense.html**: 
    - allows adding friends by username or email or both, 
    - adding groups with existing friends using autocomplete(use of bootstrap tokenfield for multiple entries in one input box) for friends
    - allows adding expense with friends and groups using autocomplete (use of bootstrap tokenfield for multiple entries in one input box)
    - on click of **'paid by you'** on expense page sends an ajax request to backend to fetch involved users-id which is rendered to **paidby.html** in #paidbydiv div
    - on click of **'split equally'** user gets an option to select how to split - equally or unequally, by percentages, by  exact amounts or by shares. This data for selection is rendered in #splitdiv.
    - **equallydiv.html** is rendered in #equallydiv for display of amounts of amount is split equally
    - **amountdiv.html** is rendered in #amountdiv for display of input boxes to fetch data from user on how to split with exact amounts
    - **percentdiv.html** is rendered in #percentdiv for display of input boxes to fetch data from user on how to split with percentages
    - **sharediv.html** is rendered in #sharediv for display of input boxes to fetch data from user on how to split with shares of each user involved

- **dashboard.html**:
    - shows main dashboard summary of groups, friends and overall expenses
    - contains divs for other summaries which can be accessed through side navigation
    - side navigation has following links to:
        - **all_g.html** : rendered from buttons of 'all groups','outstanding balances', 'groups you owe' and 'groups that owe you'. Based on relevant data retrieval on ajax request, app.py sends to relevant div (#all_g,#outstanding_g,#owe_to_g,#lent_to_g)
        - on click of a particular group on all_g.html leads to ajax response from app.py to **group_transactions.html** feeded to div (#particular_g on dashboard.html)
        - **all_f.html** : rendered from buttons of 'all friends','outstanding balances', 'friends you owe' and 'friends that owe you'. Based on relevant data retrieval on ajax request, app.py sends to relevant div (#all_f,#outstanding_f,#owe_to_f,#lent_to_f)
        - on click of a particular friend on all_f.html leads to ajax response from app.py to **friend_transactions.html** feeded to div (#particular_f on dashboard.html)
        - on click of **settle** on group_transactions.html or friend_transactions.html adds **settle.html** to #settlediv for showing expenses that are outstanding for settlement for that particular group or friend
        - on click of **balances** on group_transactions.html adds **balances.html** to #balancesdiv for showing expenses that are outstanding for settlement for that particular group for all members of that group
        - on click of **totals** on group_transactions.html adds **totals.html** to #totalsdiv for showing group totals (expenditure,paid,share)

- **activity.html**: displays the activities where user was involved including transactions, settlements, adding groupes or friends.
- **account.html**: displays account details to user and allows change while checking validity of email and password
- **layout.html**: contains header with main navigation tabs of 'dashboard', 'add expense', 'your account' etc. with main body and footer. This layout is extended for all other templates.
- **login.html**: shows a login page with email and password, displays error if any while login
- **signup.html**: asks for username, email, password to signup user, displays error if any while signup and checks for email validity using javascript
- **index.html**: homepage before login. Shows animation of main banner and purpose of app to user. Allows signup/login.
- **error.html**: renders error from ajax requests in a div allocated for the success/error output on expense.html

### helpers.py

Contains helpers functions such as:

- **login_required**: decorates route to require login first if not logged in. Essential, if we add feature if auto log out in some time.
- **money**: formats all values in relevant selected currency from database
- **get_db_conn**: creates database connection
- **password_criteria**: checks if password is strong enough i.e. user password must contain 8 characters using atleast 1 uppercase, 1 lowercase, 1 digit and 1 special character.
- **get_friendRows**: gets friendID and friend names of logged in user
- **get_DebtRows**: gets friendIDs and friend names of logged in user along with group_id and groups for autocomplete feature of expense page
- **check_and_add_friends**: While adding transaction in table, checks if all members of transaction are friends of each other, if not it adds them as friends

### splitbucks.db

Database contains all essential tables required to maintain the app records.

Tables contained in database are:

- **users**: contains user details such as name, email, password
- **friends**: contains a relationship of friendship among users i.e. user_id and friend_id
- **groups**: contains group_names
- **groups_friends**: contains friend_id in each group_name
- **transactions**: contains transaction detail for each field when an expense is added, including description, total_amount, net_amount for each user, split_amount for each user, paid_amount for each user etc.
- **pay**: for each transaction, contains who owes/lent a certain amount for that transaction
- **summary**: for each lender and ower shows total amount grouped by currency and group_id. Also shows if that amount is settled(1) or not(0)
- **activity**: there are 5 activity types - create_profile, add_friend, add_group, add_transaction and add_settlement for which data is accumulated in this table to display for each activity on homepage.

### requirements.txt

Contains all modules to be imported(as required by flask)

### /static/

Contains icons used to design app, a common css style sheet for all html files 


### /static/images

Contains images loaded by user for transaction. The database saves this file location while saving the transaction.

## Deployment

To deploy this project run

```
  python3 -m flask run
```

In order to ensure that project runs only in Python version 3.0
Python3 is critical as logic for ordered dictionaries has been taken into account while programming.

## Scope

Due to limited time and non-essential nature of below features, they were not implemented.

However, if added, below features will improve user experience.

- Allow view,edit and delete of each expense on click from summary reports
- Show amount or percentage left from total while entering bill share split/pay split on expense page 
- Individual expenses/Transactions in summary reports are visible in order of lent and owed. Instead, they can be displayed sorted by recent like activity page.
- Groups can have an additional feature of simplify debts. Example: If A has to pay B and B has to pay C, A can directly pay C.

## Lessons Learned

- Importance of abstraction, encapsulation, DRY, crisp functions as project attains scale.
- Importance of commenting
- Importance of spending time on design, visualization and algorithm so that time on re-writing/ bug handling is reduced.
- Making a real world complex app for the first time despite never having learned flask, javascript, HTML and CSS prior to CS50.

## Technologies used

- Web Framework: Flask
- Backend Language: Python3
- Database System: Sqlite3
- Client Side Language: Javascript, Jquery, Ajax
- Markup/ Web Template Engine: HTML, Jinja
- Style Sheets: CSS, Bootstrap

## Inspired By

Splitwise <https://secure.splitwise.com/>

The idea was to implement everything learned in this course and implement learnings as close as possible to a real world app so that maximum focus is on learning logic, programmer's mindset and technologies involved.