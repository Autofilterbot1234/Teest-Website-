from flask import Flask, request, redirect, url_for, jsonify, render_template
import os
import uuid
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from werkzeug.security import generate_password_hash, check_password_hash # যদিও এটি এখনো ব্যবহৃত হচ্ছে না, তবে নিরাপত্তার জন্য রাখা হয়েছে
from functools import wraps

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Flask Secret Key for session management and security
# In a production environment, set this securely as an environment variable
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

# --- Configuration ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "moviedokan_db"
COLLECTION_NAME = "movies"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# IMPORTANT: For production, hash this password using generate_password_hash()
# and store the hash (e.g., ADMIN_PASSWORD_HASH = generate_password_hash("your_admin_password"))
# Then, use check_password_hash(ADMIN_PASSWORD_HASH, auth.password) for verification.
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# --- MongoDB Connection ---
client = None
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, connectTimeoutMS=30000, socketTimeoutMS=None)
        db = client[DATABASE_NAME]
        movies_collection = db[COLLECTION_NAME]
        movies_collection.create_index([("title", "text")]) # For text search capability
        movies_collection.create_index("slug", unique=True) # Ensure unique URLs for movies
        print("Connected to MongoDB successfully!")
    else:
        print("MONGO_URI not set. MongoDB operations disabled.")
except Exception as e:
    print(f"MongoDB connection error: {e}")
    client = None # Set client to None if connection fails

# --- Genre Cache (Optional, for better performance if displaying genres often) ---
genre_map = {}

def fetch_tmdb_genres():
    """Fetches and caches TMDb movie genres."""
    global genre_map
    if not genre_map and TMDB_API_KEY:
        try:
            response = requests.get(
                f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}",
                timeout=10 # Set a timeout for external API calls
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            genre_map = {genre['id']: genre['name'] for genre in data.get('genres', [])}
            print("TMDb genres cached successfully")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching genres from TMDb: {e}")
        except ValueError: # Catches JSON decoding errors
            print("Error decoding TMDb genre list response.")

fetch_tmdb_genres() # Fetch genres on application startup

# --- Authentication Decorator for Admin Panel ---
def admin_required(f):
    """Decorator to protect admin routes with Basic Auth."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        # For a production app, use password hashing (check_password_hash) here
        if not auth or not (auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions for Database Operations ---
def get_movie_by_slug(slug):
    """Retrieves a single movie by its unique slug."""
    if not client:
        return None
    return movies_collection.find_one({"slug": slug}, {'_id': 0}) # Exclude MongoDB's default _id field

def get_all_movies(limit=20):
    """Retrieves a limited number of all movies."""
    if not client:
        return []
    # Sort by a recent field if available, or just by _id (creation order)
    return list(movies_collection.find({}, {'_id': 0}).limit(limit).sort("_id", -1))

def save_movie(movie_data):
    """Saves a new movie to the database."""
    if not client:
        return False
    try:
        if not movie_data.get("title"):
            print("Error: Movie title is required.")
            return False

        # Ensure all expected fields exist, even if empty
        for k in ['year', 'genre', 'plot', 'poster', 'telegram_link', 'terabox_link']:
            movie_data.setdefault(k, '')

        # Generate a URL-friendly slug from the title
        slug_base = ''.join(c for c in movie_data['title'].lower() if c.isalnum() or c == ' ')
        slug_base = slug_base.replace(' ', '-')[:40] # Limit length for cleaner URLs
        # Append a unique identifier to ensure slug uniqueness
        movie_data['slug'] = f"{slug_base}-{str(uuid.uuid4())[:8]}"

        result = movies_collection.insert_one(movie_data)
        return result.inserted_id is not None
    except Exception as e:
        print(f"Error saving movie: {e}")
        return False

# --- New API Endpoint for TMDb details (for Admin Panel AJAX) ---
@app.route('/fetch_tmdb_details', methods=['GET'])
@admin_required
def fetch_tmdb_details():
    """
    Fetches movie details from TMDb based on a given title.
    Used by the admin panel via AJAX to auto-fill fields.
    """
    title = request.args.get('title')
    if not title or not TMDB_API_KEY:
        return jsonify({}) # Return empty JSON if no title or API key

    movie_details = {}
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
        res = requests.get(search_url, timeout=10).json()

        if res.get('results'):
            # Get details for the first (most relevant) search result
            tmdb_id = res['results'][0]['id']
            details = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}", timeout=10).json()

            # Populate dictionary with TMDb data
            movie_details['year'] = details.get('release_date', '')[:4]
            movie_details['plot'] = details.get('overview', '')
            if details.get('poster_path'):
                movie_details['poster'] = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
            
            genres = [g['name'] for g in details.get('genres', [])]
            movie_details['genre'] = ', '.join(genres)

    except requests.exceptions.RequestException as e:
        print(f"TMDb API request error in /fetch_tmdb_details: {e}")
    except ValueError:
        print("Error decoding TMDb response in /fetch_tmdb_details.")
    except Exception as e:
        print(f"An unexpected error occurred in /fetch_tmdb_details: {e}")
    return jsonify(movie_details)

# --- Routes ---
@app.route('/')
def home():
    """Renders the main homepage with a list of movies."""
    movies = get_all_movies()
    return render_template('index.html', movies=movies)

@app.route('/movie/<slug>')
def movie_detail(slug):
    """Renders the detail page for a specific movie."""
    movie = get_movie_by_slug(slug)
    if not movie:
        return "Movie not found", 404
    return render_template('movie_detail.html', movie=movie)

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_panel():
    """
    Admin panel for adding new movies.
    On POST, it attempts to save the movie data, optionally fetching missing details from TMDb.
    """
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

        # If year or poster are missing, try to fetch from TMDb, but only if API key is set
        # This block is now less critical as the JS in admin.html handles auto-fill,
        # but kept as a fallback for direct POSTs or if JS fails.
        if (not movie_data['year'] or not movie_data['poster'] or not movie_data['plot'] or not movie_data['genre']) and TMDB_API_KEY:
            try:
                search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
                res = requests.get(search_url, timeout=10).json()
                if res.get('results'):
                    tmdb_id = res['results'][0]['id']
                    details = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}", timeout=10).json()
                    
                    # Only update if the field is currently empty in the form data
                    movie_data['year'] = movie_data['year'] or details.get('release_date', '')[:4]
                    movie_data['plot'] = movie_data['plot'] or details.get('overview', '')
                    if details.get('poster_path'):
                        movie_data['poster'] = movie_data['poster'] or f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
                    genres = [g['name'] for g in details.get('genres', [])]
                    movie_data['genre'] = movie_data['genre'] or ', '.join(genres)
            except requests.exceptions.RequestException as e:
                print(f"TMDb API request error during form submission: {e}")
            except ValueError:
                print("Error decoding TMDb response during form submission.")
            except Exception as e:
                print(f"An unexpected error occurred during TMDb fetch on form submission: {e}")

        if save_movie(movie_data):
            return redirect(f"/movie/{movie_data['slug']}")
        else:
            return "Failed to save movie", 500
    # For GET request, render the admin form
    return render_template('admin.html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

