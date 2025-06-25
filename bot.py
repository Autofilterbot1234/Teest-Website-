import os
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, send_from_directory
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import requests
import json
from functools import wraps
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Configuration from .env ---
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'movie_platform')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# --- MongoDB Connection ---
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
movies_collection = db.movies
series_collection = db.series
featured_collection = db.featured_movies # New collection for featured movies

# --- TMDb API Base URLs ---
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_POSTER_BASE_URL = "https://image.tmdb.org/t/p/w185" # For smaller posters
TMDB_BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/w1280" # For backdrops/banners

# --- Helper Functions ---
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD):
            return "Unauthorized", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        return f(*args, **kwargs)
    return decorated

def get_movie_details_from_tmdb(title):
    search_url = f"{TMDB_BASE_URL}/search/movie"
    params = {'api_key': TMDB_API_KEY, 'query': title}
    response = requests.get(search_url, params=params)
    data = response.json()
    if data['results']:
        movie_id = data['results'][0]['id']
        details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
        params = {'api_key': TMDB_API_KEY}
        details_response = requests.get(details_url, params=params)
        details = details_response.json()
        
        trailer_url = None
        videos_url = f"{TMDB_BASE_URL}/movie/{movie_id}/videos"
        videos_response = requests.get(videos_url, params={'api_key': TMDB_API_KEY})
        videos_data = videos_response.json()
        for video in videos_data.get('results', []):
            if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                trailer_url = f"https://www.youtube.com/embed/{video['key']}"
                break
        
        genres = [g['name'] for g in details.get('genres', [])]
        
        return {
            "title": details.get('title'),
            "description": details.get('overview'),
            "release_date": details.get('release_date'),
            "poster_url": f"{TMDB_POSTER_BASE_URL}{details.get('poster_path')}" if details.get('poster_path') else None,
            "backdrop_url": f"{TMDB_BACKDROP_BASE_URL}{details.get('backdrop_path')}" if details.get('backdrop_path') else None,
            "trailer_url": trailer_url,
            "rating": details.get('vote_average'),
            "genres": genres,
            "tmdb_id": movie_id
        }
    return None

def get_series_details_from_tmdb(title):
    search_url = f"{TMDB_BASE_URL}/search/tv"
    params = {'api_key': TMDB_API_KEY, 'query': title}
    response = requests.get(search_url, params=params)
    data = response.json()
    if data['results']:
        series_id = data['results'][0]['id']
        details_url = f"{TMDB_BASE_URL}/tv/{series_id}"
        params = {'api_key': TMDB_API_KEY}
        details_response = requests.get(details_url, params=params)
        details = details_response.json()

        trailer_url = None
        videos_url = f"{TMDB_BASE_URL}/tv/{series_id}/videos"
        videos_response = requests.get(videos_url, params={'api_key': TMDB_API_KEY})
        videos_data = videos_response.json()
        for video in videos_data.get('results', []):
            if video.get('site') == 'YouTube' and video.get('type') == 'Trailer':
                trailer_url = f"https://www.youtube.com/embed/{video['key']}"
                break
        
        genres = [g['name'] for g in details.get('genres', [])]

        return {
            "title": details.get('name'),
            "description": details.get('overview'),
            "release_date": details.get('first_air_date'),
            "poster_url": f"{TMDB_POSTER_BASE_URL}{details.get('poster_path')}" if details.get('poster_path') else None,
            "backdrop_url": f"{TMDB_BACKDROP_BASE_URL}{details.get('backdrop_path')}" if details.get('backdrop_path') else None,
            "trailer_url": trailer_url,
            "rating": details.get('vote_average'),
            "genres": genres,
            "tmdb_id": series_id
        }
    return None

# --- HTML Templates (for simplicity, kept as strings) ---

# index.html
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StreamHub - Watch Movies & Series Online</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary-bg: #1a1a1a;
            --secondary-bg: #2a2a2a;
            --card-bg: #333;
            --text-color: #f0f0f0;
            --accent-color: #e50914; /* Netflix Red */
            --light-grey: #bbb;
            --dark-grey: #555;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--primary-bg);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Header */
        header {
            background-color: var(--secondary-bg);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .logo {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--accent-color);
            text-decoration: none;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
        }

        .logo i {
            margin-right: 8px;
            color: var(--text-color);
        }

        .logo span {
            color: var(--text-color);
            margin-left: 5px;
        }

        .search-bar {
            display: flex;
            align-items: center;
            background-color: var(--card-bg);
            border-radius: 25px;
            padding: 5px 15px;
            width: 300px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
        }

        .search-bar input {
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 1em;
            outline: none;
            flex-grow: 1;
            padding: 8px 0;
        }

        .search-bar input::placeholder {
            color: var(--light-grey);
        }

        .search-bar button {
            background: none;
            border: none;
            color: var(--light-grey);
            font-size: 1.1em;
            cursor: pointer;
            padding: 5px;
        }

        .search-bar button:hover {
            color: var(--text-color);
        }

        /* Hero Section / Featured Slider */
        .hero-section {
            position: relative;
            width: 100%;
            height: 500px; /* Adjust height as needed */
            overflow: hidden;
            background-color: var(--secondary-bg);
            margin-bottom: 30px;
        }

        .slider-item {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            transition: opacity 1s ease-in-out;
            display: flex;
            align-items: center;
            justify-content: center;
            background-size: cover;
            background-position: center;
            color: white;
            text-shadow: 2px 2px 5px rgba(0,0,0,0.7);
        }

        .slider-item.active {
            opacity: 1;
        }

        .slider-content {
            background: linear-gradient(to right, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.6) 30%, rgba(0,0,0,0.2) 60%, transparent 100%);
            padding: 50px 80px;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .slider-content h2 {
            font-size: 3.5em;
            margin-bottom: 10px;
            color: var(--accent-color);
            line-height: 1.2;
        }

        .slider-content p {
            font-size: 1.2em;
            max-width: 600px;
            margin-bottom: 20px;
            line-height: 1.6;
        }

        .slider-buttons .btn {
            display: inline-block;
            padding: 12px 25px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: 600;
            transition: background-color 0.3s ease, transform 0.2s ease;
            margin-right: 15px;
        }

        .slider-buttons .btn-play {
            background-color: var(--accent-color);
            color: white;
        }

        .slider-buttons .btn-play:hover {
            background-color: #c11119;
            transform: translateY(-2px);
        }

        .slider-buttons .btn-info {
            background-color: rgba(100, 100, 100, 0.7);
            color: white;
        }

        .slider-buttons .btn-info:hover {
            background-color: rgba(80, 80, 80, 0.9);
            transform: translateY(-2px);
        }

        /* Sections */
        .section-title {
            font-size: 2em;
            margin-bottom: 25px;
            color: var(--accent-color);
            border-bottom: 3px solid var(--accent-color);
            padding-bottom: 10px;
            display: inline-block;
            letter-spacing: 0.5px;
        }

        .movie-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .movie-card {
            background-color: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            transform-style: preserve-3d;
            perspective: 1000px;
            border: 2px solid transparent; /* For RGB border */
            animation: gradientBorder 5s linear infinite; /* RGB border animation */
        }

        @keyframes gradientBorder {
            0% { border-image: linear-gradient(to right, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3); border-image-slice: 1; }
            100% { border-image: linear-gradient(to right, #9400d3, #4b0082, #0000ff, #00ff00, #ffff00, #ff7f00, #ff0000); border-image-slice: 1; }
        }

        .movie-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.7);
        }

        .movie-card img {
            width: 100%;
            height: 270px; /* Fixed height for posters */
            object-fit: cover;
            display: block;
        }

        .movie-card-info {
            padding: 15px;
            text-align: center;
        }

        .movie-card-info h3 {
            font-size: 1.1em;
            margin: 0 0 10px;
            color: var(--text-color);
            height: 45px; /* Fixed height for titles */
            overflow: hidden;
            text-overflow: ellipsis;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
        }

        .movie-card-info .btn {
            display: inline-block;
            background-color: var(--accent-color);
            color: white;
            padding: 8px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-size: 0.9em;
            transition: background-color 0.3s ease;
        }

        .movie-card-info .btn:hover {
            background-color: #c11119;
        }

        /* Categories/Genres */
        .categories {
            margin-bottom: 40px;
        }

        .categories .section-title {
            margin-bottom: 20px;
        }

        .genre-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 15px;
        }

        .genre-item {
            background-color: var(--card-bg);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            text-decoration: none;
            color: var(--text-color);
            font-weight: 600;
            transition: background-color 0.3s ease, transform 0.3s ease;
        }

        .genre-item:hover {
            background-color: var(--accent-color);
            transform: translateY(-5px);
        }

        /* Bottom Navigation (Mobile) */
        .bottom-nav {
            display: none; /* Hidden by default, shown on mobile */
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: var(--secondary-bg);
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.4);
            z-index: 1000;
            justify-content: space-around;
            padding: 10px 0;
        }

        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-decoration: none;
            color: var(--light-grey);
            font-size: 0.8em;
            transition: color 0.3s ease;
        }

        .nav-item i {
            font-size: 1.5em;
            margin-bottom: 5px;
        }

        .nav-item.active, .nav-item:hover {
            color: var(--accent-color);
        }

        /* Footer */
        footer {
            background-color: var(--secondary-bg);
            color: var(--light-grey);
            text-align: center;
            padding: 20px;
            margin-top: auto; /* Pushes footer to the bottom */
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.4);
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
                padding: 10px 15px;
            }

            .logo {
                font-size: 1.5em;
                margin-bottom: 10px;
            }

            .search-bar {
                width: 100%;
                margin-top: 10px;
            }

            .hero-section {
                height: 350px;
            }

            .slider-content {
                padding: 30px;
            }

            .slider-content h2 {
                font-size: 2.2em;
            }

            .slider-content p {
                font-size: 0.9em;
                max-width: 90%;
            }

            .slider-buttons .btn {
                padding: 10px 20px;
                font-size: 0.9em;
            }

            .movie-grid {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 15px;
            }

            .movie-card img {
                height: 220px;
            }

            .movie-card-info h3 {
                font-size: 1em;
                height: 40px;
            }

            .bottom-nav {
                display: flex; /* Show on mobile */
            }

            .container {
                padding-bottom: 70px; /* Make space for bottom nav */
            }
        }

        @media (max-width: 480px) {
            .hero-section {
                height: 280px;
            }
            .slider-content {
                padding: 20px;
            }
            .slider-content h2 {
                font-size: 1.8em;
            }
            .slider-content p {
                font-size: 0.8em;
                max-width: 100%;
            }
            .slider-buttons .btn {
                padding: 8px 15px;
                font-size: 0.8em;
            }
            .movie-grid {
                grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            }
            .movie-card img {
                height: 190px;
            }
            .movie-card-info h3 {
                font-size: 0.9em;
                height: 35px;
            }
            .genre-grid {
                grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            }
        }
    </style>
