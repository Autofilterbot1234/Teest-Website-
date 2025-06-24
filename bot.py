from flask import Flask, request, redirect, url_for, jsonify
import os, json, uuid
import requests
from dotenv import load_dotenv # For loading environment variables
from pymongo import MongoClient # For MongoDB
from urllib.parse import quote_plus # For safely encoding URL parameters

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
# Get API Key and MongoDB URI from environment variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "moviedokan_db" # You can choose your database name
COLLECTION_NAME = "movies"

# --- Global variable to store genre map (to avoid repeated API calls) ---
genre_map = {}

# --- MongoDB Connection ---
client = None # Initialize client as None
try:
    if MONGO_URI: # Only try to connect if URI is provided
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        movies_collection = db[COLLECTION_NAME]
        print("Connected to MongoDB successfully!")
    else:
        print("MONGO_URI is not set. MongoDB operations will fail.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    client = None # Ensure client is None if connection fails

# --- Function to fetch and cache TMDb Genres ---
def fetch_tmdb_genres():
    global genre_map
    if genre_map: # If already fetched, return
        return

    if not TMDB_API_KEY:
        print("TMDB_API_KEY not set. Cannot fetch genres.")
        return

    genre_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}"
    try:
        response = requests.get(genre_url)
        response.raise_for_status()
        data = response.json()
        if data and data.get('genres'):
            genre_map = {genre['id']: genre['name'] for genre in data['genres']}
            print("TMDb Genres fetched and cached.")
        else:
            print("Failed to fetch genres from TMDb.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TMDb genres: {e}")

# Call this function once at app startup
with app.app_context(): # Run this within the app context
    fetch_tmdb_genres()

