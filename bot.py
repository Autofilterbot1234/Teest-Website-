from flask import Flask, request, redirect, url_for, jsonify, render_template_string
import os
import uuid
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Load .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# Config
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "moviedokan_db"
COLLECTION_NAME = "movies"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# MongoDB
client = None
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, connectTimeoutMS=30000, socketTimeoutMS=None)
        db = client[DATABASE_NAME]
        movies_collection = db[COLLECTION_NAME]
        movies_collection.create_index([("title", "text")])
        movies_collection.create_index("slug", unique=True)
        print("✅ Connected to MongoDB!")
    else:
        print("⚠️ MONGO_URI not set.")
except Exception as e:
    print(f"MongoDB connection error: {e}")
    client = None

# Genres cache
genre_map = {}
def fetch_tmdb_genres():
    global genre_map
    if not genre_map and TMDB_API_KEY:
        try:
            res = requests.get(
                f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}", timeout=10
            )
            res.raise_for_status()
            data = res.json()
            genre_map = {g['id']: g['name'] for g in data.get('genres', [])}
        except Exception as e:
            print(f"Genre fetch failed: {e}")
fetch_tmdb_genres()

# Auth Decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

# HTML Templates
base_html = '''<!DOCTYPE html>
<html><head><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{css}</style></head><body>{content}</body></html>'''

index_css = '''body { font-family: sans-serif; background: #f9f9f9; margin:0; }
.header { background: #c62828; color:white; padding:15px; text-align:center; }
.notice-bar { background: #d32f2f; color:white; padding:10px; text-align:center; font-size:14px; }
.button-section { display:flex; flex-wrap:wrap; justify-content:center; gap:10px; padding:15px; }
.btn { padding:12px 20px; border:none; border-radius:4px; color:white; font-weight:bold; text-align:center; text-decoration:none; }
.btn-red { background:#d32f2f; } .btn-blue { background:#1976d2; } .btn-purple { background:#7b1fa2; }
.movie-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:15px; padding:15px; }
.movie-card { background:white; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1); transition:0.3s; }
.movie-card:hover { transform:translateY(-5px); }
.movie-poster { width:100%; height:240px; object-fit:cover; }
.movie-info { padding:10px; }
.footer { background:#212121; color:white; text-align:center; padding:15px; margin-top:20px; }'''

admin_html = '''<html><head><title>Admin Panel</title>
<style>body {font-family:Arial; margin:20px;} input,textarea{width:100%;padding:8px;margin-bottom:10px;}
button{background:#4CAF50;color:white;padding:10px 15px;border:none;cursor:pointer;}</style></head><body>
<h1>Add New Movie</h1>
<form method="POST">
<input type="text" name="title" placeholder="Title" required>
<input type="text" name="year" placeholder="Year">
<input type="text" name="genre" placeholder="Genre">
<textarea name="plot" placeholder="Plot"></textarea>
<input type="text" name="poster" placeholder="Poster URL">
<input type="text" name="telegram" placeholder="Telegram Link">
<input type="text" name="terabox" placeholder="Terabox Link">
<button type="submit">Add Movie</button>
</form></body></html>'''

# Helpers
def get_movie_by_slug(slug):
    if not client:
        return None
    return movies_collection.find_one({"slug": slug}, {'_id': 0})

def generate_movie_cards(movies):
    cards = []
    for movie in movies:
        cards.append(f'''
        <a href="/movie/{movie['slug']}" class="movie-card">
            <img src="{movie.get('poster', '')}" class="movie-poster">
            <div class="movie-info">
                <h3>{movie['title']}</h3>
                <p>{movie.get('year', '')} | {movie.get('genre', '')}</p>
            </div>
        </a>''')
    return '\n'.join(cards)

def get_all_movies(limit=20):
    if not client:
        return []
    return list(movies_collection.find({}, {'_id': 0}).limit(limit))

def save_movie(movie_data):
    if not client:
        return False
    try:
        if not movie_data.get("title"):
            return False
        for k in ['year', 'genre', 'plot', 'poster', 'telegram_link', 'terabox_link']:
            movie_data.setdefault(k, '')
        slug_base = ''.join(c for c in movie_data['title'].lower() if c.isalnum() or c == ' ')
        slug_base = slug_base.replace(' ', '-')[:40]
        movie_data['slug'] = f"{slug_base}-{str(uuid.uuid4())[:8]}"
        result = movies_collection.insert_one(movie_data)
        return result.inserted_id is not None
    except Exception as e:
        print(f"Error saving movie: {e}")
        return False