</head>
<body>
    <header>
        <a href="/" class="logo"><i class="fas fa-play-circle"></i>Stream<span>Hub</span></a>
        <form action="/search" method="get" class="search-bar">
            <input type="text" name="query" placeholder="Search movies or series..." required>
            <button type="submit"><i class="fas fa-search"></i></button>
        </form>
    </header>

    <main>
        <section class="hero-section">
            {% for movie in featured_movies %}
            <div class="slider-item {% if loop.first %}active{% endif %}" style="background-image: url('{{ movie.backdrop_url if movie.backdrop_url else movie.poster_url }}');">
                <div class="slider-content">
                    <h2>{{ movie.title }}</h2>
                    <p>{{ movie.description | truncate(150) }}</p>
                    <div class="slider-buttons">
                        <a href="/detail/{{ movie._id }}" class="btn btn-play"><i class="fas fa-play-circle"></i> Watch Now</a>
                        <a href="/detail/{{ movie._id }}" class="btn btn-info"><i class="fas fa-info-circle"></i> More Info</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </section>

        <div class="container">
            <section class="trending-section">
                <h2 class="section-title">🔥 Trending Movies</h2>
                <div class="movie-grid">
                    {% for movie in trending_movies %}
                    <div class="movie-card">
                        <a href="/detail/{{ movie._id }}">
                            <img src="{{ movie.poster_url if movie.poster_url else '/static/placeholder.jpg' }}" alt="{{ movie.title }}">
                        </a>
                        <div class="movie-card-info">
                            <h3>{{ movie.title }}</h3>
                            <a href="/detail/{{ movie._id }}" class="btn">View Details</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </section>

            <section class="latest-movies-section">
                <h2 class="section-title">🎬 Latest Movies</h2>
                <div class="movie-grid">
                    {% for movie in latest_movies %}
                    <div class="movie-card">
                        <a href="/detail/{{ movie._id }}">
                            <img src="{{ movie.poster_url if movie.poster_url else '/static/placeholder.jpg' }}" alt="{{ movie.title }}">
                        </a>
                        <div class="movie-card-info">
                            <h3>{{ movie.title }}</h3>
                            <a href="/detail/{{ movie._id }}" class="btn">View Details</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </section>

            <section class="latest-series-section">
                <h2 class="section-title">📺 Latest Web Series</h2>
                <div class="movie-grid">
                    {% for series in latest_series %}
                    <div class="movie-card">
                        <a href="/detail/{{ series._id }}">
                            <img src="{{ series.poster_url if series.poster_url else '/static/placeholder.jpg' }}" alt="{{ series.title }}">
                        </a>
                        <div class="movie-card-info">
                            <h3>{{ series.title }}</h3>
                            <a href="/detail/{{ series._id }}" class="btn">View Details</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </section>

            <section class="coming-soon-section">
                <h2 class="section-title">⏰ Coming Soon</h2>
                <div class="movie-grid">
                    {% for movie in coming_soon_movies %}
                    <div class="movie-card">
                        <a href="/detail/{{ movie._id }}">
                            <img src="{{ movie.poster_url if movie.poster_url else '/static/placeholder.jpg' }}" alt="{{ movie.title }}">
                        </a>
                        <div class="movie-card-info">
                            <h3>{{ movie.title }}</h3>
                            <a href="/detail/{{ movie._id }}" class="btn">View Details</a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </section>

            <section class="categories">
                <h2 class="section-title">📚 Explore Genres</h2>
                <div class="genre-grid">
                    {% for genre in all_genres %}
                    <a href="/genre/{{ genre }}" class="genre-item">{{ genre }}</a>
                    {% endfor %}
                </div>
            </section>
        </div>
    </main>

    <nav class="bottom-nav">
        <a href="/" class="nav-item active">
            <i class="fas fa-home"></i>
            <span>Home</span>
        </a>
        <a href="/search" class="nav-item">
            <i class="fas fa-search"></i>
            <span>Search</span>
        </a>
        <a href="/movies" class="nav-item">
            <i class="fas fa-film"></i>
            <span>Movies</span>
        </a>
        <a href="/series" class="nav-item">
            <i class="fas fa-tv"></i>
            <span>Series</span>
        </a>
    </nav>

    <footer>
        <p>&copy; 2024 StreamHub. All rights reserved.</p>
        <p>Developed by YourName/Company</p>
    </footer>

    <script>
        // Hero Slider functionality
        const sliderItems = document.querySelectorAll('.slider-item');
        let currentSlide = 0;

        function showSlide(index) {
            sliderItems.forEach((item, i) => {
                item.classList.remove('active');
                if (i === index) {
                    item.classList.add('active');
                }
            });
        }

        function nextSlide() {
            currentSlide = (currentSlide + 1) % sliderItems.length;
            showSlide(currentSlide);
        }

        // Auto-advance slider every 5 seconds
        if (sliderItems.length > 0) {
            setInterval(nextSlide, 5000);
            showSlide(currentSlide); // Initialize first slide
        }

        // Handle bottom navigation active state
        document.addEventListener('DOMContentLoaded', () => {
            const currentPath = window.location.pathname;
            const navItems = document.querySelectorAll('.bottom-nav .nav-item');
            navItems.forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('href') === currentPath || 
                    (currentPath.startsWith('/movies') && item.getAttribute('href') === '/movies') ||
                    (currentPath.startsWith('/series') && item.getAttribute('href') === '/series')) {
                    item.classList.add('active');
                }
            });
        });
    </script>
