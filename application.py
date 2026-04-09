from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import re
import requests
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
    api_key=os.getenv("GEMINI_API_KEY") 
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


@app.route('/api/search')
@login_required
def search_spots():
    # --- 1. Get request params ---
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', type=int, default=1000)
    types = request.args.getlist('type')

    on_campus = request.args.get('on-campus') == 'true'
    off_campus = request.args.get('off-campus') == 'true'

    want_quiet = request.args.get('quiet') == 'true'
    want_outlets = request.args.get('outlets') == 'true'
    want_wifi = request.args.get('wifi') == 'true'
    # Added transit param
    want_transit = request.args.get('transit') == 'true'

    params = {'lat': lat, 'lng': lng, 'radius': radius}
    results = []

    # --- 2. Build ATMOSPHERE filter ---
    atmos_conditions = []
    if want_quiet:
        atmos_conditions.append("(r.comment ILIKE '%quiet%' OR r.location ILIKE '%library%')")
    if want_wifi:
        if not on_campus:
            atmos_conditions.append("(r.comment ILIKE '%wifi%' OR r.comment ILIKE '%wi-fi%' OR r.comment ILIKE '%internet%')")
    if want_outlets:
        if on_campus:
            atmos_conditions.append("(r.comment ILIKE '%outlet%' OR r.comment ILIKE '%charging%' OR r.comment ILIKE '%plug%' OR r.location ILIKE '%library%' OR r.location ILIKE '%classroom%')")
        else:
            atmos_conditions.append("(r.comment ILIKE '%outlet%' OR r.comment ILIKE '%charging%' OR r.comment ILIKE '%plug%')")

    atmos_sql = ""
    if len(atmos_conditions) > 0:
        atmos_sql = " AND (" + " AND ".join(atmos_conditions) + ")"

    # --- NEW: Transit Filter logic ---
    # This only adds a rule to the DB if the box is checked
    transit_filter_sql = ""
    if want_transit:
        transit_filter_sql = """
            AND EXISTS (
                SELECT 1 FROM transit ts  -- Changed from transit_stops to transit
                WHERE ST_DWithin({alias}.coords::geography, ts.coords::geography, 500) -- Changed point to coords
            )
        """

    join_type = "JOIN" if len(atmos_conditions) > 0 else "LEFT JOIN"

    # --- 3. Helpers ---
    def campus_sql(table_alias):
        if on_campus and not off_campus:
            return f"AND EXISTS (SELECT 1 FROM uni u WHERE ST_DWithin({table_alias}.coords::geography, u.coords::geography, 300))"
        elif off_campus and not on_campus:
            return f"AND NOT EXISTS (SELECT 1 FROM uni u WHERE ST_DWithin({table_alias}.coords::geography, u.coords::geography, 300))"
        return ""

    def within(alias):
    # Changed: removed the 'point' check because your transit table uses 'coords'
        return f"ST_DWithin({alias}.coords::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)"
    
    # --- 4. LIBRARIES ---
    if 'library' in types:
        if on_campus:
            query = f"""
                SELECT DISTINCT ON (u.name) u.name, ST_X(u.coords) AS lon, ST_Y(u.coords) AS lat, r.comment, r.source
                FROM uni u JOIN reddit r ON r.location = u.name
                WHERE (u.name ILIKE '%library%' OR r.comment ILIKE '%library%')
                AND {within('u')} {transit_filter_sql.format(alias='u')} {atmos_sql}
            """
            rows = db.session.execute(text(query), params)
            for r in rows:
                results.append({'name': r.name, 'lat': r.lat, 'lon': r.lon, 'type': 'Campus Library', 'tip': r.comment, 'source': r.source})

        if off_campus:
            query = f"""
                SELECT DISTINCT ON (l.name) l.name, ST_X(l.coords) AS lon, ST_Y(l.coords) AS lat, r.comment, r.source
                FROM libraries l {join_type} reddit r ON r.location = l.name
                WHERE {within('l')} {transit_filter_sql.format(alias='l')} {atmos_sql}
            """
            rows = db.session.execute(text(query), params)
            for r in rows:
                results.append({'name': r.name, 'lat': r.lat, 'lon': r.lon, 'type': 'Public Library', 'tip': r.comment, 'source': r.source})

    # --- 5. CAFES ---
    if 'cafe' in types:
        query = f"""
            SELECT DISTINCT ON (f.name) f.name, ST_X(f.coords) AS lon, ST_Y(f.coords) AS lat, r.comment, r.source
            FROM food f {join_type} reddit r ON r.location = f.name
            WHERE {within('f')} {campus_sql('f')} {transit_filter_sql.format(alias='f')} {atmos_sql}
        """
        rows = db.session.execute(text(query), params)
        for r in rows:
            results.append({'name': r.name, 'lat': r.lat, 'lon': r.lon, 'type': 'Cafe', 'tip': r.comment, 'source': r.source})

    # --- 6. CAMPUS SPOTS ---
    if on_campus:
        campus_types = []
        if 'uni_classroom' in types: campus_types.append("r.comment ILIKE '%classroom%'")
        if 'uni_hall' in types: campus_types.append("(r.comment ILIKE '%hallway%' OR r.comment ILIKE '%atrium%')")
        if 'uni_lounges' in types: campus_types.append("r.comment ILIKE '%lounge%'")

        if campus_types:
            type_sql = " OR ".join(campus_types)
            query = f"""
                SELECT u.name, ST_X(u.coords) AS lon, ST_Y(u.coords) AS lat, r.comment, r.source
                FROM uni u JOIN reddit r ON r.location = u.name
                WHERE ({type_sql}) AND {within('u')} {transit_filter_sql.format(alias='u')} {atmos_sql}
            """
            rows = db.session.execute(text(query), params)
            for r in rows:
                results.append({'name': r.name, 'lat': r.lat, 'lon': r.lon, 'type': 'Campus Study Spot', 'tip': r.comment, 'source': r.source})

    # --- 7. FETCH TRANSIT STOPS FOR MAP ---
    transit_stops = []
    if want_transit:
        # This now correctly uses ts.coords thanks to the helper update above
        t_query = f"""
            SELECT name, ST_X(coords) as lon, ST_Y(coords) as lat 
            FROM transit ts 
            WHERE {within('ts')}
        """
        t_rows = db.session.execute(text(t_query), params)
        for tr in t_rows:
            transit_stops.append({
                'name': tr.name, 
                'lat': tr.lat, 
                'lon': tr.lon, 
                'type': 'transit_stop'
            })

    return jsonify({'study_spots': results, 'transit_stops': transit_stops})

    
