import os
import uuid
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from functools import wraps

# Flask modules
from flask import Flask, request, redirect, url_for, jsonify, render_template

# Load environment variables from .env file
# This should be at the very top to ensure all environment variables are loaded before use.
load_dotenv()

app = Flask(__name__)

# Flask Secret Key for session management and security
# IMPORTANT: In a production environment, set FLASK_SECRET_KEY securely as an environment variable.
# Example: FLASK_SECRET_KEY=your_very_long_and_random_string_here
# If not set, a random one is generated on each start, which is okay for development but not for production
# where sessions might need to persist across restarts.
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

# --- Configuration ---
# Get API keys and database URIs from environment variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Define database and collection names
DATABASE_NAME = "moviedokan_db"
COLLECTION_NAME = "movies"

# Admin credentials for basic authentication
# IMPORTANT: For production, hash the ADMIN_PASSWORD using werkzeug.security.generate_password_hash()
# and store the hash (e.g., ADMIN_PASSWORD_HASH = generate_password_hash("your_admin_password")).
# Then, use check_password_hash(ADMIN_PASSWORD_HASH, auth.password) for verification.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123") # Plain text for simplicity in this example

# --- MongoDB Connection ---
client = None # Initialize client as None
try:
    if MONGO_URI:
        # Connect to MongoDB with timeout settings
        client = MongoClient(MONGO_URI, connectTimeoutMS=30000, socketTimeoutMS=None)
        db = client[DATABASE_NAME]
        movies_collection = db[COLLECTION_NAME]
        
        # Create indexes for efficient querying
        movies_collection.create_index([("title", "text")]) # For text search capability
        movies_collection.create_index("slug", unique=True) # Ensure unique URLs for movies
        print("Connected to MongoDB successfully!")
    else:
        print("MONGO_URI not set. MongoDB operations will be disabled.")
except Exception as e:
    # Print specific error if connection fails
    print(f"MongoDB connection error: {e}")
    client = None # Ensure client remains None if connection fails

# --- Genre Cache (Optional, for better performance if displaying genres often) ---
genre_map = {}

def fetch_tmdb_genres():
    """Fetches and caches TMDb movie genres."""
    global genre_map
    # Fetch only if TMDB_API_KEY is available and genre_map is empty
    if not genre_map and TMDB_API_KEY:
        try:
            response = requests.get(
                f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}",
                timeout=10 # Set a timeout for external API calls
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            genre_map = {genre['id']: genre['name'] for genre in data.get('genres', [])}
            print("TMDb genres cached successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching genres from TMDb: {e}")
        except ValueError: # Catches JSON decoding errors
            print("Error decoding TMDb genre list response.")
        except Exception as e:
            print(f"An unexpected error occurred during genre fetch: {e}")

fetch_tmdb_genres() # Fetch genres on application startup