</body>
</html>
"""

# detail.html
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ content.title }} - StreamHub</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary-bg: #1a1a1a;
            --secondary-bg: #2a2a2a;
            --card-bg: #333;
            --text-color: #f0f0f0;
            --accent-color: #e50914; /* Netflix Red */
            --light-grey: #bbb;
            --dark-grey: #555;
            --backdrop-overlay: rgba(0, 0, 0, 0.7);
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--primary-bg);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }

        /* Header (reuse from index) */
        header {
            background-color: var(--secondary-bg);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .logo {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--accent-color);
            text-decoration: none;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
        }

        .logo i {
            margin-right: 8px;
            color: var(--text-color);
        }

        .logo span {
            color: var(--text-color);
            margin-left: 5px;
        }

        .search-bar {
            display: flex;
            align-items: center;
            background-color: var(--card-bg);
            border-radius: 25px;
            padding: 5px 15px;
            width: 300px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
        }

        .search-bar input {
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 1em;
            outline: none;
            flex-grow: 1;
            padding: 8px 0;
        }

        .search-bar input::placeholder {
            color: var(--light-grey);
        }

        .search-bar button {
            background: none;
            border: none;
            color: var(--light-grey);
            font-size: 1.1em;
            cursor: pointer;
            padding: 5px;
        }

        .search-bar button:hover {
            color: var(--text-color);
        }

        /* Main Content */
        .detail-hero {
            position: relative;
            width: 100%;
            height: 60vh;
            background-size: cover;
            background-position: center;
            display: flex;
            align-items: flex-end;
            padding: 40px;
            box-sizing: border-box;
            color: white;
            text-shadow: 2px 2px 5px rgba(0,0,0,0.8);
            margin-bottom: 30px;
        }

        .detail-hero::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--backdrop-overlay);
            z-index: 1;
        }

        .detail-content {
            position: relative;
            z-index: 2;
            display: flex;
            align-items: flex-start;
            gap: 30px;
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
        }

        .detail-poster {
            width: 250px;
            min-width: 200px;
            border-radius: 10px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.7);
        }

        .detail-info {
            flex-grow: 1;
            background-color: rgba(0,0,0,0.6);
            padding: 20px 30px;
            border-radius: 10px;
        }

        .detail-info h1 {
            font-size: 3em;
            margin-top: 0;
            margin-bottom: 10px;
            color: var(--accent-color);
        }

        .detail-meta {
            font-size: 1.1em;
            color: var(--light-grey);
            margin-bottom: 20px;
        }

        .detail-meta span {
            margin-right: 20px;
        }

        .detail-meta i {
            margin-right: 5px;
            color: var(--accent-color);
        }

        .detail-description {
            font-size: 1.1em;
            line-height: 1.6;
            margin-bottom: 30px;
            max-width: 800px;
        }

        .action-buttons .btn {
            display: inline-block;
            padding: 12px 25px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: 600;
            transition: background-color 0.3s ease, transform 0.2s ease;
            margin-right: 15px;
            margin-bottom: 15px;
            font-size: 1em;
        }

        .action-buttons .btn-primary {
            background-color: var(--accent-color);
            color: white;
        }

        .action-buttons .btn-primary:hover {
            background-color: #c11119;
            transform: translateY(-2px);
        }

        .action-buttons .btn-secondary {
            background-color: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--dark-grey);
        }

        .action-buttons .btn-secondary:hover {
            background-color: var(--dark-grey);
            transform: translateY(-2px);
        }

        /* Download Links / Episodes */
        .download-section, .episodes-section {
            background-color: var(--secondary-bg);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }

        .download-section h2, .episodes-section h2 {
            font-size: 2em;
            color: var(--accent-color);
            margin-bottom: 25px;
            border-bottom: 2px solid var(--dark-grey);
            padding-bottom: 10px;
        }

        .download-links ul {
            list-style: none;
            padding: 0;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }

        .download-links li {
            background-color: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s ease;
            width: calc(33.333% - 10px); /* 3 items per row */
            min-width: 250px;
        }

        .download-links li:hover {
            transform: translateY(-5px);
        }

        .download-links a {
            display: block;
            padding: 15px 20px;
            color: var(--text-color);
            text-decoration: none;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .download-links a:hover {
            background-color: var(--accent-color);
        }

        .download-links .quality {
            font-size: 0.9em;
            color: var(--light-grey);
            margin-left: 10px;
        }

        /* Episodes */
        .episode-list {
            list-style: none;
            padding: 0;
        }

        .episode-item {
            background-color: var(--card-bg);
            margin-bottom: 10px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s ease;
        }

        .episode-item:hover {
            transform: translateY(-3px);
        }

        .episode-item a {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            text-decoration: none;
            color: var(--text-color);
            font-weight: 600;
        }

        .episode-item a:hover {
            background-color: var(--accent-color);
        }

        .episode-title {
            flex-grow: 1;
        }

        .episode-quality {
            font-size: 0.9em;
            color: var(--light-grey);
        }

        /* Trailer Section */
        .trailer-section {
            background-color: var(--secondary-bg);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }

        .trailer-section h2 {
            font-size: 2em;
            color: var(--accent-color);
            margin-bottom: 25px;
            border-bottom: 2px solid var(--dark-grey);
            padding-bottom: 10px;
        }

        .video-container {
            position: relative;
            padding-bottom: 56.25%; /* 16:9 Aspect Ratio */
            height: 0;
            overflow: hidden;
            border-radius: 8px;
            background-color: black;
        }

        .video-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }

        /* Related Content (Similar Movies/Series) */
        .related-content-section {
            padding: 30px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }

        .related-content-section h2 {
            font-size: 2em;
            color: var(--accent-color);
            margin-bottom: 25px;
            border-bottom: 2px solid var(--dark-grey);
            padding-bottom: 10px;
        }

        .related-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 20px;
        }

        .related-card {
            background-color: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .related-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.7);
        }

        .related-card img {
            width: 100%;
            height: 270px;
            object-fit: cover;
            display: block;
        }

        .related-card-info {
            padding: 15px;
            text-align: center;
        }

        .related-card-info h3 {
            font-size: 1.1em;
            margin: 0 0 10px;
            color: var(--text-color);
            height: 45px;
            overflow: hidden;
            text-overflow: ellipsis;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
        }

        .related-card-info .btn {
            display: inline-block;
            background-color: var(--accent-color);
            color: white;
            padding: 8px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-size: 0.9em;
            transition: background-color 0.3s ease;
        }

        .related-card-info .btn:hover {
            background-color: #c11119;
        }

        /* Footer (reuse from index) */
        footer {
            background-color: var(--secondary-bg);
            color: var(--light-grey);
            text-align: center;
            padding: 20px;
            margin-top: 50px;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.4);
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
                padding: 10px 15px;
            }
            .logo {
                font-size: 1.5em;
                margin-bottom: 10px;
            }
            .search-bar {
                width: 100%;
                margin-top: 10px;
            }

            .detail-hero {
                height: auto;
                padding: 20px;
                background-size: cover;
                background-position: center;
            }

            .detail-hero::before {
                background: linear-gradient(to top, var(--primary-bg) 0%, rgba(0,0,0,0.8) 50%, transparent 100%);
            }

            .detail-content {
                flex-direction: column;
                align-items: center;
                text-align: center;
                width: 100%;
                padding: 0;
            }

            .detail-poster {
                width: 180px;
                margin-bottom: 20px;
                min-width: unset;
            }

            .detail-info {
                padding: 20px;
                width: 100%;
                box-sizing: border-box;
            }

            .detail-info h1 {
                font-size: 2em;
            }

            .detail-meta {
                font-size: 0.9em;
                margin-bottom: 15px;
            }

            .detail-description {
                font-size: 0.9em;
                margin-bottom: 20px;
            }

            .action-buttons .btn {
                width: 100%;
                margin-right: 0;
                margin-bottom: 10px;
            }

            .download-section, .episodes-section, .trailer-section, .related-content-section {
                padding: 20px;
                margin: 20px auto;
            }

            .download-links li {
                width: 100%;
                min-width: unset;
            }

            .related-grid {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }
            .related-card img {
                height: 220px;
            }
        }

        @media (max-width: 480px) {
            .detail-info h1 {
                font-size: 1.8em;
            }
            .detail-meta {
                font-size: 0.8em;
            }
            .detail-description {
                font-size: 0.85em;
            }
            .download-links a, .episode-item a {
                padding: 12px 15px;
                font-size: 0.9em;
            }
            .related-grid {
                grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            }
            .related-card img {
                height: 190px;
            }
        }
    </style>
</head>
<body>
    <header>
        <a href="/" class="logo"><i class="fas fa-play-circle"></i>Stream<span>Hub</span></a>
        <form action="/search" method="get" class="search-bar">
            <input type="text" name="query" placeholder="Search movies or series..." required>
            <button type="submit"><i class="fas fa-search"></i></button>
        </form>
    </header>

    <main>
        <section class="detail-hero" style="background-image: url('{{ content.backdrop_url if content.backdrop_url else content.poster_url }}');">
            <div class="detail-content">
                <img src="{{ content.poster_url if content.poster_url else '/static/placeholder.jpg' }}" alt="{{ content.title }}" class="detail-poster">
                <div class="detail-info">
                    <h1>{{ content.title }}</h1>
                    <div class="detail-meta">
                        {% if content.release_date %}
                        <span><i class="fas fa-calendar-alt"></i> {{ content.release_date.split('-')[0] if content.release_date else 'N/A' }}</span>
                        {% endif %}
                        {% if content.rating %}
                        <span><i class="fas fa-star"></i> {{ "%.1f" | format(content.rating) }} / 10</span>
                        {% endif %}
                        {% if content.genres %}
                        <span><i class="fas fa-tags"></i> {{ content.genres | join(', ') }}</span>
                        {% endif %}
                        {% if content.type == 'movie' and content.duration %}
                        <span><i class="fas fa-clock"></i> {{ content.duration }}</span>
                        {% endif %}
                    </div>
                    <p class="detail-description">{{ content.description }}</p>
                    <div class="action-buttons">
                        {% if content.trailer_url %}
                        <a href="#trailer-section" class="btn btn-primary"><i class="fas fa-play"></i> Watch Trailer</a>
                        {% endif %}
                        {% if content.type == 'movie' and content.download_links %}
                        <a href="#download-section" class="btn btn-secondary"><i class="fas fa-download"></i> Download Movie</a>
                        {% elif content.type == 'series' and content.episodes %}
                        <a href="#episodes-section" class="btn btn-secondary"><i class="fas fa-list"></i> View Episodes</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        </section>

        {% if content.trailer_url %}
        <section class="trailer-section" id="trailer-section">
            <h2>Official Trailer</h2>
            <div class="video-container">
                <iframe src="{{ content.trailer_url }}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
            </div>
        </section>
        {% endif %}

        {% if content.type == 'movie' and content.download_links %}
        <section class="download-section" id="download-section">
            <h2>Download Links</h2>
            <div class="download-links">
                <ul>
                    {% for link in content.download_links %}
                    <li><a href="{{ link.url }}" target="_blank">
                        <span>{{ link.source }}</span>
                        <span class="quality">{{ link.quality }}</span>
                    </a></li>
                    {% endfor %}
                </ul>
            </div>
        </section>
        {% elif content.type == 'series' and content.episodes %}
        <section class="episodes-section" id="episodes-section">
            <h2>Episodes</h2>
            <ul class="episode-list">
                {% for episode in content.episodes %}
                <li class="episode-item">
                    <a href="{{ episode.url }}" target="_blank">
                        <span class="episode-title">Season {{ episode.season }}, Episode {{ episode.episode_number }}: {{ episode.title }}</span>
                        <span class="episode-quality">{{ episode.quality }}</span>
                    </a>
                </li>
                {% endfor %}
            </ul>
        </section>
        {% endif %}

        {% if related_content %}
        <section class="related-content-section">
            <h2>You might also like</h2>
            <div class="related-grid movie-grid">
                {% for item in related_content %}
                <div class="related-card movie-card">
                    <a href="/detail/{{ item._id }}">
                        <img src="{{ item.poster_url if item.poster_url else '/static/placeholder.jpg' }}" alt="{{ item.title }}">
                    </a>
                    <div class="related-card-info movie-card-info">
                        <h3>{{ item.title }}</h3>
                        <a href="/detail/{{ item._id }}" class="btn">View Details</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}
    </main>

    <footer>
        <p>&copy; 2024 StreamHub. All rights reserved.</p>
        <p>Developed by YourName/Company</p>
    </footer>
</body>
</html>
"""