def get_vibe_profile(vibe_key):
    vibes = {
        'finals_solo': {
            'label': 'Finals Study Solo',
            'categories': 'education.library,education.university,catering.cafe.coffee_shop',
            'conditions': 'internet_access',
            'keywords': ['quiet', 'library', 'solo', 'focus']
        },
        'group_study': {
            'label': 'Group Study',
            'categories': 'education.library,catering.cafe,catering.food_court,education.university',
            'conditions': 'internet_access',
            'keywords': ['group', 'discussion', 'table', 'meeting']
        },
        'capstone_project': {
            'label': 'Capstone Project',
            'categories': 'office.coworking,education.library,catering.cafe.coffee_shop,education.university',
            'conditions': 'internet_access',
            'keywords': ['project', 'wifi', 'workspace', 'team']
        },
        'cozy_cafe': {
            'label': 'Cozy Cafe Vibes',
            'categories': 'catering.cafe,catering.cafe.coffee_shop,catering.cafe.dessert,catering.cafe.tea',
            'conditions': 'internet_access',
            'keywords': ['cozy', 'cafe', 'warm', 'relaxed']
        },
        'hanging_out': {
            'label': 'When You Say You’re Studying But You’re Really Hanging Out',
            'categories': 'catering.cafe.bubble_tea,catering.cafe.dessert,catering.food_court,catering.cafe',
            'conditions': '',
            'keywords': ['social', 'hangout', 'fun', 'friends']
        }
    }

    return vibes.get(vibe_key, vibes['finals_solo'])


def categories_to_label(categories):
    if not categories:
        return 'Study Spot'

    text = categories[0]
    text = text.replace('.', ' ').replace('_', ' ').title()
    return text


def extract_json_from_text(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\{.*\})', text, re.S)
        if match:
            return json.loads(match.group(1))
        raise