# Routes
@app.route('/')
def home():
    movies = get_all_movies()
    return render_template_string(
        base_html.format(
            title="MovieDokan - Home", css=index_css,
            content=f'''
            <div class="header"><h1>MOVIE DOKAN</h1></div>
            <div class="notice-bar">Join our Telegram for updates</div>
            <div class="button-section">
                <a href="#" class="btn btn-red">Adult & Bangla Dubbed</a>
                <a href="https://t.me/your_channel" class="btn btn-blue" target="_blank">Join Telegram</a>
                <a href="#" class="btn btn-purple">Ads Free Website</a>
                <a href="#" class="btn btn-blue">How To Download</a>
            </div>
            <div class="movie-grid">{generate_movie_cards(movies)}</div>
            <div class="footer"><p>© 2025 MovieDokan</p></div>
            '''
        )
    )

@app.route('/movie/<slug>')
def movie_detail(slug):
    movie = get_movie_by_slug(slug)
    if not movie:
        return "Movie not found", 404
    return render_template_string(
        base_html.format(
            title=f"{movie['title']} | MovieDokan",
            css='''
            body { font-family: Arial; padding: 20px; }
            .movie-container { max-width: 800px; margin: 0 auto; }
            .movie-poster { max-width: 300px; float: left; margin-right: 20px; }
            .download-btn { display:inline-block;padding:10px 15px;background:#d32f2f;color:white;text-decoration:none;border-radius:4px;margin:5px;}
            ''',
            content=f'''
            <div class="movie-container">
                <img src="{movie.get('poster', '')}" class="movie-poster">
                <h1>{movie['title']} ({movie.get('year', '')})</h1>
                <p><strong>Genre:</strong> {movie.get('genre', '')}</p>
                <p>{movie.get('plot', '')}</p>
                <div style="clear: both; padding-top: 20px;">
                    <h3>Download Links:</h3>
                    <a href="{movie.get('telegram_link', '#')}" class="download-btn" target="_blank">
                        <i class="fab fa-telegram"></i> Telegram</a>
                    <a href="{movie.get('terabox_link', '#')}" class="download-btn" target="_blank">
                        <i class="fas fa-download"></i> Terabox</a>
                </div>
            </div>
            '''
        )
    )

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_panel():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            return "Title is required", 400
        movie_data = {
            'title': title,
            'year': request.form.get('year', '').strip(),
            'genre': request.form.get('genre', '').strip(),
            'plot': request.form.get('plot', '').strip(),
            'poster': request.form.get('poster', '').strip(),
            'telegram_link': request.form.get('telegram', '').strip(),
            'terabox_link': request.form.get('terabox', '').strip()
        }

        # Auto-fetch missing fields from TMDb
        if (not movie_data['year'] or not movie_data['poster']) and TMDB_API_KEY:
            try:
                search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
                res = requests.get(search_url, timeout=10).json()
                if res.get('results'):
                    tmdb_id = res['results'][0]['id']
                    details = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}").json()
                    movie_data['year'] = details.get('release_date', '')[:4] or movie_data['year']
                    movie_data['plot'] = details.get('overview', '') or movie_data['plot']
                    if details.get('poster_path'):
                        movie_data['poster'] = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
                    genres = [g['name'] for g in details.get('genres', [])]
                    movie_data['genre'] = ', '.join(genres) or movie_data['genre']
            except Exception as e:
                print(f"TMDb fetch error: {e}")

        if save_movie(movie_data):
            return redirect(f"/movie/{movie_data['slug']}")
        else:
            return "Failed to save movie", 500

    return admin_html

@app.route('/api/tmdb')
def tmdb_proxy():
    title = request.args.get('title')
    if not title:
        return jsonify({'error': 'title param required'}), 400
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
        res = requests.get(url, timeout=10).json()
        if not res.get('results'):
            return jsonify({'error': 'No results'}), 404
        movie = res['results'][0]
        details = requests.get(f"https://api.themoviedb.org/3/movie/{movie['id']}?api_key={TMDB_API_KEY}").json()
        genres = [g['name'] for g in details.get('genres', [])]
        return jsonify({
            'title': details.get('title'),
            'year': details.get('release_date', '')[:4],
            'genre': ', '.join(genres),
            'plot': details.get('overview', ''),
            'poster': f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}" if details.get('poster_path') else ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False') == 'True')