# admin.html
admin_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - StreamHub</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary-bg: #1a1a1a;
            --secondary-bg: #2a2a2a;
            --card-bg: #333;
            --text-color: #f0f0f0;
            --accent-color: #e50914;
            --light-grey: #bbb;
            --dark-grey: #555;
            --input-border: #444;
            --button-hover: #c11119;
            --danger-color: #dc3545;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--primary-bg);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }

        .container {
            max-width: 1200px;
            margin: 20px auto;
            padding: 20px;
        }

        /* Header (similar to main site) */
        header {
            background-color: var(--secondary-bg);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            margin-bottom: 30px;
        }

        .logo {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--accent-color);
            text-decoration: none;
            letter-spacing: 1px;
        }

        .logo span {
            color: var(--text-color);
            margin-left: 5px;
        }

        .admin-nav a {
            color: var(--text-color);
            text-decoration: none;
            margin-left: 20px;
            font-weight: 600;
            transition: color 0.3s ease;
        }

        .admin-nav a:hover {
            color: var(--accent-color);
        }

        h1 {
            color: var(--accent-color);
            margin-bottom: 30px;
            text-align: center;
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 10px;
            display: inline-block;
            width: 100%;
            box-sizing: border-box;
        }

        /* Forms */
        .form-section {
            background-color: var(--secondary-bg);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            margin-bottom: 40px;
        }

        .form-section h2 {
            color: var(--text-color);
            margin-top: 0;
            margin-bottom: 25px;
            font-size: 1.8em;
            border-bottom: 1px solid var(--dark-grey);
            padding-bottom: 10px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--light-grey);
        }

        .form-group input[type="text"],
        .form-group input[type="url"],
        .form-group input[type="number"],
        .form-group textarea,
        .form-group select {
            width: calc(100% - 20px);
            padding: 12px;
            border: 1px solid var(--input-border);
            border-radius: 5px;
            background-color: var(--card-bg);
            color: var(--text-color);
            font-size: 1em;
            box-sizing: border-box;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            border-color: var(--accent-color);
            outline: none;
            box-shadow: 0 0 0 2px rgba(229, 9, 20, 0.3);
        }

        .form-group button {
            background-color: var(--accent-color);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 5px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }

        .form-group button:hover {
            background-color: var(--button-hover);
        }

        .tmdb-fetch-button {
            background-color: #007bff; /* Blue for fetch */
            margin-left: 10px;
        }
        .tmdb-fetch-button:hover {
            background-color: #0056b3;
        }

        .form-inline {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            align-items: flex-end;
        }

        .form-inline input {
            flex-grow: 1;
        }

        .add-link-btn, .add-episode-btn {
            background-color: #28a745; /* Green for add */
        }
        .add-link-btn:hover, .add-episode-btn:hover {
            background-color: #218838;
        }

        .remove-btn {
            background-color: var(--danger-color);
            padding: 8px 12px;
            font-size: 0.9em;
            margin-left: 10px;
        }
        .remove-btn:hover {
            background-color: #c82333;
        }

        /* List/Table */
        .list-section {
            background-color: var(--secondary-bg);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        }

        .list-section h2 {
            color: var(--text-color);
            margin-top: 0;
            margin-bottom: 25px;
            font-size: 1.8em;
            border-bottom: 1px solid var(--dark-grey);
            padding-bottom: 10px;
        }

        .search-list-bar {
            display: flex;
            margin-bottom: 20px;
        }

        .search-list-bar input {
            flex-grow: 1;
            padding: 10px;
            border: 1px solid var(--input-border);
            border-radius: 5px;
            background-color: var(--card-bg);
            color: var(--text-color);
            margin-right: 10px;
        }

        .search-list-bar button {
            background-color: var(--accent-color);
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }

        .search-list-bar button:hover {
            background-color: var(--button-hover);
        }

        .item-list {
            list-style: none;
            padding: 0;
        }

        .item-list li {
            background-color: var(--card-bg);
            padding: 15px 20px;
            margin-bottom: 10px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        .item-list li span {
            flex-grow: 1;
            margin-right: 10px;
            font-weight: 500;
        }

        .item-list li .actions button {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            margin-left: 10px;
            transition: background-color 0.3s ease;
        }

        .item-list li .actions button:hover {
            background-color: #0056b3;
        }

        .item-list li .actions .delete-btn {
            background-color: var(--danger-color);
        }

        .item-list li .actions .delete-btn:hover {
            background-color: #c82333;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
            }
            .admin-nav {
                margin-top: 15px;
                width: 100%;
                display: flex;
                justify-content: space-around;
            }
            .admin-nav a {
                margin: 0 5px;
            }
            .form-section, .list-section {
                padding: 20px;
            }
            .form-inline {
                flex-direction: column;
                align-items: stretch;
            }
            .form-inline input, .form-inline button {
                width: 100%;
                margin-left: 0;
                margin-top: 10px;
            }
            .item-list li {
                flex-direction: column;
                align-items: flex-start;
            }
            .item-list li span {
                margin-bottom: 10px;
            }
            .item-list li .actions {
                width: 100%;
                display: flex;
                justify-content: flex-end;
            }
            .item-list li .actions button {
                margin-left: 0;
                margin-right: 10px;
            }
        }
    </style>