def build_gemini_top_three(vibe, places):
    if not places:
        return {
            'title': f'Best 3 for {vibe["label"]}',
            'summary': 'No strong vibe matches showed up yet. Try a bigger search radius or another mood.',
            'top_three': [],
            'ranked_places': []
        }

    # Build JSON-safe input for LLM
    places_json = []
    for place in places:
        places_json.append({
            "name": place.get("name", "Unknown"),
            "address": place.get("address", "Address unavailable"),
            "type": place.get("type", "Unknown"),
            "distance": place.get("distance", 0),
            "categories": place.get("categories", [])
        })

    prompt = f"""
You are an assistant that ranks study spots based on a selected vibe.

### STRICT RULES
- You MUST return ONLY valid JSON.
- You MUST NOT invent any attributes, categories, amenities, or details.
- You MUST NOT add new fields.
- You MUST NOT infer features not explicitly present in the input.
- You MUST NOT create new places.
- You MUST use ONLY the fields provided in the JSON array.

### RANKING RULES
Rank places using this exact priority order:
1. Category match with preferred categories
2. Keyword alignment with vibe keywords
3. Distance (closer is better)
4. Type relevance

### INPUT
Vibe label: {vibe['label']}
Vibe keywords: {vibe.get('keywords', [])}
Preferred categories: {vibe.get('categories', '')}
Preferred conditions: {vibe.get('conditions', '')}

Here is the JSON array of candidate places:
{json.dumps(places_json, indent=2)}

### OUTPUT FORMAT (STRICT)
Return ONLY this JSON structure:

{{
  "title": "Best 3 for {vibe['label']}",
  "summary": "string",
  "top_three": [
    {{
      "name": "string",
      "address": "string",
      "type": "string",
      "distance": number,
      "reason": "string"
    }}
  ],
  "ranked_places": [
    "Place Name 1",
    "Place Name 2",
    "Place Name 3"
  ]
}}
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )

        parsed = extract_json_from_text(response.text.strip())

        # Build full ranked list
        ranked_names = parsed.get("ranked_places", [])
        name_to_place = {p["name"]: p for p in places}
        ranked_full = [name_to_place[n] for n in ranked_names if n in name_to_place]

        parsed["top_three"] = parsed.get("top_three", [])[:3]
        parsed["ranked_full"] = ranked_full

        return parsed

    except Exception as e:
        print(f"Gemini error: {e}")
        
        import traceback
        traceback.print_exc()


        # Fallback: sort by distance
        sorted_places = sorted(places, key=lambda p: p['distance'])
        fallback_top_three = sorted_places[:3]
        fallback_top_ten = sorted_places[:10]

        return {
            "title": f"Best 3 for {vibe['label']} (Fallback)",
            "summary": "AI ranking unavailable. Showing closest matches.",
            "top_three": [
                {
                    "name": p["name"],
                    "address": p["address"],
                    "type": p["type"],
                    "distance": p["distance"],
                    "reason": "Closest match available (AI unavailable)"
                }
                for p in fallback_top_three
            ],
            "ranked_full": fallback_top_ten
        }





@app.route('/api/geoapify-vibe-spots')
@login_required
def geoapify_vibe_spots():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', type=int, default=2000)
    vibe_key = request.args.get('vibe', default='finals_solo')

    if lat is None or lng is None:
        return jsonify({'error': 'Missing location coordinates.'}), 400

    api_key = os.getenv('GEOAPIFY_API_KEY')
    if not api_key:
        return jsonify({'error': 'Missing GEOAPIFY_API_KEY in .env'}), 400

    vibe = get_vibe_profile(vibe_key)

    params = {
        'categories': vibe['categories'],
        'filter': f'circle:{lng},{lat},{radius}',
        'bias': f'proximity:{lng},{lat}',
        'limit': 20,
        'lang': 'en',
        'apiKey': api_key
    }

    if vibe['conditions']:
        params['conditions'] = vibe['conditions']

    try:
        response = requests.get(
            'https://api.geoapify.com/v2/places',
            params=params,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        features = data.get('features', [])
        places = []

        for feature in features:
            props = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            coords = geometry.get('coordinates', [None, None])

            if coords[0] is None or coords[1] is None:
                continue

            mapped = {
                'name': props.get('name') or props.get('formatted') or 'Unnamed Place',
                'address': props.get('formatted') or props.get('address_line1') or 'Address unavailable',
                'type': categories_to_label(props.get('categories')),
                'distance': props.get('distance') or 0,
                'lat': coords[1],
                'lng': coords[0],
                'categories': props.get('categories') or [],
                'place_id': props.get('place_id') or ''
            }

            places.append(mapped)

        gemini_box = build_gemini_top_three(vibe, places)
        top_three = gemini_box.get('top_three', [])

        gemini_box = build_gemini_top_three(vibe, places)

        return jsonify({
            "vibe_label": vibe["label"],
            "top_three": gemini_box.get("top_three", []),
            "top_ten": gemini_box.get("ranked_full", [])[:10],
            "all_places": places,
            "gemini_box": gemini_box
        })


    except requests.RequestException as e:
        return jsonify({'error': f'Geoapify request failed: {str(e)}'}), 500
        
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)