# --- Authentication Decorator for Admin Panel ---
def admin_required(f):
    """Decorator to protect admin routes with Basic Auth."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        # Basic authentication check
        # For production, use password hashing (e.g., check_password_hash) here.
        if not auth or not (auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD):
            # Return unauthorized response with WWW-Authenticate header
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions for Database Operations ---
def get_movie_by_slug(slug):
    """Retrieves a single movie by its unique slug."""
    if not client: # Check if MongoDB client is connected
        return None
    return movies_collection.find_one({"slug": slug}, {'_id': 0}) # Exclude MongoDB's default _id field for cleaner output

def get_all_movies(limit=20):
    """Retrieves a limited number of all movies, sorted by creation date."""
    if not client: # Check if MongoDB client is connected
        return []
    # Sort by _id in descending order to get most recent movies first
    return list(movies_collection.find({}, {'_id': 0}).limit(limit).sort("_id", -1))

def save_movie(movie_data):
    """Saves a new movie to the database."""
    if not client: # Check if MongoDB client is connected
        return False
    try:
        if not movie_data.get("title"):
            print("Error: Movie title is required to save.")
            return False

        # Ensure all expected fields exist, even if empty, before inserting
        for k in ['year', 'genre', 'plot', 'poster', 'telegram_link', 'terabox_link']:
            movie_data.setdefault(k, '')

        # Generate a URL-friendly slug from the title
        slug_base = ''.join(c for c in movie_data['title'].lower() if c.isalnum() or c == ' ')
        slug_base = slug_base.replace(' ', '-') # Replace spaces with hyphens
        slug_base = slug_base.strip('-') # Remove leading/trailing hyphens
        slug_base = slug_base[:40] # Limit length for cleaner URLs

        # Append a unique identifier to ensure slug uniqueness, crucial for MongoDB unique index
        movie_data['slug'] = f"{slug_base}-{str(uuid.uuid4())[:8]}"

        result = movies_collection.insert_one(movie_data)
        return result.inserted_id is not None # Return True if insertion was successful
    except Exception as e:
        print(f"Error saving movie to MongoDB: {e}")
        return False

# --- API Endpoint for TMDb details (for Admin Panel AJAX) ---
@app.route('/fetch_tmdb_details', methods=['GET'])
@admin_required # Protect this endpoint with admin authentication
def fetch_tmdb_details():
    """
    Fetches movie details from TMDb based on a given title.
    This endpoint is called by the admin panel via AJAX to auto-fill form fields.
    """
    title = request.args.get('title') # Get title from query parameters
    if not title or not TMDB_API_KEY:
        return jsonify({}) # Return empty JSON if no title or API key is provided

    movie_details = {} # Dictionary to store fetched details
    try:
        # Search TMDb for the movie title
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
        res = requests.get(search_url, timeout=10).json()

        if res.get('results'):
            # Get details for the first (most relevant) search result
            tmdb_id = res['results'][0]['id']
            details = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}", timeout=10).json()

            # Populate dictionary with TMDb data, using empty string as fallback
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
    return jsonify(movie_details) # Return fetched details as JSON

# --- Main Routes ---
@app.route('/')
def home():
    """Renders the main homepage with a list of movies."""
    movies = get_all_movies() # Fetch movies from MongoDB
    return render_template('index.html', movies=movies) # Render index.html template

@app.route('/movie/<slug>')
def movie_detail(slug):
    """Renders the detail page for a specific movie using its slug."""
    movie = get_movie_by_slug(slug) # Retrieve movie by slug
    if not movie:
        return "Movie not found", 404 # Return 404 if movie not found
    return render_template('movie_detail.html', movie=movie) # Render movie_detail.html template

@app.route('/admin', methods=['GET', 'POST'])
@admin_required # Protect the admin panel
def admin_panel():
    """
    Admin panel for adding new movies.
    Handles both GET (display form) and POST (submit form) requests.
    """
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            return "Title is required", 400 # Require title for submission

        movie_data = {
            'title': title,
            'year': request.form.get('year', '').strip(),
            'genre': request.form.get('genre', '').strip(),
            'plot': request.form.get('plot', '').strip(),
            'poster': request.form.get('poster', '').strip(),
            'telegram_link': request.form.get('telegram', '').strip(),
            'terabox_link': request.form.get('terabox', '').strip()
        }

        # This block serves as a fallback: If a user submits the form directly without
        # JavaScript filling the fields, or if TMDb fetch through JS fails for some reason,
        # the server will attempt to fetch missing details from TMDb before saving.
        if (not movie_data['year'] or not movie_data['poster'] or not movie_data['plot'] or not movie_data['genre']) and TMDB_API_KEY:
            try:
                search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"
                res = requests.get(search_url, timeout=10).json()
                if res.get('results'):
                    tmdb_id = res['results'][0]['id']
                    details = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}", timeout=10).json()
                    
                    # Update fields only if they are currently empty in the submitted form data
                    movie_data['year'] = movie_data['year'] or details.get('release_date', '')[:4]
                    movie_data['plot'] = movie_data['plot'] or details.get('overview', '')
                    if details.get('poster_path'):
                        movie_data['poster'] = movie_data['poster'] or f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
                    genres = [g['name'] for g in details.get('genres', [])]
                    movie_data['genre'] = movie_data['genre'] or ', '.join(genres)
            except requests.exceptions.RequestException as e:
                print(f"TMDb API request error during form submission fallback: {e}")
            except ValueError:
                print("Error decoding TMDb response during form submission fallback.")
            except Exception as e:
                print(f"An unexpected error occurred during TMDb fallback fetch: {e}")

        if save_movie(movie_data):
            return redirect(f"/movie/{movie_data['slug']}") # Redirect to the new movie's detail page
        else:
            return "Failed to save movie", 500 # Return error if save fails
    # For GET request, render the admin form
    return render_template('admin.html') # Render admin.html template

if __name__ == '__main__':
    # Get port from environment variable, default to 5000
    port = int(os.getenv('PORT', 5000))
    # Run the Flask application
    # debug=True is good for development, but should be False in production
    app.run(host='0.0.0.0', port=port, debug=True)