</head>
<body>
    <header>
        <a href="/" class="logo">Admin<span>Panel</span></a>
        <nav class="admin-nav">
            <a href="/admin/add_movie">Add Movie</a>
            <a href="/admin/add_series">Add Series</a>
            <a href="/admin/list_movies">List Movies</a>
            <a href="/admin/list_series">List Series</a>
            <a href="/admin/featured">Featured Movies</a>
        </nav>
    </header>

    <div class="container">
        <h1>Admin Dashboard</h1>

        <section class="form-section">
            <h2>Add New Movie</h2>
            <form id="addMovieForm" action="/admin/add_movie" method="post">
                <div class="form-group">
                    <label for="movie_title">Movie Title:</label>
                    <input type="text" id="movie_title" name="title" required>
                    <button type="button" class="tmdb-fetch-button" onclick="fetchTmdbMovieDetails()">Fetch from TMDb</button>
                </div>
                <div class="form-group">
                    <label for="movie_description">Description:</label>
                    <textarea id="movie_description" name="description"></textarea>
                </div>
                <div class="form-group">
                    <label for="movie_release_date">Release Date (YYYY-MM-DD):</label>
                    <input type="text" id="movie_release_date" name="release_date">
                </div>
                <div class="form-group">
                    <label for="movie_poster_url">Poster URL:</label>
                    <input type="url" id="movie_poster_url" name="poster_url">
                </div>
                <div class="form-group">
                    <label for="movie_backdrop_url">Backdrop URL:</label>
                    <input type="url" id="movie_backdrop_url" name="backdrop_url">
                </div>
                <div class="form-group">
                    <label for="movie_trailer_url">Trailer URL (YouTube Embed):</label>
                    <input type="url" id="movie_trailer_url" name="trailer_url">
                </div>
                 <div class="form-group">
                    <label for="movie_rating">Rating (0-10):</label>
                    <input type="number" step="0.1" id="movie_rating" name="rating" min="0" max="10">
                </div>
                <div class="form-group">
                    <label for="movie_genres">Genres (comma separated):</label>
                    <input type="text" id="movie_genres" name="genres">
                </div>
                <div class="form-group">
                    <label for="movie_duration">Duration (e.g., 2h 30m):</label>
                    <input type="text" id="movie_duration" name="duration">
                </div>

                <h3>Download Links:</h3>
                <div id="movie_download_links">
                    </div>
                <button type="button" class="add-link-btn" onclick="addDownloadLink('movie')">Add Download Link</button>
                
                <div class="form-group" style="margin-top: 20px;">
                    <button type="submit">Add Movie</button>
                </div>
            </form>
        </section>

        <section class="form-section">
            <h2>Add New Series</h2>
            <form id="addSeriesForm" action="/admin/add_series" method="post">
                <div class="form-group">
                    <label for="series_title">Series Title:</label>
                    <input type="text" id="series_title" name="title" required>
                    <button type="button" class="tmdb-fetch-button" onclick="fetchTmdbSeriesDetails()">Fetch from TMDb</button>
                </div>
                <div class="form-group">
                    <label for="series_description">Description:</label>
                    <textarea id="series_description" name="description"></textarea>
                </div>
                <div class="form-group">
                    <label for="series_release_date">First Air Date (YYYY-MM-DD):</label>
                    <input type="text" id="series_release_date" name="release_date">
                </div>
                <div class="form-group">
                    <label for="series_poster_url">Poster URL:</label>
                    <input type="url" id="series_poster_url" name="poster_url">
                </div>
                <div class="form-group">
                    <label for="series_backdrop_url">Backdrop URL:</label>
                    <input type="url" id="series_backdrop_url" name="backdrop_url">
                </div>
                <div class="form-group">
                    <label for="series_trailer_url">Trailer URL (YouTube Embed):</label>
                    <input type="url" id="series_trailer_url" name="trailer_url">
                </div>
                 <div class="form-group">
                    <label for="series_rating">Rating (0-10):</label>
                    <input type="number" step="0.1" id="series_rating" name="rating" min="0" max="10">
                </div>
                <div class="form-group">
                    <label for="series_genres">Genres (comma separated):</label>
                    <input type="text" id="series_genres" name="genres">
                </div>

                <h3>Episodes:</h3>
                <div id="series_episodes">
                    </div>
                <button type="button" class="add-episode-btn" onclick="addEpisode()">Add Episode</button>

                <div class="form-group" style="margin-top: 20px;">
                    <button type="submit">Add Series</button>
                </div>
            </form>
        </section>

        <section class="list-section">
            <h2>Manage Movies</h2>
            <div class="search-list-bar">
                <input type="text" id="search_movie_query" placeholder="Search movies...">
                <button onclick="searchAdminList('movie')">Search</button>
            </div>
            <ul id="movie_list" class="item-list">
                {% for movie in movies %}
                <li>
                    <span>{{ movie.title }}</span>
                    <div class="actions">
                        <button onclick="window.location.href='/admin/edit_movie/{{ movie._id }}'">Edit</button>
                        <button class="delete-btn" onclick="confirmDelete('movie', '{{ movie._id }}')">Delete</button>
                    </div>
                </li>
                {% endfor %}
            </ul>
        </section>

        <section class="list-section" style="margin-top: 40px;">
            <h2>Manage Series</h2>
            <div class="search-list-bar">
                <input type="text" id="search_series_query" placeholder="Search series...">
                <button onclick="searchAdminList('series')">Search</button>
            </div>
            <ul id="series_list" class="item-list">
                {% for series in all_series %}
                <li>
                    <span>{{ series.title }}</span>
                    <div class="actions">
                        <button onclick="window.location.href='/admin/edit_series/{{ series._id }}'">Edit</button>
                        <button class="delete-btn" onclick="confirmDelete('series', '{{ series._id }}')">Delete</button>
                    </div>
                </li>
                {% endfor %}
            </ul>
        </section>

        <section class="list-section" style="margin-top: 40px;">
            <h2>Manage Featured Movies</h2>
            <p>Select movies to feature on the homepage slider. Max 5 allowed.</p>
            <form action="/admin/featured" method="post">
                <div class="form-group">
                    <label for="select_featured_movie">Add Movie to Featured:</label>
                    <select id="select_featured_movie" name="movie_id" required>
                        <option value="">-- Select a movie --</option>
                        {% for movie in all_movies_for_featured %}
                            <option value="{{ movie._id }}">{{ movie.title }}</option>
                        {% endfor %}
                    </select>
                    <button type="submit" name="action" value="add_featured" style="margin-left: 10px;">Add to Featured</button>
                </div>
            </form>
            <ul class="item-list">
                {% for f_movie in current_featured_movies %}
                <li>
                    <span>{{ f_movie.title }}</span>
                    <div class="actions">
                        <form action="/admin/featured" method="post" style="display:inline;">
                            <input type="hidden" name="movie_id" value="{{ f_movie._id }}">
                            <button type="submit" name="action" value="remove_featured" class="delete-btn">Remove</button>
                        </form>
                    </div>
                </li>
                {% endfor %}
            </ul>
        </section>

    </div>

    <script>
        function addDownloadLink(type) {
            const container = document.getElementById(`${type}_download_links`);
            const div = document.createElement('div');
            div.className = 'form-inline';
            div.innerHTML = `
                <input type="text" name="${type}_download_source[]" placeholder="Source (e.g., Server 1)" required>
                <input type="text" name="${type}_download_quality[]" placeholder="Quality (e.g., 1080p)" required>
                <input type="url" name="${type}_download_url[]" placeholder="URL" required>
                <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
            `;
            container.appendChild(div);
        }

        function addEpisode() {
            const container = document.getElementById('series_episodes');
            const div = document.createElement('div');
            div.className = 'form-inline';
            div.innerHTML = `
                <input type="number" name="episode_season[]" placeholder="Season" required style="width: 80px;">
                <input type="number" name="episode_number[]" placeholder="Episode No." required style="width: 100px;">
                <input type="text" name="episode_title[]" placeholder="Episode Title" required>
                <input type="text" name="episode_quality[]" placeholder="Quality (e.g., 720p)" required>
                <input type="url" name="episode_url[]" placeholder="URL" required>
                <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
            `;
            container.appendChild(div);
        }

        function fetchTmdbMovieDetails() {
            const title = document.getElementById('movie_title').value;
            if (!title) {
                alert('Please enter a movie title to fetch from TMDb.');
                return;
            }
            fetch(`/admin/fetch_tmdb_movie?title=${encodeURIComponent(title)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('movie_description').value = data.description || '';
                        document.getElementById('movie_release_date').value = data.release_date || '';
                        document.getElementById('movie_poster_url').value = data.poster_url || '';
                        document.getElementById('movie_backdrop_url').value = data.backdrop_url || '';
                        document.getElementById('movie_trailer_url').value = data.trailer_url || '';
                        document.getElementById('movie_rating').value = data.rating || '';
                        document.getElementById('movie_genres').value = data.genres ? data.genres.join(', ') : '';
                    } else {
                        alert('Could not fetch movie details from TMDb. Please enter manually.');
                    }
                })
                .catch(error => {
                    console.error('Error fetching TMDb movie details:', error);
                    alert('An error occurred while fetching TMDb details.');
                });
        }

        function fetchTmdbSeriesDetails() {
            const title = document.getElementById('series_title').value;
            if (!title) {
                alert('Please enter a series title to fetch from TMDb.');
                return;
            }
            fetch(`/admin/fetch_tmdb_series?title=${encodeURIComponent(title)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('series_description').value = data.description || '';
                        document.getElementById('series_release_date').value = data.release_date || '';
                        document.getElementById('series_poster_url').value = data.poster_url || '';
                        document.getElementById('series_backdrop_url').value = data.backdrop_url || '';
                        document.getElementById('series_trailer_url').value = data.trailer_url || '';
                        document.getElementById('series_rating').value = data.rating || '';
                        document.getElementById('series_genres').value = data.genres ? data.genres.join(', ') : '';
                    } else {
                        alert('Could not fetch series details from TMDb. Please enter manually.');
                    }
                })
                .catch(error => {
                    console.error('Error fetching TMDb series details:', error);
                    alert('An error occurred while fetching TMDb details.');
                });
        }

        function confirmDelete(type, id) {
            if (confirm(`Are you sure you want to delete this ${type}?`)) {
                fetch(`/admin/delete_${type}/${id}`, {
                    method: 'POST',
                }).then(response => {
                    if (response.ok) {
                        location.reload(); // Reload page to reflect changes
                    } else {
                        alert(`Failed to delete ${type}.`);
                    }
                }).catch(error => {
                    console.error('Error deleting:', error);
                    alert('An error occurred during deletion.');
                });
            }
        }

        function searchAdminList(type) {
            const query = document.getElementById(`search_${type}_query`).value.toLowerCase();
            const listItems = document.getElementById(`${type}_list`).getElementsByTagName('li');
            
            for (let i = 0; i < listItems.length; i++) {
                const title = listItems[i].querySelector('span').textContent.toLowerCase();
                if (title.includes(query)) {
                    listItems[i].style.display = 'flex';
                } else {
                    listItems[i].style.display = 'none';
                }
            }
        }

        // For edit pages, if download links or episodes exist, populate them
        // This part would be added in the edit_movie/edit_series HTML if needed
    </script>
</body>
</html>
"""

# edit_movie.html
edit_movie_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Movie - {{ movie.title }}</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary-bg: #1a1a1a;
            --secondary-bg: #2a2a2a;
            --card-bg: #333;
            --text-color: #f0f0f0;
            --accent-color: #e50914;
            --light-grey: #bbb;
            --dark-grey: #555;
            --input-border: #444;
            --button-hover: #c11119;
            --danger-color: #dc3545;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--primary-bg);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }

        .container {
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background-color: var(--secondary-bg);
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        }

        /* Header (similar to main site and admin) */
        header {
            background-color: var(--secondary-bg);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            margin-bottom: 30px;
        }

        .logo {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--accent-color);
            text-decoration: none;
            letter-spacing: 1px;
        }

        .logo span {
            color: var(--text-color);
            margin-left: 5px;
        }

        .admin-nav a {
            color: var(--text-color);
            text-decoration: none;
            margin-left: 20px;
            font-weight: 600;
            transition: color 0.3s ease;
        }

        .admin-nav a:hover {
            color: var(--accent-color);
        }

        h1 {
            color: var(--accent-color);
            margin-bottom: 30px;
            text-align: center;
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 10px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--light-grey);
        }

        .form-group input[type="text"],
        .form-group input[type="url"],
        .form-group input[type="number"],
        .form-group textarea {
            width: calc(100% - 20px);
            padding: 12px;
            border: 1px solid var(--input-border);
            border-radius: 5px;
            background-color: var(--card-bg);
            color: var(--text-color);
            font-size: 1em;
            box-sizing: border-box;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .form-group input:focus,
        .form-group textarea:focus {
            border-color: var(--accent-color);
            outline: none;
            box-shadow: 0 0 0 2px rgba(229, 9, 20, 0.3);
        }

        .form-group button {
            background-color: var(--accent-color);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 5px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }

        .form-group button:hover {
            background-color: var(--button-hover);
        }

        .form-inline {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            align-items: flex-end;
            flex-wrap: wrap; /* Allow wrapping on smaller screens */
        }

        .form-inline input {
            flex-grow: 1;
            min-width: 120px; /* Ensure inputs don't become too small */
        }

        .add-link-btn {
            background-color: #28a745; /* Green for add */
            margin-top: 10px; /* Space from last link */
        }
        .add-link-btn:hover {
            background-color: #218838;
        }

        .remove-btn {
            background-color: var(--danger-color);
            padding: 8px 12px;
            font-size: 0.9em;
            margin-left: auto; /* Push to the right */
        }
        .remove-btn:hover {
            background-color: #c82333;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
            }
            .admin-nav {
                margin-top: 15px;
                width: 100%;
                display: flex;
                justify-content: space-around;
            }
            .admin-nav a {
                margin: 0 5px;
            }
            .container {
                margin: 20px;
                padding: 15px;
            }
            h1 {
                font-size: 1.8em;
            }
            .form-inline {
                flex-direction: column;
                align-items: stretch;
            }
            .form-inline input, .form-inline button {
                width: 100%;
                margin-left: 0;
                margin-top: 10px;
            }
        }
    </style>
</head>
<body>
    <header>
        <a href="/admin" class="logo">Admin<span>Panel</span></a>
        <nav class="admin-nav">
            <a href="/admin/add_movie">Add Movie</a>
            <a href="/admin/add_series">Add Series</a>
            <a href="/admin/list_movies">List Movies</a>
            <a href="/admin/list_series">List Series</a>
            <a href="/admin/featured">Featured Movies</a>
        </nav>
    </header>

    <div class="container">
        <h1>Edit Movie: {{ movie.title }}</h1>
        <form action="/admin/edit_movie/{{ movie._id }}" method="post">
            <div class="form-group">
                <label for="title">Movie Title:</label>
                <input type="text" id="title" name="title" value="{{ movie.title }}" required>
            </div>
            <div class="form-group">
                <label for="description">Description:</label>
                <textarea id="description" name="description">{{ movie.description }}</textarea>
            </div>
            <div class="form-group">
                <label for="release_date">Release Date (YYYY-MM-DD):</label>
                <input type="text" id="release_date" name="release_date" value="{{ movie.release_date }}">
            </div>
            <div class="form-group">
                <label for="poster_url">Poster URL:</label>
                <input type="url" id="poster_url" name="poster_url" value="{{ movie.poster_url }}">
            </div>
            <div class="form-group">
                <label for="backdrop_url">Backdrop URL:</label>
                <input type="url" id="backdrop_url" name="backdrop_url" value="{{ movie.backdrop_url }}">
            </div>
            <div class="form-group">
                <label for="trailer_url">Trailer URL (YouTube Embed):</label>
                <input type="url" id="trailer_url" name="trailer_url" value="{{ movie.trailer_url }}">
            </div>
             <div class="form-group">
                <label for="rating">Rating (0-10):</label>
                <input type="number" step="0.1" id="rating" name="rating" value="{{ movie.rating }}" min="0" max="10">
            </div>
            <div class="form-group">
                <label for="genres">Genres (comma separated):</label>
                <input type="text" id="genres" name="genres" value="{{ movie.genres | join(', ') }}">
            </div>
            <div class="form-group">
                <label for="duration">Duration (e.g., 2h 30m):</label>
                <input type="text" id="duration" name="duration" value="{{ movie.duration }}">
            </div>

            <h3>Download Links:</h3>
            <div id="download_links_container">
                {% if movie.download_links %}
                    {% for link in movie.download_links %}
                        <div class="form-inline">
                            <input type="text" name="download_source[]" placeholder="Source" value="{{ link.source }}" required>
                            <input type="text" name="download_quality[]" placeholder="Quality" value="{{ link.quality }}" required>
                            <input type="url" name="download_url[]" placeholder="URL" value="{{ link.url }}" required>
                            <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
                        </div>
                    {% endfor %}
                {% endif %}
            </div>
            <button type="button" class="add-link-btn" onclick="addDownloadLink('download_links_container')">Add Download Link</button>
            
            <div class="form-group" style="margin-top: 20px;">
                <button type="submit">Update Movie</button>
            </div>
        </form>
    </div>

    <script>
        function addDownloadLink(containerId) {
            const container = document.getElementById(containerId);
            const div = document.createElement('div');
            div.className = 'form-inline';
            div.innerHTML = `
                <input type="text" name="download_source[]" placeholder="Source (e.g., Server 1)" required>
                <input type="text" name="download_quality[]" placeholder="Quality (e.g., 1080p)" required>
                <input type="url" name="download_url[]" placeholder="URL" required>
                <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
            `;
            container.appendChild(div);
        }
    </script>
</body>
</html>
"""