# --- HTML Templates (admin_html will have significant changes) ---
# No change needed for index, search, movie HTML for now, focus on admin_html
index_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MovieDokan - Official</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            background-color: #f0f2f5;
            color: #333;
        }}
        .header {{
            background-color: #222;
            color: #fff;
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 1.2em;
        }}
        .header .logo {{
            flex-grow: 1;
            text-align: center;
            font-weight: bold;
            font-size: 1.4em;
        }}
        .header .icon {{
            font-size: 1.5em;
            cursor: pointer;
        }}
        .notice-bar {{
            background-color: #dc3545; /* Red */
            color: #fff;
            padding: 8px 15px;
            text-align: center;
            font-size: 0.9em;
            animation: blink 1s infinite alternate; /* Simple blink effect */
        }}
        @keyframes blink {{
            from {{ opacity: 1; }}
            to {{ opacity: 0.7; }}
        }}
        .button-section {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            padding: 15px 10px;
            gap: 10px;
        }}
        .button-section .btn {{
            flex: 1 1 calc(50% - 20px); /* Two buttons per row on mobile */
            max-width: 250px;
            padding: 12px 15px;
            border: none;
            border-radius: 5px;
            color: #fff;
            font-weight: bold;
            text-align: center;
            text-decoration: none;
            font-size: 0.95em;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            transition: transform 0.2s;
        }}
        .button-section .btn:hover {{
            transform: translateY(-2px);
        }}
        .btn.red {{ background-color: #dc3545; }}
        .btn.blue {{ background-color: #007bff; }}
        .btn.purple {{ background-color: #6f42c1; }}
        .domain-notice {{
            background-color: #ffc107; /* Yellow */
            color: #333;
            padding: 10px 15px;
            text-align: center;
            font-size: 0.9em;
            margin-bottom: 15px;
            border-radius: 5px;
            margin: 10px 15px; /* Added margin */
        }}
        .gaza-banner {{
            background-color: #333; /* Dark background as seen in screenshot */
            color: #fff;
            padding: 15px 10px;
            text-align: center;
            font-size: 1.1em;
            font-weight: bold;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .gaza-banner img {{
            height: 30px; /* Adjust as needed */
            margin-right: 10px;
            border-radius: 50%; /* If circular image */
        }}
        .content-section {{
            padding: 0 15px;
        }}
        .section-header {{
            background-color: #c0392b; /* Darker red for section header */
            color: #fff;
            padding: 8px 15px;
            margin-bottom: 10px;
            font-size: 1.1em;
            font-weight: bold;
            text-align: center;
        }}
        .movie-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); /* Responsive grid */
            gap: 15px;
            padding: 10px; /* Padding for the grid */
        }}
        .movie-card {{
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
            text-align: center;
            position: relative;
        }}
        .movie-card img {{
            width: 100%;
            height: 220px; /* Fixed height for consistency */
            object-fit: cover;
            display: block;
        }}
        .movie-card .tag {{
            position: absolute;
            top: 8px;
            left: 8px;
            background-color: #28a745; /* Green for "TV" tag */
            color: #fff;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .movie-card .title {{
            padding: 10px;
            font-size: 0.9em;
            font-weight: bold;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .movie-card .year {{
            font-size: 0.8em;
            color: #666;
            margin-bottom: 8px;
        }}
        .movie-card a {{
            text-decoration: none;
            color: inherit;
        }}
        .footer-nav {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #222;
            color: #fff;
            display: flex;
            justify-content: space-around;
            padding: 10px 0;
            box-shadow: 0 -2px 5px rgba(0,0,0,0.2);
            z-index: 1000; /* Ensure it stays on top */
        }}
        .footer-nav .nav-item {{
            text-align: center;
            flex: 1;
            padding: 5px 0;
            cursor: pointer;
            text-decoration: none;
            color: #fff;
            font-size: 0.8em;
        }}
        .footer-nav .nav-item i {{
            display: block;
            font-size: 1.5em;
            margin-bottom: 3px;
        }}
        /* Font Awesome for icons (requires CDN or local files) */
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css');

    </style>
</head>
<body>
    <div class="header">
        <span class="icon">&#9776;</span> <div class="logo">MOVIE DOKAN</div>
        <span class="icon">&#128269;</span> </div>

    <div class="notice-bar">
        Notice: সবার আ গো পেতে জয়েন রুন আমাদের টেলিগ্রাম
    </div>

    <div class="button-section">
        <a href="#" class="btn red">Adult & Bangla Dubbed</a>
        <a href="https://t.me/your_telegram_channel" target="_blank" class="btn blue">Join Telegram</a>
        <a href="#" class="btn purple">Ads Free Website</a>
        <a href="#" class="btn blue">How To Download</a>
    </div>

    <div class="domain-notice">
        Our Official New Domain is MovieDokan.biz Please Bookmark our Official domain.! Keep Supporting & Keep Sharing.
    </div>

    <div class="gaza-banner">
        <img src="https://via.placeholder.com/30" alt="Gaza Icon"> SAVE GAZA FREE PALESTINE
    </div>

    <div class="content-section">
        <div class="section-header">Trending on MovieDokan</div>
        <div class="movie-grid">
            {trending_list}
            <a href="/movie/macgyver-1985-s01-bangla-dubbe-some-uuid" class="movie-card">
                <img src="https://via.placeholder.com/150x220?text=MacGyver" alt="MacGyver Poster">
                <span class="tag">TV</span>
                <div class="title">ম্যাকগাইভার MacGyver (1985) S01 Bangla Dubbe...</div>
                <div class="year">1985</div>
            </a>
            <a href="#" class="movie-card">
                <img src="https://via.placeholder.com/150x220?text=Movie+2" alt="Movie 2 Poster">
                <span class="tag">Movie</span>
                <div class="title">New Action Film</div>
                <div class="year">2024</div>
            </a>
             <a href="#" class="movie-card">
                <img src="https://via.placeholder.com/150x220?text=Movie+3" alt="Movie 3 Poster">
                <span class="tag">Series</span>
                <div class="title">Sci-Fi Adventure</div>
                <div class="year">2023</div>
            </a>
             <a href="#" class="movie-card">
                <img src="https://via.placeholder.com/150x220?text=Movie+4" alt="Movie 4 Poster">
                <span class="tag">Movie</span>
                <div class="title">Drama Classic</div>
                <div class="year">2021</div>
            </a>
        </div>
    </div>

    <div class="footer-nav">
        <a href="#" class="nav-item"><i class="fas fa-home"></i> <span>Home</span></a>
        <a href="#" class="nav-item"><i class="fas fa-film"></i> <span>Movie</span></a>
        <a href="#" class="nav-item"><i class="fas fa-plus-circle"></i> <span>Request</span></a>
        <a href="#" class="nav-item"><i class="fas fa-tv"></i> <span>Web Series</span></a>
        <a href="#" class="nav-item"><i class="fas fa-search"></i> <span>Search</span></a>
    </div>

</body>
</html>
'''

search_html = '''
<html><head><title>Search Results</title></head><body>
<h2>Search Results for: {query}</h2>
<ul>
{results_list}
</ul>
<a href="/">← Back</a>
</body></html>
'''

movie_html = '''
<html><head><title>{title}</title></head><body>
<h2>{title} ({year})</h2>
<p><b>Genre:</b> {genre}</p>
<p><b>Plot:</b> {plot}</p>
<p><img src="{poster}" width="200"></p>
<p><a href="{telegram_link}" target="_blank">📥 Telegram Download</a></p>
<p><a href="{terabox_link}" target="_blank">📥 Terabox Download</a></p>
<a href="/">← Home</a>
</body></html>
'''

admin_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - Add Movie</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f0f2f5; color: #333; }}
        h2 {{ color: #222; }}
        form {{
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            max-width: 500px;
            margin: 20px auto;
        }}
        label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
        input[type="text"], textarea {{
            width: calc(100% - 22px);
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        textarea {{
            resize: vertical;
            min-height: 80px;
        }}
        button {{
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            margin-top: 10px;
        }}
        button:hover {{
            background-color: #0056b3;
        }}
        .download-links {{
            margin-top: 15px;
            border-top: 1px solid #eee;
            padding-top: 15px;
        }}
        .download-links button {{
            display: block; /* Make buttons stack */
            width: 100%;
            margin-bottom: 5px; /* Space between buttons */
            background-color: #28a745; /* Green for download buttons */
        }}
        .download-links button:hover {{
            background-color: #218838;
        }}
        .auto-fill-button {{
            background-color: #ffc107; /* Yellow for auto-fill */
            color: #333;
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            margin-left: 5px;
        }}
        .auto-fill-button:hover {{
            background-color: #e0a800;
        }}
        #posterPreview {{
            max-width: 150px;
            max-height: 200px;
            display: block;
            margin-top: 10px;
            border: 1px solid #ddd;
        }}
        .input-with-button {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}
        .input-with-button input {{
            margin-bottom: 0; /* Remove margin from input */
            flex-grow: 1;
        }}
    </style>
</head>
<body>
    <h2>Add New Movie</h2>
    <form method="POST" id="movieForm">
        <label for="title">Title:</label>
        <div class="input-with-button">
            <input type="text" name="title" id="title" placeholder="Movie Title" required>
            <button type="button" class="auto-fill-button" onclick="fetchMovieInfo()">Auto-fill</button>
        </div>

        <label for="year">Year:</label>
        <input type="text" name="year" id="year" placeholder="Year"><br>

        <label for="genre">Genre:</label>
        <input type="text" name="genre" id="genre" placeholder="Genre"><br>

        <label for="plot">Plot:</label>
        <textarea name="plot" id="plot" placeholder="Plot Summary"></textarea><br>

        <label for="poster">Poster URL:</label>
        <input type="text" name="poster" id="poster" placeholder="Poster URL">
        <img id="posterPreview" src="" alt="Poster Preview" style="display:none;"><br>

        <div class="download-links">
            <h3>Download Links (Admin will manually add)</h3>
            <label for="telegram">Telegram Link:</label>
            <input type="text" name="telegram" id="telegram" placeholder="Telegram Download Link"><br>

            <label for="terabox">Terabox Link:</label>
            <input type="text" name="terabox" id="terabox" placeholder="Terabox Download Link"><br>
        </div>
        
        <button type="submit">Add Movie</button>
    </form>
    <a href="/">← Home</a>

    <script>
        // JavaScript for Auto-filling from TMDb API via our Flask endpoint
        const titleInput = document.getElementById('title');
        const yearInput = document.getElementById('year');
        const genreInput = document.getElementById('genre');
        const plotInput = document.getElementById('plot');
        const posterInput = document.getElementById('poster');
        const posterPreview = document.getElementById('posterPreview');

        // Update poster preview when poster URL changes manually
        posterInput.addEventListener('input', function() {{
            if (this.value) {{
                posterPreview.src = this.value;
                posterPreview.style.display = 'block';
            }} else {{
                posterPreview.src = '';
                posterPreview.style.display = 'none';
            }}
        }});

        async function fetchMovieInfo() {{
            const title = titleInput.value.trim();
            if (!title) {{
                alert("Please enter a movie title to auto-fill.");
                return;
            }}

            try {{
                // Call our Flask endpoint to get movie info from TMDb
                const response = await fetch(`/api/get_tmdb_movie_info?title=${{encodeURIComponent(title)}}`);
                const data = await response.json();

                if (data.error) {{
                    alert("Error: " + data.error);
                    console.error("TMDb API Error:", data.error);
                    // Clear fields on error
                    yearInput.value = '';
                    genreInput.value = '';
                    plotInput.value = '';
                    posterInput.value = '';
                    posterPreview.src = '';
                    posterPreview.style.display = 'none';
                    return;
                }}

                // Populate the form fields
                yearInput.value = data.year || '';
                genreInput.value = data.genre || ''; // Now should be names
                plotInput.value = data.plot || '';
                posterInput.value = data.poster || '';

                // Update poster preview
                if (data.poster) {{
                    posterPreview.src = data.poster;
                    posterPreview.style.display = 'block';
                }} else {{
                    posterPreview.src = '';
                    posterPreview.style.display = 'none';
                }}

            }} catch (error) {{
                alert("An error occurred while fetching movie info.");
                console.error("Fetch error:", error);
            }}
        }}
    </script>
</body>
</html>
'''

# --- Data Helpers (Updated for MongoDB) ---
# Check if movies_collection is initialized before using it
def get_all_movies():
    if client is None:
        print("MongoDB client not initialized.")
        return []
    return list(movies_collection.find({}, {'_id': 0})) # Exclude MongoDB's default _id field

def save_movie(movie_data):
    if client is None:
        print("MongoDB client not initialized. Cannot save movie.")
        return False
    # Ensure slug is unique, even though we generate UUID
    if movies_collection.find_one({"slug": movie_data['slug']}):
        # If slug already exists, generate a new one (unlikely with UUID, but good practice)
        movie_data['slug'] += '-' + str(uuid.uuid4())[:4] # Append more unique characters
    movies_collection.insert_one(movie_data)
    return True

def get_movie_by_slug(slug):
    if client is None:
        print("MongoDB client not initialized.")
        return None
    return movies_collection.find_one({"slug": slug}, {'_id': 0}) # Exclude _id field

# --- Routes ---
@app.route('/')
def home():
    # In a real app, you'd fetch trending movies from MongoDB or a separate source
    # For now, keeping the static HTML as per the screenshot
    return index_html.format(trending_list="")

@app.route('/search')
def search():
    q = request.args.get("q", "").lower()
    if client is None:
        results = []
    else:
        # Search in MongoDB
        results = list(movies_collection.find({"title": {"$regex": q, "$options": "i"}}, {'_id': 0})) # Case-insensitive search
    
    results_list = ''
    for m in results:
        results_list += f'<li><a href="/movie/{m["slug"]}">{m["title"]} ({m["year"]})</a></li>'
    return search_html.format(results_list=results_list, query=q)

@app.route('/movie/<slug>')
def movie(slug):
    movie = get_movie_by_slug(slug)
    if not movie:
        return "Movie not found", 404
    return movie_html.format(**movie)

# --- New API Endpoint for TMDb ---
@app.route('/api/get_tmdb_movie_info', methods=['GET'])
def get_tmdb_movie_info():
    title = request.args.get('title')
    if not title:
        return jsonify({"error": "Title parameter is missing"}), 400

    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY": # Check for placeholder
        return jsonify({"error": "TMDb API Key is not configured in .env."}), 500
    
    # TMDb Search API
    tmdb_search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={quote_plus(title)}"

    try:
        response = requests.get(tmdb_search_url)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        search_results = response.json()

        if search_results and search_results.get("results"):
            # Take the first result
            first_result = search_results["results"][0]
            
            # Convert genre_ids to genre names
            genres = []
            if first_result.get("genre_ids"):
                for genre_id in first_result["genre_ids"]:
                    if genre_id in genre_map:
                        genres.append(genre_map[genre_id])
            genre_names = ", ".join(genres)

            # TMDb poster base URL
            poster_base_url = "https://image.tmdb.org/t/p/w500" # w500 for a reasonable size

            return jsonify({
                "title": first_result.get("title"),
                "year": first_result.get("release_date", "")[:4], # Extract year from release_date
                "plot": first_result.get("overview"),
                "poster": poster_base_url + first_result.get("poster_path") if first_result.get("poster_path") else "",
                "genre": genre_names
            })
        else:
            return jsonify({"error": "Movie not found on TMDb."}), 404
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to connect to TMDb API: {e}"}), 500
    except ValueError: # JSON decoding error
        return jsonify({"error": "Invalid response from TMDb API"}), 500


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        title = request.form.get('title')
        year = request.form.get('year')
        genre = request.form.get('genre')
        plot = request.form.get('plot')
        poster = request.form.get('poster')
        telegram = request.form.get('telegram')
        terabox = request.form.get('terabox')

        # Simple slug generation. For production, consider a more robust slugify library.
        # Ensure slug is URL-safe and handle potential duplicates
        base_slug = "".join(c for c in title.lower() if c.isalnum() or c == ' ').replace(" ", "-")
        slug = base_slug + '-' + str(uuid.uuid4())[:6]

        movie = {
            "title": title,
            "year": year,
            "genre": genre,
            "plot": plot,
            "poster": poster,
            "telegram_link": telegram,
            "terabox_link": terabox,
            "slug": slug
        }

        if save_movie(movie): # save_movie now returns True/False
            return redirect(url_for('movie', slug=slug))
        else:
            return "Failed to save movie. MongoDB connection error?", 500

    return admin_html

# --- Run ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # In production, debug should be False for security and performance
    # debug=True is for local development only
    app.run(host='0.0.0.0', port=port, debug=True)
