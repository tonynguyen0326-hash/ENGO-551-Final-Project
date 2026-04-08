### ENGO 551 - Advanced Geospatial Topics 
### Final Project
# Study Spot Finder
**Authors**: Sneha Dubey, Tony Nguyen, Antenaina Rakotoarison

## Description
A web application that helps users discover study spots near their location based on specific filters or general vibe preferences. The project combines local geospatial data, crowd-sourced Reddit comments, campus buildings, transit stops, and external API searches to recommend libraries, cafes, and other study-friendly venues.

## Features
- User authentication with registration, login, logout, and password reset
- Protected homepage and study spot suggestion pages
- Endpoint to query local study spots with filters like quiet, Wi-Fi, outlets, campus/off-campus, and transit access
- Endpoint to fetch additional places from Geoapify and score them by study vibe
- Interactive leaflet map that displays location markers
- Auto-creates database tables on startup if they do not exist
- Data import helper for CSV files in the `data/` folder

## Setup

1. Install dependencies:

```bash
pip install flask flask_sqlalchemy flask_login python-dotenv requests google-cloud-genai
```

2. Create a `.env` file with:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost/dbname
GEOAPIFY_API_KEY=your_geoapify_api_key
GEMINI_API_KEY=your_gemini_api_key
```

3. Initialize the database schema using `create.sql` and/or run the app once to create tables automatically.

4. Import CSV data (optional but recommended):

```bash
python import.py
```

5. Start the app:

```bash
python application.py
```

## Main Pages

- `GET /register` — Registration form
- `GET /login` — Login form
- `GET /homepage` — Main landing page after login
- `GET /study-spot-suggestion` — Study spot suggestion interface
- `GET /reset-password` — Reset password form

## Request and Response Examplse

### 1. Search Local Study Spots

`GET /api/search`

Query parameters:

- `lat` (float): Latitude of search center
- `lng` (float): Longitude of search center
- `radius` (int, default `1000`): Search radius in meters
- `type` (repeatable): `library`, `cafe`, `uni_classroom`, `uni_hall`, `uni_lounges`
- `on-campus` (`true`/`false`)
- `off-campus` (`true`/`false`)
- `quiet` (`true`/`false`)
- `outlets` (`true`/`false`)
- `wifi` (`true`/`false`)
- `transit` (`true`/`false`)

This endpoint searches local Postgres/PostGIS tables and Reddit-derived comments, then returns matching study spots plus nearby transit stops when requested.

Example request:

```bash
curl -G "http://localhost:5000/api/search" \
  --data-urlencode "lat=43.4723" \
  --data-urlencode "lng=-80.5401" \
  --data-urlencode "radius=1500" \
  --data-urlencode "type=cafe" \
  --data-urlencode "type=library" \
  --data-urlencode "on-campus=true" \
  --data-urlencode "quiet=true" \
  --data-urlencode "wifi=true" \
  --data-urlencode "transit=true"
```

Example response:

```json
{
  "study_spots": [
    {
      "name": "Dana Porter Library",
      "lat": 43.4725,
      "lon": -80.5431,
      "type": "Campus Library",
      "tip": "Quiet study sections and plenty of outlets.",
      "source": "reddit"
    },
    {
      "name": "Graduate House Cafe",
      "lat": 43.4708,
      "lon": -80.5405,
      "type": "Cafe",
      "tip": "Good Wi-Fi and study-friendly atmosphere.",
      "source": "reddit"
    }
  ],
  "transit_stops": [
    {
      "name": "UW Student Rec",
      "lat": 43.4711,
      "lon": -80.5420,
      "type": "transit_stop"
    }
  ]
}
```

### 2. Geoapify Vibe-Based Place Search

`GET /api/geoapify-vibe-spots`

Query parameters:

- `lat` (float): Latitude of the search center
- `lng` (float): Longitude of the search center
- `radius` (int, default `2000`): Radius in meters
- `vibe` (string, default `finals_solo`): One of
  - `finals_solo`
  - `group_study`
  - `capstone_project`
  - `cozy_cafe`
  - `hanging_out`

This endpoint calls Geoapify to find places matching a vibe profile, scores them by keyword/category/distance, and returns a top-three summary with Gemini-generated copy.

Example request:

```bash
curl -G "http://localhost:5000/api/geoapify-vibe-spots" \
  --data-urlencode "lat=43.4723" \
  --data-urlencode "lng=-80.5401" \
  --data-urlencode "radius=1200" \
  --data-urlencode "vibe=cozy_cafe"
```

Example response:

```json
{
  "vibe_label": "Cozy Cafe Vibes",
  "top_three": [
    {
      "name": "The Common Ground Cafe",
      "address": "123 College St",
      "type": "Catering Cafe",
      "distance": 450,
      "lat": 43.4738,
      "lng": -80.5412,
      "score": 42,
      "stars": "★★★★★",
      "categories": ["catering.cafe", "internet_access"],
      "place_id": "abc123"
    }
  ],
  "all_places": [
    {
      "name": "The Common Ground Cafe",
      "address": "123 College St",
      "type": "Catering Cafe",
      "distance": 450,
      "lat": 43.4738,
      "lng": -80.5412,
      "score": 42,
      "stars": "★★★★★",
      "categories": ["catering.cafe", "internet_access"],
      "place_id": "abc123"
    }
  ],
  "gemini_box": {
    "title": "Best 3 for Cozy Cafe Vibes",
    "summary": "These cozy cafes are perfect for reading, sipping warm drinks, and staying focused with strong Wi-Fi and relaxed atmosphere."
  }
}
```

## Database and Data

- `application.py` uses SQLAlchemy and Flask-Login
- `create.sql` contains the database schema for tables such as `food`, `libraries`, `transit`, `uni`, and `reddit`
- `import.py` loads CSV data from `data/` into the database

## Notes

- The app requires a logged-in user for the protected routes and API endpoints.
- The `/api/geoapify-vibe-spots` endpoint requires a valid `GEOAPIFY_API_KEY` in `.env`.
- The Gemini integration uses `GEMINI_API_KEY` to generate the top-three summary box.

## Example User Flow

1. Register a new user at `/register`
2. Login at `/login`
3. Visit `/study-spot-suggestion`
4. Use the app UI or the API to query study spots with custom filters

Enjoy exploring study spots with location-aware recommendations and vibe-based suggestions!