# edit_series.html
edit_series_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Series - {{ series.title }}</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary-bg: #1a1a1a;
            --secondary-bg: #2a2a2a;
            --card-bg: #333;
            --text-color: #f0f0f0;
            --accent-color: #e50914;
            --light-grey: #bbb;
            --dark-grey: #555;
            --input-border: #444;
            --button-hover: #c11119;
            --danger-color: #dc3545;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--primary-bg);
            color: var(--text-color);
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }

        .container {
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background-color: var(--secondary-bg);
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        }

        /* Header (similar to main site and admin) */
        header {
            background-color: var(--secondary-bg);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            margin-bottom: 30px;
        }

        .logo {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--accent-color);
            text-decoration: none;
            letter-spacing: 1px;
        }

        .logo span {
            color: var(--text-color);
            margin-left: 5px;
        }

        .admin-nav a {
            color: var(--text-color);
            text-decoration: none;
            margin-left: 20px;
            font-weight: 600;
            transition: color 0.3s ease;
        }

        .admin-nav a:hover {
            color: var(--accent-color);
        }

        h1 {
            color: var(--accent-color);
            margin-bottom: 30px;
            text-align: center;
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 10px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--light-grey);
        }

        .form-group input[type="text"],
        .form-group input[type="url"],
        .form-group input[type="number"],
        .form-group textarea {
            width: calc(100% - 20px);
            padding: 12px;
            border: 1px solid var(--input-border);
            border-radius: 5px;
            background-color: var(--card-bg);
            color: var(--text-color);
            font-size: 1em;
            box-sizing: border-box;
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .form-group input:focus,
        .form-group textarea:focus {
            border-color: var(--accent-color);
            outline: none;
            box-shadow: 0 0 0 2px rgba(229, 9, 20, 0.3);
        }

        .form-group button {
            background-color: var(--accent-color);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 5px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }

        .form-group button:hover {
            background-color: var(--button-hover);
        }

        .form-inline {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            align-items: flex-end;
            flex-wrap: wrap;
        }

        .form-inline input {
            flex-grow: 1;
            min-width: 80px;
        }
        .form-inline input[type="number"] {
            flex-grow: 0;
        }


        .add-episode-btn {
            background-color: #28a745; /* Green for add */
            margin-top: 10px;
        }
        .add-episode-btn:hover {
            background-color: #218838;
        }

        .remove-btn {
            background-color: var(--danger-color);
            padding: 8px 12px;
            font-size: 0.9em;
            margin-left: auto;
        }
        .remove-btn:hover {
            background-color: #c82333;
        }

        /* Responsive adjustments */
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
            }
            .admin-nav {
                margin-top: 15px;
                width: 100%;
                display: flex;
                justify-content: space-around;
            }
            .admin-nav a {
                margin: 0 5px;
            }
            .container {
                margin: 20px;
                padding: 15px;
            }
            h1 {
                font-size: 1.8em;
            }
            .form-inline {
                flex-direction: column;
                align-items: stretch;
            }
            .form-inline input, .form-inline button {
                width: 100%;
                margin-left: 0;
                margin-top: 10px;
            }
        }
    </style>
</head>
<body>
    <header>
        <a href="/admin" class="logo">Admin<span>Panel</span></a>
        <nav class="admin-nav">
            <a href="/admin/add_movie">Add Movie</a>
            <a href="/admin/add_series">Add Series</a>
            <a href="/admin/list_movies">List Movies</a>
            <a href="/admin/list_series">List Series</a>
            <a href="/admin/featured">Featured Movies</a>
        </nav>
    </header>

    <div class="container">
        <h1>Edit Series: {{ series.title }}</h1>
        <form action="/admin/edit_series/{{ series._id }}" method="post">
            <div class="form-group">
                <label for="title">Series Title:</label>
                <input type="text" id="title" name="title" value="{{ series.title }}" required>
            </div>
            <div class="form-group">
                <label for="description">Description:</label>
                <textarea id="description" name="description">{{ series.description }}</textarea>
            </div>
            <div class="form-group">
                <label for="release_date">First Air Date (YYYY-MM-DD):</label>
                <input type="text" id="release_date" name="release_date" value="{{ series.release_date }}">
            </div>
            <div class="form-group">
                <label for="poster_url">Poster URL:</label>
                <input type="url" id="poster_url" name="poster_url" value="{{ series.poster_url }}">
            </div>
            <div class="form-group">
                <label for="backdrop_url">Backdrop URL:</label>
                <input type="url" id="backdrop_url" name="backdrop_url" value="{{ series.backdrop_url }}">
            </div>
            <div class="form-group">
                <label for="trailer_url">Trailer URL (YouTube Embed):</label>
                <input type="url" id="trailer_url" name="trailer_url" value="{{ series.trailer_url }}">
            </div>
            <div class="form-group">
                <label for="rating">Rating (0-10):</label>
                <input type="number" step="0.1" id="rating" name="rating" value="{{ series.rating }}" min="0" max="10">
            </div>
            <div class="form-group">
                <label for="genres">Genres (comma separated):</label>
                <input type="text" id="genres" name="genres" value="{{ series.genres | join(', ') }}">
            </div>

            <h3>Episodes:</h3>
            <div id="episodes_container">
                {% if series.episodes %}
                    {% for episode in series.episodes %}
                        <div class="form-inline">
                            <input type="number" name="episode_season[]" placeholder="Season" value="{{ episode.season }}" required style="width: 80px;">
                            <input type="number" name="episode_number[]" placeholder="Episode No." value="{{ episode.episode_number }}" required style="width: 100px;">
                            <input type="text" name="episode_title[]" placeholder="Episode Title" value="{{ episode.title }}" required>
                            <input type="text" name="episode_quality[]" placeholder="Quality (e.g., 720p)" value="{{ episode.quality }}" required>
                            <input type="url" name="episode_url[]" placeholder="URL" value="{{ episode.url }}" required>
                            <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
                        </div>
                    {% endfor %}
                {% endif %}
            </div>
            <button type="button" class="add-episode-btn" onclick="addEpisode('episodes_container')">Add Episode</button>

            <div class="form-group" style="margin-top: 20px;">
                <button type="submit">Update Series</button>
            </div>
        </form>
    </div>

    <script>
        function addEpisode(containerId) {
            const container = document.getElementById(containerId);
            const div = document.createElement('div');
            div.className = 'form-inline';
            div.innerHTML = `
                <input type="number" name="episode_season[]" placeholder="Season" required style="width: 80px;">
                <input type="number" name="episode_number[]" placeholder="Episode No." required style="width: 100px;">
                <input type="text" name="episode_title[]" placeholder="Episode Title" required>
                <input type="text" name="episode_quality[]" placeholder="Quality (e.g., 720p)" required>
                <input type="url" name="episode_url[]" placeholder="URL" required>
                <button type="button" class="remove-btn" onclick="this.parentNode.remove()">Remove</button>
            `;
            container.appendChild(div);
        }
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def home():
    # Fetch featured movies for slider
    featured_movie_ids = [str(f['_id']) for f in featured_collection.find({})]
    featured_movies = []
    for movie_id_str in featured_movie_ids:
        from bson.objectid import ObjectId # Import ObjectId here
        try:
            movie_obj_id = ObjectId(movie_id_str)
            movie = movies_collection.find_one({'_id': movie_obj_id})
            if movie:
                featured_movies.append(movie)
        except Exception as e:
            print(f"Error fetching featured movie {movie_id_str}: {e}")


    # Fetch latest movies (e.g., last 12 added, sorted by _id descending)
    latest_movies = list(movies_collection.find({}).sort('_id', DESCENDING).limit(12))
    
    # Fetch latest series (e.g., last 12 added, sorted by _id descending)
    latest_series = list(series_collection.find({}).sort('_id', DESCENDING).limit(12))

    # Placeholder for trending and coming soon (you'd implement logic to determine these)
    # For now, using a subset of latest movies/series or dummy data
    trending_movies = list(movies_collection.find({}).sort('rating', DESCENDING).limit(12))
    # Filter out movies that have already been released
    coming_soon_movies = list(movies_collection.find({"release_date": {"$gt": datetime.now().strftime("%Y-%m-%d")}}).sort("release_date", ASCENDING).limit(12))

    # Get all unique genres from movies and series for filtering
    all_movie_genres = movies_collection.distinct('genres')
    all_series_genres = series_collection.distinct('genres')
    all_genres = sorted(list(set(all_movie_genres + all_series_genres)))

    return render_template_string(index_html, 
                                  featured_movies=featured_movies,
                                  trending_movies=trending_movies,
                                  latest_movies=latest_movies,
                                  latest_series=latest_series,
                                  coming_soon_movies=coming_soon_movies,
                                  all_genres=all_genres)

