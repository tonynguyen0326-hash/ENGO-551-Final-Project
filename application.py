from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from sqlalchemy import text
from google import genai

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Update your client setup line:
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={'api_version': 'v1'} 
)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'app_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('homepage'))

    return render_template('register.html', hide_nav=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return render_template(
                'login.html',
                success_message='Login successful! Redirecting...',
                redirect_url=url_for('homepage'),
                hide_nav=True
            )

        return render_template(
            'login.html',
            error_message='Incorrect username or password',
            hide_nav=True
        )

    return render_template('login.html', hide_nav=True)

@app.route('/')
@login_required
def index():
    return redirect(url_for('homepage'))

@app.route('/homepage')
@login_required
def homepage():
    return render_template('homepage.html')

@app.route('/study-spot-suggestion')
@login_required
def study_spot_suggestion():
    return render_template('study_spot_suggestion.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('homepage'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password reset successful!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username not found.')

    return render_template('reset_password.html', hide_nav=True)

from flask import jsonify

@app.route('/api/search')
@login_required
def search_spots():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', type=int, default=1000)
    types = request.args.getlist('type')
    
    on_campus = request.args.get('on-campus') == 'true'
    off_campus = request.args.get('off-campus') == 'true'
    
    # Atmosphere filters
    want_quiet = request.args.get('quiet') == 'true'
    want_outlets = request.args.get('outlets') == 'true'
    want_wifi = request.args.get('wifi') == 'true'

    results = []
    params = {'lng': lng, 'lat': lat, 'radius': radius}

    # --- HELPER: BUILD ATMOSPHERE SQL ---
    atmos_conditions = []
    if want_quiet:
        atmos_conditions.append("r.comment ILIKE '%quiet%'")
    if want_outlets:
        atmos_conditions.append("(r.comment ILIKE '%outlet%' OR r.comment ILIKE '%charging%' OR r.comment ILIKE '%plugin%')")
    if want_wifi:
        atmos_conditions.append("(r.comment ILIKE '%wifi%' OR r.comment ILIKE '%wi-fi%' OR r.comment ILIKE '%internet%')")
    
    atmos_sql = " AND " + " AND ".join(atmos_conditions) if atmos_conditions else ""

    # --- 1. LIBRARIES ---
    if 'library' in types:
        if on_campus:
            query = text(f"""
                SELECT DISTINCT ON (u.name) u.name, ST_X(u.coords) as lon, ST_Y(u.coords) as lat, r.comment, r.source
                FROM uni u
                JOIN reddit r ON r.location = u.name
                WHERE (u.name ILIKE '%Library%' OR r.comment ILIKE '%Library%')
                {atmos_sql}
                AND ST_DWithin(u.coords::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
            """)
            res = db.session.execute(query, params)
            for row in res:
                results.append({'name': row.name, 'lat': row.lat, 'lon': row.lon, 'type': 'Campus Library', 'tip': row.comment, 'source': row.source})

        if off_campus:
            # Note: We use LEFT JOIN so we don't hide libraries that don't have reddit tips, 
            # UNLESS the user specifically filtered for atmosphere (which requires a comment).
            join_type = "JOIN" if atmos_conditions else "LEFT JOIN"
            query = text(f"""
                SELECT DISTINCT ON (l.name) l.name, ST_X(l.coords) as lon, ST_Y(l.coords) as lat, r.comment, r.source
                FROM libraries l
                {join_type} reddit r ON r.location = l.name
                WHERE ST_DWithin(l.coords::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
                {atmos_sql}
            """)
            res = db.session.execute(query, params)
            for row in res:
                results.append({'name': row.name, 'lat': row.lat, 'lon': row.lon, 'type': 'Public Library', 'tip': row.comment, 'source': row.source})

    # --- 2. CAFE / FOOD ---
    if 'cafe' in types:
        join_type = "JOIN" if atmos_conditions else "LEFT JOIN"
        sql = f"""
            SELECT DISTINCT ON (f.name) f.name, ST_X(f.coords) as lon, ST_Y(f.coords) as lat, r.comment, r.source
            FROM food f
            {join_type} reddit r ON r.location = f.name
            WHERE ST_DWithin(f.coords::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
            {atmos_sql}
        """
        if on_campus and not off_campus:
            sql += " AND EXISTS (SELECT 1 FROM uni u WHERE ST_DWithin(f.coords::geography, u.coords::geography, 300))"
        elif off_campus and not on_campus:
            sql += " AND NOT EXISTS (SELECT 1 FROM uni u WHERE ST_DWithin(f.coords::geography, u.coords::geography, 300))"

        cafes = db.session.execute(text(sql), params)
        for row in cafes:
            results.append({'name': row.name, 'lat': row.lat, 'lon': row.lon, 'type': 'Cafe', 'tip': row.comment, 'source': row.source})

    # --- 3. CAMPUS SPECIFIC (Classrooms, Halls, Lounges) ---
    if on_campus:
        campus_filters = []
        if 'uni_classroom' in types: campus_filters.append("r.comment ILIKE '%classroom%'")
        if 'uni_hall' in types: campus_filters.append("(r.comment ILIKE '%hallway%' OR r.comment ILIKE '%atrium%')")
        if 'uni_lounges' in types: campus_filters.append("r.comment ILIKE '%lounge%'")

        if campus_filters:
            type_sql = "(" + " OR ".join(campus_filters) + ")"
            query = text(f"""
                SELECT u.name, ST_X(u.coords) as lon, ST_Y(u.coords) as lat, r.comment, r.source
                FROM uni u
                JOIN reddit r ON r.location = u.name
                WHERE {type_sql} {atmos_sql}
                AND ST_DWithin(u.coords::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
            """)
            res = db.session.execute(query, params)
            for row in res:
                results.append({'name': row.name, 'lat': row.lat, 'lon': row.lon, 'type': 'Campus Study Spot', 'tip': row.comment, 'source': row.source})

    return jsonify(results)

@app.route('/api/summarize/<name>')
@login_required
def summarize(name):
    # 1. Fetch all comments for this specific building/cafe
    rows = db.session.execute(
        text("SELECT comment FROM reddit WHERE location = :name"),
        {'name': name}
    ).fetchall()
    
    if not rows:
        return jsonify({"summary": "No student reviews available for this spot yet."})

    # 2. Combine comments into one block of text
    combined_comments = " ".join([row[0] for row in rows])

    # 3. Call Gemini
    prompt = f"""
    Based on these student reviews for '{name}', give a 2-sentence summary.
    Focus on noise levels, outlet availability, and the general vibe.
    Reviews: {combined_comments}
    """
    
    try:
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return jsonify({"summary": response.text})
    except Exception as e:
        print(f"Gemini Error: {e}")
        return jsonify({"summary": "Could not generate summary at this time."}), 500
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)