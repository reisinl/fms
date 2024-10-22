# Flask application for Farm Management Simulator
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import mysql.connector
import connect

app = Flask(__name__)
app.secret_key = 'COMP636 S2'

pasture_growth_rate = 65  # kg DM/ha/day
stock_consumption_rate = 14 # kg DM/animal/day

db_connection = None

def getCursor():
    global db_connection

    if db_connection is None or not db_connection.is_connected():
        db_connection = mysql.connector.connect(
            user=connect.dbuser,
            password=connect.dbpass,
            host=connect.dbhost,
            database=connect.dbname,
            autocommit=True
        )
    return db_connection.cursor()

@app.route('/')
def home():
    # Initialize the current date if not set in the session
    if 'curr_date' not in session:
        session['curr_date'] = datetime.now().strftime('%Y-%m-%d')
    curr_date = session['curr_date'] if isinstance(session['curr_date'], str) else session['curr_date'].strftime('%Y-%m-%d')
    curr_date = datetime.strptime(curr_date, '%Y-%m-%d')
    return render_template('home.html', curr_date=curr_date)

@app.route('/mobs')
def mobs():
    cursor = getCursor()
    cursor.execute("""
    SELECT mobs.id, mobs.name, paddocks.name 
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
    SELECT paddocks.id, paddocks.name, paddocks.area, paddocks.dm_per_ha, paddocks.total_dm, mobs.name, 
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
    curr_date = session['curr_date'] if isinstance(session['curr_date'], str) else session['curr_date'].strftime('%Y-%m-%d')
    curr_date = datetime.strptime(curr_date, '%Y-%m-%d')
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

if __name__ == '__main__':
    app.run(debug=True)