@app.route('/detail/<content_id>')
def detail(content_id):
    from bson.objectid import ObjectId # Import ObjectId here
    try:
        obj_id = ObjectId(content_id)
    except:
        return "Invalid ID", 400

    content = movies_collection.find_one({'_id': obj_id})
    content_type = 'movie'
    if not content:
        content = series_collection.find_one({'_id': obj_id})
        content_type = 'series'
        if not content:
            return "Content not found", 404

    content['type'] = content_type

    # Fetch related content (simple example: by genre)
    related_content = []
    if content.get('genres'):
        if content_type == 'movie':
            related_content = list(movies_collection.find({
                '_id': {'$ne': obj_id},
                'genres': {'$in': content['genres']}
            }).limit(8))
        else: # series
            related_content = list(series_collection.find({
                '_id': {'$ne': obj_id},
                'genres': {'$in': content['genres']}
            }).limit(8))


    return render_template_string(detail_html, content=content, related_content=related_content)

@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    results = []

    if query:
        # Case-insensitive search for movies
        movie_results = list(movies_collection.find({"title": {"$regex": query, "$options": "i"}}).limit(20))
        for movie in movie_results:
            movie['type'] = 'movie'
            results.append(movie)

        # Case-insensitive search for series
        series_results = list(series_collection.find({"title": {"$regex": query, "$options": "i"}}).limit(20))
        for series in series_results:
            series['type'] = 'series'
            results.append(series)
    
    return render_template_string(index_html, 
                                  search_results=results, # Pass results to index.html
                                  query=query,
                                  # Empty other lists to show search results primarily
                                  featured_movies=[],
                                  trending_movies=[],
                                  latest_movies=[],
                                  latest_series=[],
                                  coming_soon_movies=[],
                                  all_genres=[]) # Maybe also hide categories for search results page
                                  
@app.route('/genre/<genre_name>')
def show_genre(genre_name):
    # Find movies and series belonging to this genre
    genre_movies = list(movies_collection.find({"genres": genre_name}).limit(20))
    genre_series = list(series_collection.find({"genres": genre_name}).limit(20))

    # Combine and sort (optional, e.g., by release date)
    genre_content = []
    for item in genre_movies:
        item['type'] = 'movie'
        genre_content.append(item)
    for item in genre_series:
        item['type'] = 'series'
        genre_content.append(item)
    
    # Sort by title for consistent display
    genre_content.sort(key=lambda x: x['title'])

    return render_template_string(index_html, 
                                  genre_name=genre_name,
                                  genre_content=genre_content, # Pass genre content
                                  # Empty other lists
                                  featured_movies=[],
                                  trending_movies=[],
                                  latest_movies=[],
                                  latest_series=[],
                                  coming_soon_movies=[],
                                  all_genres=[]) # Hide categories if only showing genre results

@app.route('/movies')
def list_all_movies():
    all_movies = list(movies_collection.find({}).sort('title', ASCENDING))
    return render_template_string(index_html, 
                                  all_movies=all_movies,
                                  # Empty other lists
                                  featured_movies=[],
                                  trending_movies=[],
                                  latest_movies=[],
                                  latest_series=[],
                                  coming_soon_movies=[],
                                  all_genres=[])

@app.route('/series')
def list_all_series():
    all_series = list(series_collection.find({}).sort('title', ASCENDING))
    return render_template_string(index_html, 
                                  all_series=all_series,
                                  # Empty other lists
                                  featured_movies=[],
                                  trending_movies=[],
                                  latest_movies=[],
                                  latest_series=[],
                                  coming_soon_movies=[],
                                  all_genres=[])


# --- Admin Routes ---

@app.route('/admin')
@requires_auth
def admin_dashboard():
    movies = list(movies_collection.find({}).sort('_id', DESCENDING).limit(10))
    all_series = list(series_collection.find({}).sort('_id', DESCENDING).limit(10))
    all_movies_for_featured = list(movies_collection.find({}, {'title': 1}).sort('title', ASCENDING))
    
    featured_ids = [f['movie_id'] for f in featured_collection.find({})]
    current_featured_movies = []
    from bson.objectid import ObjectId # Import ObjectId here
    for movie_id in featured_ids:
        try:
            obj_id = ObjectId(movie_id)
            movie = movies_collection.find_one({'_id': obj_id})
            if movie:
                current_featured_movies.append(movie)
        except Exception as e:
            print(f"Error fetching featured movie {movie_id}: {e}")

    return render_template_string(admin_html, movies=movies, all_series=all_series, 
                                  all_movies_for_featured=all_movies_for_featured,
                                  current_featured_movies=current_featured_movies)

@app.route('/admin/add_movie', methods=['GET', 'POST'])
@requires_auth
def add_movie():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        release_date = request.form.get('release_date')
        poster_url = request.form.get('poster_url')
        backdrop_url = request.form.get('backdrop_url')
        trailer_url = request.form.get('trailer_url')
        rating_str = request.form.get('rating')
        genres_str = request.form.get('genres')
        duration = request.form.get('duration')

        download_sources = request.form.getlist('movie_download_source[]')
        download_qualities = request.form.getlist('movie_download_quality[]')
        download_urls = request.form.getlist('movie_download_url[]')
        
        download_links = []
        for i in range(len(download_sources)):
            if download_sources[i] and download_qualities[i] and download_urls[i]:
                download_links.append({
                    'source': download_sources[i],
                    'quality': download_qualities[i],
                    'url': download_urls[i]
                })
        
        rating = float(rating_str) if rating_str else None
        genres = [g.strip() for g in genres_str.split(',')] if genres_str else []

        movie_data = {
            "title": title,
            "description": description,
            "release_date": release_date,
            "poster_url": poster_url,
            "backdrop_url": backdrop_url,
            "trailer_url": trailer_url,
            "rating": rating,
            "genres": genres,
            "duration": duration,
            "download_links": download_links,
            "created_at": datetime.now()
        }
        movies_collection.insert_one(movie_data)
        return redirect(url_for('admin_dashboard'))
    return render_template_string(admin_html, movies=[], all_series=[], add_movie_form=True) # Only render form, lists are not needed

@app.route('/admin/add_series', methods=['GET', 'POST'])
@requires_auth
def add_series():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        release_date = request.form.get('release_date')
        poster_url = request.form.get('poster_url')
        backdrop_url = request.form.get('backdrop_url')
        trailer_url = request.form.get('trailer_url')
        rating_str = request.form.get('rating')
        genres_str = request.form.get('genres')

        episode_seasons = request.form.getlist('episode_season[]')
        episode_numbers = request.form.getlist('episode_number[]')
        episode_titles = request.form.getlist('episode_title[]')
        episode_qualities = request.form.getlist('episode_quality[]')
        episode_urls = request.form.getlist('episode_url[]')

        episodes = []
        for i in range(len(episode_seasons)):
            if episode_seasons[i] and episode_numbers[i] and episode_titles[i] and episode_qualities[i] and episode_urls[i]:
                episodes.append({
                    'season': int(episode_seasons[i]),
                    'episode_number': int(episode_numbers[i]),
                    'title': episode_titles[i],
                    'quality': episode_qualities[i],
                    'url': episode_urls[i]
                })
        
        rating = float(rating_str) if rating_str else None
        genres = [g.strip() for g in genres_str.split(',')] if genres_str else []

        series_data = {
            "title": title,
            "description": description,
            "release_date": release_date,
            "poster_url": poster_url,
            "backdrop_url": backdrop_url,
            "trailer_url": trailer_url,
            "rating": rating,
            "genres": genres,
            "episodes": episodes,
            "created_at": datetime.now()
        }
        series_collection.insert_one(series_data)
        return redirect(url_for('admin_dashboard'))
    return render_template_string(admin_html, movies=[], all_series=[], add_series_form=True) # Only render form

