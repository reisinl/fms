# Flask application for Farm Management Simulator
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import mysql.connector
import connect

app = Flask(__name__)
app.secret_key = 'COMP636 S2'

start_date = datetime(2024,10,29)
pasture_growth_rate = 65    #kg DM/ha/day
stock_consumption_rate = 14 #kg DM/animal/day

db_connection = None

def getCursor():
    """Gets a new dictionary cursor for the database.
    If necessary, a new database connection is created here and used for all
    subsequent to getCursor()."""
    global db_connection
 
    if db_connection is None or not db_connection.is_connected():
        db_connection = mysql.connector.connect(user=connect.dbuser, \
            password=connect.dbpass, host=connect.dbhost,
            database=connect.dbname, autocommit=True)
       
    cursor = db_connection.cursor(buffered=False)   # returns a list
    # cursor = db_connection.cursor(dictionary=True, buffered=False)  # use a dictionary cursor if you prefer
    return cursor

####### New function - reads the date from the new database table
def get_date():
    cursor = getCursor()        
    qstr = "select curr_date from curr_date;"  
    cursor.execute(qstr)        
    curr_date = cursor.fetchone()[0]        
    return curr_date

####### Updated if statement with this line
@app.route("/")
def home():
    # This line:
    curr_date = get_date()
    # Replaces these lines:
    # if 'curr_date' not in session:
    #     session.update({'curr_date': start_date})
    return render_template("home.html", curr_date=curr_date)

####### New function to reset the simulation back to the beginning - replaces reset_date() and clear_date()
##  NOTE: This requires fms-reset.sql file to be in the same folder as app.py
@app.route("/reset")
def reset():
    """Reset data to original state."""
    THIS_FOLDER = Path(__file__).parent.resolve()
    with open(THIS_FOLDER / 'fms-reset.sql', 'r') as f:
        mqstr = f.read()
        for qstr in mqstr.split(";"):
            cursor = getCursor()
            cursor.execute(qstr)
    get_date()
    return redirect(url_for('paddocks'))  

@app.route('/mobs')
def mobs():
    cursor = getCursor()
    cursor.execute("""
    SELECT mobs.id, mobs.name, paddocks.name AS paddock_name
    FROM mobs
    LEFT JOIN paddocks ON mobs.paddock_id = paddocks.id
    ORDER BY mobs.name;
    """)
    mobs = cursor.fetchall()
    return render_template('mobs.html', mobs=mobs)

@app.route('/paddocks')
def paddocks():
    cursor = getCursor()
    cursor.execute("""
    SELECT paddocks.id, paddocks.name, paddocks.area, paddocks.dm_per_ha, paddocks.total_dm, mobs.name AS mob_name,
           (SELECT COUNT(*) FROM stock WHERE stock.mob_id = mobs.id) AS stock_count
    FROM paddocks
    LEFT JOIN mobs ON paddocks.id = mobs.paddock_id
    ORDER BY paddocks.name;
    """)
    paddocks = cursor.fetchall()
    return render_template('paddocks.html', paddocks=paddocks)

@app.route('/move_mob', methods=['GET', 'POST'])
def move_mob():
    cursor = getCursor()

    if request.method == 'POST':
        mob_id = request.form.get('mob_id')
        new_paddock_id = request.form.get('paddock_id')
        # Ensure paddock is available
        cursor.execute("SELECT paddock_id FROM mobs WHERE paddock_id = %s;", (new_paddock_id,))
        if cursor.fetchone() is not None:
            flash('The selected paddock already has a mob.', 'danger')
            return redirect(url_for('move_mob'))
        cursor.execute("UPDATE mobs SET paddock_id = %s WHERE id = %s;", (new_paddock_id, mob_id))
        flash('Mob successfully moved to the new paddock.', 'success')
        return redirect(url_for('mobs'))

    cursor.execute("SELECT id, name FROM mobs WHERE paddock_id IS NOT NULL;")
    mobs = cursor.fetchall()

    cursor.execute("SELECT id, name FROM paddocks WHERE id NOT IN (SELECT paddock_id FROM mobs WHERE paddock_id IS NOT NULL);")
    paddocks = cursor.fetchall()

    return render_template('move_mob.html', mobs=mobs, paddocks=paddocks)

@app.route('/next_day')
def next_day():
    cursor = getCursor()

    # Increment the current date by one day in the session
    curr_date = datetime.strptime(session['curr_date'], '%Y-%m-%d')
    new_date = curr_date + timedelta(days=1)
    session['curr_date'] = new_date.strftime('%Y-%m-%d')

    # Update paddock pasture values based on growth and consumption
    cursor.execute("SELECT id, area, dm_per_ha FROM paddocks;")
    paddocks = cursor.fetchall()

    for paddock in paddocks:
        paddock_id = paddock[0]
        area = paddock[1]
        dm_per_ha = paddock[2]
        growth = area * pasture_growth_rate
        cursor.execute("SELECT COUNT(*) FROM stock WHERE mob_id IN (SELECT id FROM mobs WHERE paddock_id = %s);", (paddock_id,))
        stock_count = cursor.fetchone()[0]
        consumption = stock_count * stock_consumption_rate
        new_dm_per_ha = max(0, dm_per_ha + growth - consumption)
        total_dm = area * new_dm_per_ha
        cursor.execute("UPDATE paddocks SET dm_per_ha = %s, total_dm = %s WHERE id = %s;", (new_dm_per_ha, total_dm, paddock_id))

    flash('Date advanced by one day. Pasture values updated.', 'success')
    return redirect(url_for('paddocks'))

@app.route('/add_paddock', methods=['GET', 'POST'])
def add_paddock():
    cursor = getCursor()

    if request.method == 'POST':
        name = request.form.get('name')
        area = float(request.form.get('area'))
        dm_per_ha = float(request.form.get('dm_ha'))
        total_dm = area * dm_per_ha
        cursor.execute("INSERT INTO paddocks (name, area, dm_per_ha, total_dm) VALUES (%s, %s, %s, %s);", (name, area, dm_per_ha, total_dm))
        flash('Paddock added successfully.', 'success')
        return redirect(url_for('paddocks'))

    return render_template('add_paddock.html')

@app.route('/edit_paddock/<int:paddock_id>', methods=['GET', 'POST'])
def edit_paddock(paddock_id):
    cursor = getCursor()

    if request.method == 'POST':
        area = float(request.form.get('area'))
        dm_per_ha = float(request.form.get('dm_ha'))
        total_dm = area * dm_per_ha
        cursor.execute("UPDATE paddocks SET area = %s, dm_per_ha = %s, total_dm = %s WHERE id = %s;", (area, dm_per_ha, total_dm, paddock_id))
        flash('Paddock updated successfully.', 'success')
        return redirect(url_for('paddocks'))

    cursor.execute("SELECT id, name, area, dm_per_ha FROM paddocks WHERE id = %s;", (paddock_id,))
    paddock = cursor.fetchone()

    return render_template('edit_paddock.html', paddock=paddock)

if __name__ == '__main__':
    app.run(debug=True)