@app.route('/admin/edit_movie/<movie_id>', methods=['GET', 'POST'])
@requires_auth
def edit_movie(movie_id):
    from bson.objectid import ObjectId # Import ObjectId here
    try:
        obj_id = ObjectId(movie_id)
    except:
        return "Invalid Movie ID", 400

    movie = movies_collection.find_one({'_id': obj_id})
    if not movie:
        return "Movie not found", 404

    if request.method == 'POST':
        movie['title'] = request.form['title']
        movie['description'] = request.form.get('description')
        movie['release_date'] = request.form.get('release_date')
        movie['poster_url'] = request.form.get('poster_url')
        movie['backdrop_url'] = request.form.get('backdrop_url')
        movie['trailer_url'] = request.form.get('trailer_url')
        movie['rating'] = float(request.form.get('rating')) if request.form.get('rating') else None
        movie['genres'] = [g.strip() for g in request.form.get('genres').split(',')] if request.form.get('genres') else []
        movie['duration'] = request.form.get('duration')

        download_sources = request.form.getlist('download_source[]')
        download_qualities = request.form.getlist('download_quality[]')
        download_urls = request.form.getlist('download_url[]')
        
        updated_download_links = []
        for i in range(len(download_sources)):
            if download_sources[i] and download_qualities[i] and download_urls[i]:
                updated_download_links.append({
                    'source': download_sources[i],
                    'quality': download_qualities[i],
                    'url': download_urls[i]
                })
        movie['download_links'] = updated_download_links

        movies_collection.update_one({'_id': obj_id}, {'$set': movie})
        return redirect(url_for('admin_dashboard'))
    
    return render_template_string(edit_movie_html, movie=movie)

@app.route('/admin/edit_series/<series_id>', methods=['GET', 'POST'])
@requires_auth
def edit_series(series_id):
    from bson.objectid import ObjectId # Import ObjectId here
    try:
        obj_id = ObjectId(series_id)
    except:
        return "Invalid Series ID", 400

    series = series_collection.find_one({'_id': obj_id})
    if not series:
        return "Series not found", 404

    if request.method == 'POST':
        series['title'] = request.form['title']
        series['description'] = request.form.get('description')
        series['release_date'] = request.form.get('release_date')
        series['poster_url'] = request.form.get('poster_url')
        series['backdrop_url'] = request.form.get('backdrop_url')
        series['trailer_url'] = request.form.get('trailer_url')
        series['rating'] = float(request.form.get('rating')) if request.form.get('rating') else None
        series['genres'] = [g.strip() for g in request.form.get('genres').split(',')] if request.form.get('genres') else []

        episode_seasons = request.form.getlist('episode_season[]')
        episode_numbers = request.form.getlist('episode_number[]')
        episode_titles = request.form.getlist('episode_title[]')
        episode_qualities = request.form.getlist('episode_quality[]')
        episode_urls = request.form.getlist('episode_url[]')

        updated_episodes = []
        for i in range(len(episode_seasons)):
            if episode_seasons[i] and episode_numbers[i] and episode_titles[i] and episode_qualities[i] and episode_urls[i]:
                updated_episodes.append({
                    'season': int(episode_seasons[i]),
                    'episode_number': int(episode_numbers[i]),
                    'title': episode_titles[i],
                    'quality': episode_qualities[i],
                    'url': episode_urls[i]
                })
        series['episodes'] = updated_episodes

        series_collection.update_one({'_id': obj_id}, {'$set': series})
        return redirect(url_for('admin_dashboard'))
    
    return render_template_string(edit_series_html, series=series)

@app.route('/admin/delete_movie/<movie_id>', methods=['POST'])
@requires_auth
def delete_movie(movie_id):
    from bson.objectid import ObjectId # Import ObjectId here
    try:
        obj_id = ObjectId(movie_id)
    except:
        return jsonify({"success": False, "message": "Invalid Movie ID"}), 400
    
    movies_collection.delete_one({'_id': obj_id})
    # Also remove from featured if it was featured
    featured_collection.delete_one({'movie_id': movie_id})
    return jsonify({"success": True, "message": "Movie deleted successfully"})

@app.route('/admin/delete_series/<series_id>', methods=['POST'])
@requires_auth
def delete_series(series_id):
    from bson.objectid import ObjectId # Import ObjectId here
    try:
        obj_id = ObjectId(series_id)
    except:
        return jsonify({"success": False, "message": "Invalid Series ID"}), 400
    
    series_collection.delete_one({'_id': obj_id})
    return jsonify({"success": True, "message": "Series deleted successfully"})

@app.route('/admin/list_movies')
@requires_auth
def list_movies():
    movies = list(movies_collection.find({}).sort('_id', DESCENDING))
    all_series = list(series_collection.find({}).sort('_id', DESCENDING).limit(10)) # Just for common template rendering
    all_movies_for_featured = list(movies_collection.find({}, {'title': 1}).sort('title', ASCENDING))
    featured_ids = [f['movie_id'] for f in featured_collection.find({})]
    current_featured_movies = []
    from bson.objectid import ObjectId # Import ObjectId here
    for movie_id in featured_ids:
        try:
            obj_id = ObjectId(movie_id)
            movie = movies_collection.find_one({'_id': obj_id})
            if movie:
                current_featured_movies.append(movie)
        except Exception as e:
            print(f"Error fetching featured movie {movie_id}: {e}")
    return render_template_string(admin_html, movies=movies, all_series=all_series, 
                                  all_movies_for_featured=all_movies_for_featured,
                                  current_featured_movies=current_featured_movies)

@app.route('/admin/list_series')
@requires_auth
def list_series():
    all_series = list(series_collection.find({}).sort('_id', DESCENDING))
    movies = list(movies_collection.find({}).sort('_id', DESCENDING).limit(10)) # Just for common template rendering
    all_movies_for_featured = list(movies_collection.find({}, {'title': 1}).sort('title', ASCENDING))
    featured_ids = [f['movie_id'] for f in featured_collection.find({})]
    current_featured_movies = []
    from bson.objectid import ObjectId # Import ObjectId here
    for movie_id in featured_ids:
        try:
            obj_id = ObjectId(movie_id)
            movie = movies_collection.find_one({'_id': obj_id})
            if movie:
                current_featured_movies.append(movie)
        except Exception as e:
            print(f"Error fetching featured movie {movie_id}: {e}")
    return render_template_string(admin_html, movies=movies, all_series=all_series, 
                                  all_movies_for_featured=all_movies_for_featured,
                                  current_featured_movies=current_featured_movies)

@app.route('/admin/fetch_tmdb_movie')
@requires_auth
def fetch_tmdb_movie():
    title = request.args.get('title')
    if not title:
        return jsonify({"success": False, "message": "Title is required"}), 400
    
    details = get_movie_details_from_tmdb(title)
    if details:
        details['success'] = True
        return jsonify(details)
    else:
        return jsonify({"success": False, "message": "Movie not found on TMDb"}), 404

@app.route('/admin/fetch_tmdb_series')
@requires_auth
def fetch_tmdb_series():
    title = request.args.get('title')
    if not title:
        return jsonify({"success": False, "message": "Title is required"}), 400
    
    details = get_series_details_from_tmdb(title)
    if details:
        details['success'] = True
        return jsonify(details)
    else:
        return jsonify({"success": False, "message": "Series not found on TMDb"}), 404

@app.route('/admin/featured', methods=['GET', 'POST'])
@requires_auth
def manage_featured():
    if request.method == 'POST':
        action = request.form.get('action')
        movie_id_to_manage = request.form.get('movie_id')

        if not movie_id_to_manage:
            return redirect(url_for('admin_dashboard')) # Or show an error

        if action == 'add_featured':
            # Check if already exists or limit exceeded
            if featured_collection.count_documents({}) >= 5:
                # Limit to 5 featured movies
                print("Cannot add more than 5 featured movies.") # Log or flash message
            else:
                existing_featured = featured_collection.find_one({'movie_id': movie_id_to_manage})
                if not existing_featured:
                    featured_collection.insert_one({'movie_id': movie_id_to_manage, 'added_at': datetime.now()})
        elif action == 'remove_featured':
            featured_collection.delete_one({'movie_id': movie_id_to_manage})
        
        return redirect(url_for('admin_dashboard')) # Redirect back to admin for update

    # GET request for /admin/featured
    return redirect(url_for('admin_dashboard'))

# To serve static files like favicon.ico
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Create a 'static' directory if it doesn't exist for favicon
    if not os.path.exists('static'):
        os.makedirs('static')
    # You might want to place a favicon.ico file inside the 'static' directory
    # For example, if you have a file named 'favicon.ico' in your project root,
    # you can copy it to 'static' or just create an empty file there.

    # Example: Create a dummy favicon if not exists
    favicon_path = os.path.join('static', 'favicon.ico')
    if not os.path.exists(favicon_path):
        try:
            # Create a simple, minimal ICO file (can be replaced with a proper one)
            # This is a very basic placeholder, real favicons are more complex.
            with open(favicon_path, 'wb') as f:
                f.write(b'\\x00\\x00\\x01\\x00\\x01\\x00\\x10\\x10\\x00\\x00\\x01\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x16\\x00\\x00\\x00(\\x00\\x00\\x00\\x10\\x00\\x00\\x00\\x10\\x00\\x00\\x00\\x01\\x00\\x18\\x00\\x00\\x00\\x00\\x00@\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00')
            print(f"Created a placeholder favicon at {favicon_path}")
        except Exception as e:
            print(f"Could not create placeholder favicon: {e}")

    app.run(debug=True)
