# app.py

from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests
import os
from functools import wraps
from dotenv import load_dotenv

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# --- Environment Variables & Admin Authentication ---
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

def check_auth(username, password):
    """ইউজারনেম ও পাসওয়ার্ড সঠিক কিনা তা যাচাই করে।"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    """অথেন্টিকেশন ব্যর্থ হলে 401 রেসপন্স পাঠায়।"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """এই ডেকোরেটরটি রুট ফাংশনে অথেন্টিকেশন চেক করে।"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- Environment Variable Checks & Database Connection ---
if not MONGO_URI:
    raise RuntimeError("Error: MONGO_URI environment variable not set. Exiting.")

try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    raise RuntimeError(f"Error connecting to MongoDB: {e}. Exiting.")

# --- TMDb Genre Map ---
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
    10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"
}

# ==============================================================================
# START OF HTML TEMPLATES
# ==============================================================================

# --- NEW index_html TEMPLATE (with Hero Slider and Horizontal Scrollers) ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MovieZone - Your Entertainment Hub</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
<style>
  /* Google Fonts Import */
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Roboto:wght@300;400;700&display=swap');

  /* --- General Styles & Reset --- */
  :root {
      --bg-color: #121212;
      --primary-card-bg: #1f1f1f;
      --secondary-card-bg: #282828;
      --text-primary: #ffffff;
      --text-secondary: #b3b3b3;
      --accent-green: #1db954;
      --accent-blue: #4dabf7;
      --accent-orange: #ff8c00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto', sans-serif;
    background: var(--bg-color);
    color: var(--text-primary);
    -webkit-tap-highlight-color: transparent;
    overflow-x: hidden;
  }
  h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; }
  a { text-decoration: none; color: inherit; }

  /* Custom Scrollbar */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: var(--secondary-card-bg); }
  ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #777; }

  /* --- Header --- */
  header {
    position: sticky; top: 0; z-index: 1000;
    background: rgba(18, 18, 18, 0.85);
    backdrop-filter: blur(10px);
    padding: 10px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.5);
  }
  header h1 {
    font-weight: 700; font-size: 24px;
    background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
    background-size: 400% 400%; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: gradientShift 10s ease infinite;
  }
  @keyframes gradientShift {
    0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%}
  }
  .search-form { flex-grow: 1; margin: 0 20px; }
  .search-input {
      width: 100%; max-width: 400px; padding: 10px 15px; border: 1px solid #333;
      border-radius: 25px; background-color: #282828; color: #e0e0e0;
      font-size: 1em; outline: none; transition: all 0.3s ease;
  }
  .search-input:focus { border-color: var(--accent-green); box-shadow: 0 0 0 3px rgba(29, 185, 84, 0.4); }

  /* --- Main Content --- */
  main {
    max-width: 1400px; margin: 0 auto;
    padding: 20px 15px 80px 15px;
  }

  /* --- Hero Slider --- */
  .hero-slider {
    position: relative;
    width: 100%;
    height: 50vh;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 40px;
    background-color: var(--primary-card-bg);
  }
  .hero-slide {
    position: absolute; top: 0; left: 0;
    width: 100%; height: 100%;
    opacity: 0; transition: opacity 0.8s ease-in-out;
    background-size: cover;
    background-position: center;
  }
  .hero-slide.active { opacity: 1; }
  .hero-slide::after {
    content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(to top, rgba(18,18,18,1) 0%, rgba(18,18,18,0.7) 40%, rgba(18,18,18,0) 100%);
  }
  .hero-content {
    position: absolute; bottom: 30px; left: 30px;
    z-index: 10; max-width: 60%;
  }
  .hero-title { font-size: 2.5rem; margin-bottom: 10px; text-shadow: 2px 2px 8px rgba(0,0,0,0.8); }
  .hero-meta { display: flex; gap: 15px; margin-bottom: 15px; color: var(--text-secondary); }
  .hero-overview {
    font-size: 1rem; line-height: 1.5; color: var(--text-secondary);
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  .slider-nav {
    position: absolute; top: 50%; transform: translateY(-50%);
    z-index: 20; background: rgba(0,0,0,0.5); color: white;
    border: none; border-radius: 50%; width: 40px; height: 40px;
    cursor: pointer; font-size: 1.2rem; transition: background 0.2s;
  }
  .slider-nav:hover { background: rgba(0,0,0,0.8); }
  .slider-nav.prev { left: 15px; }
  .slider-nav.next { right: 15px; }
  
  /* --- Category Section --- */
  .category-section { margin-bottom: 30px; }
  .category-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 15px; padding: 0 5px;
  }
  .category-title { font-size: 1.5rem; color: var(--text-primary); }
  .see-all-btn {
      color: var(--text-secondary); font-size: 0.9rem;
      transition: color 0.2s;
  }
  .see-all-btn:hover { color: var(--accent-green); }

  /* --- Horizontal Movie Scroller --- */
  .movie-scroller {
    display: flex;
    overflow-x: auto;
    overflow-y: hidden;
    gap: 15px;
    padding: 10px 5px;
    -ms-overflow-style: none; /* IE and Edge */
    scrollbar-width: none; /* Firefox */
  }
  .movie-scroller::-webkit-scrollbar { display: none; }

  /* --- Movie Card (Redesigned) --- */
  .movie-card {
    flex: 0 0 160px; /* Fixed width for horizontal scroll */
    width: 160px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: transform 0.2s ease;
  }
  .movie-card:hover { transform: scale(1.05); }

  .movie-poster-wrapper {
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
  }
  .movie-poster {
    width: 100%;
    height: 240px;
    object-fit: cover;
    display: block;
  }
  
  .overlay-badge {
    position: absolute; top: 8px; left: 8px; z-index: 5;
    background: rgba(0, 0, 0, 0.7); color: #fff;
    padding: 3px 8px; border-radius: 4px; font-size: 11px;
    font-weight: bold; text-transform: uppercase;
  }
  .overlay-badge.coming-soon { background-color: var(--accent-blue); }
  .overlay-badge.custom-label { background-color: var(--accent-orange); }

  .quality-badge {
    position: absolute; top: 8px; right: 8px; z-index: 5;
    background: var(--accent-green); color: var(--bg-color);
    padding: 2px 6px; border-radius: 4px; font-size: 11px;
    font-weight: 700;
  }
  .quality-badge.trending {
    background: linear-gradient(45deg, #ff0077, #ff9900);
    color: white;
  }
  
  .movie-card-info { text-align: left; }
  .movie-title {
    font-size: 0.95rem; font-weight: 600; color: var(--text-primary);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    margin-bottom: 2px;
  }
  .movie-title:hover {
    color: var(--accent-blue);
  }
  .movie-year { font-size: 0.8rem; color: var(--text-secondary); }
  
  /* --- Full Page List / Search Results --- */
  .full-page-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 20px;
  }
  .full-page-grid .movie-card {
      width: auto; /* Override fixed width */
      flex-basis: auto;
  }

  /* --- Bottom Navigation --- */
  .bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 1000;
    background: rgba(31, 31, 31, 0.9); backdrop-filter: blur(10px);
    display: flex; justify-content: space-around;
    padding: 8px 0; box-shadow: 0 -2px 10px rgba(0,0,0,0.7);
  }
  .nav-item {
    color: var(--text-secondary); display: flex; flex-direction: column;
    align-items: center; font-size: 0.7rem; transition: color 0.2s ease;
  }
  .nav-item i { font-size: 1.3em; margin-bottom: 4px; }
  .nav-item.active, .nav-item:hover { color: var(--accent-green); }

  /* --- Responsive Adjustments --- */
  @media (max-width: 768px) {
    header { padding: 8px 15px; }
    header h1 { font-size: 20px; }
    .search-form { margin: 0 10px; }
    .hero-slider { height: 40vh; }
    .hero-title { font-size: 1.8rem; }
    .hero-content { left: 20px; bottom: 20px; max-width: 80%; }
    .hero-overview { -webkit-line-clamp: 2; }
    .movie-card { flex: 0 0 140px; width: 140px; }
    .movie-poster { height: 210px; }
    .full-page-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
  }
  @media (max-width: 480px) {
    .movie-card { flex: 0 0 120px; width: 120px; }
    .movie-poster { height: 180px; }
    .full-page-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 15px; }
    .hero-title { font-size: 1.5rem; }
  }
</style>
</head>
<body>

<header>
  <h1>MovieZone</h1>
  <form method="GET" action="{{ url_for('home') }}" class="search-form">
    <input type="search" name="q" class="search-input" placeholder="Search movies & series..." value="{{ query|default('') }}" />
  </form>
</header>

<main>
  {% if is_full_page_list %}
    {# --- Full Page List for Categories/Search --- #}
    <div class="category-header">
      <h2 class="category-title">{{ page_title }}</h2>
    </div>
    {% if movies|length == 0 %}
      <p style="text-align:center; color:var(--text-secondary); margin-top: 40px;">No content found.</p>
    {% else %}
      <div class="full-page-grid">
        {% for m in movies %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    {% endif %}

  {% else %}
    {# --- Homepage with Slider and Scrollers --- #}

    <!-- Hero Slider -->
    {% if slider_movies %}
    <div class="hero-slider">
        {% for m in slider_movies %}
        <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="hero-slide {% if loop.first %}active{% endif %}" style="background-image: url('{{ m.poster }}');">
            <div class="hero-content">
                <h2 class="hero-title">{{ m.title }}</h2>
                <div class="hero-meta">
                    <span>{{ m.year }}</span>
                    {% if m.genres %}<span>·</span><span>{{ m.genres|join(' / ') }}</span>{% endif %}
                </div>
                <p class="hero-overview">{{ m.overview }}</p>
            </div>
        </a>
        {% endfor %}
        <button class="slider-nav prev"><i class="fas fa-chevron-left"></i></button>
        <button class="slider-nav next"><i class="fas fa-chevron-right"></i></button>
    </div>
    {% endif %}

    <!-- Trending Section -->
    {% if trending_movies %}
    <section class="category-section">
      <div class="category-header">
        <h2 class="category-title">Trending</h2>
        <a href="{{ url_for('trending_movies') }}" class="see-all-btn">See All →</a>
      </div>
      <div class="movie-scroller">
        {% for m in trending_movies %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    </section>
    {% endif %}
    
    <!-- Recently Added Section -->
    {% if recently_added %}
    <section class="category-section">
      <div class="category-header">
        <h2 class="category-title">Recently Added</h2>
        <a href="{{ url_for('recently_added_all') }}" class="see-all-btn">See All →</a>
      </div>
      <div class="movie-scroller">
        {% for m in recently_added %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    </section>
    {% endif %}

    <!-- Latest Movies Section -->
    {% if latest_movies %}
    <section class="category-section">
      <div class="category-header">
        <h2 class="category-title">Latest Movies</h2>
        <a href="{{ url_for('movies_only') }}" class="see-all-btn">See All →</a>
      </div>
      <div class="movie-scroller">
        {% for m in latest_movies %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    </section>
    {% endif %}

    <!-- Latest Series Section -->
    {% if latest_series %}
    <section class="category-section">
      <div class="category-header">
        <h2 class="category-title">Latest Web Series</h2>
        <a href="{{ url_for('webseries') }}" class="see-all-btn">See All →</a>
      </div>
      <div class="movie-scroller">
        {% for m in latest_series %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    </section>
    {% endif %}

    <!-- Coming Soon Section -->
    {% if coming_soon_movies %}
    <section class="category-section">
      <div class="category-header">
        <h2 class="category-title">Coming Soon</h2>
        <a href="{{ url_for('coming_soon') }}" class="see-all-btn">See All →</a>
      </div>
      <div class="movie-scroller">
        {% for m in coming_soon_movies %}
          {% include 'movie_card' with context %}
        {% endfor %}
      </div>
    </section>
    {% endif %}

  {% endif %}
</main>

<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' and not request.args.get('q') %}active{% endif %}">
    <i class="fas fa-home"></i>
    <span>Home</span>
  </a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}">
    <i class="fas fa-film"></i>
    <span>Movies</span>
  </a>
  <a href="https://t.me/Movie_Request_Group_23" class="nav-item" target="_blank" rel="noopener">
    <i class="fas fa-plus-circle"></i>
    <span>Request</span>
  </a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}">
    <i class="fas fa-tv"></i>
    <span>Series</span>
  </a>
  <a href="#" class="nav-item" onclick="document.querySelector('.search-input').focus(); return false;">
    <i class="fas fa-search"></i>
    <span>Search</span>
  </a>
</nav>

{%- macro movie_card(m) -%}
<div class="movie-card">
  <a href="{{ url_for('movie_detail', movie_id=m._id) }}">
    <div class="movie-poster-wrapper">
      <img class="movie-poster" src="{{ m.poster if m.poster else 'https://via.placeholder.com/160x240.png/1f1f1f/808080?text=No+Image' }}" alt="{{ m.title }}" loading="lazy">
      
      {% if m.is_coming_soon %}
        <div class="overlay-badge coming-soon">Coming Soon</div>
      {% elif m.top_label %}
        <div class="overlay-badge custom-label">{{ m.top_label }}</div>
      {% elif m.original_language and m.original_language != 'N/A' %}
        <div class="overlay-badge">{{ m.original_language | upper }}</div>
      {% endif %}

      {% if m.quality %}
        <div class="quality-badge {% if m.quality == 'TRENDING' %}trending{% endif %}">
          {% if m.quality == 'TRENDING' %}<i class="fas fa-fire"></i>{% else %}{{ m.quality }}{% endif %}
        </div>
      {% endif %}
    </div>
  </a>
  <div class="movie-card-info">
    <a href="{{ url_for('movie_detail', movie_id=m._id) }}">
        <h3 class="movie-title">{{ m.title }}</h3>
    </a>
    <p class="movie-year">{{ m.year }}</p>
  </div>
</div>
{%- endmacro -%}

<script>
document.addEventListener('DOMContentLoaded', function() {
  const slides = document.querySelectorAll('.hero-slide');
  if (slides.length > 1) {
    const prevBtn = document.querySelector('.slider-nav.prev');
    const nextBtn = document.querySelector('.slider-nav.next');
    let currentSlide = 0;
    let slideInterval;

    function showSlide(n) {
      slides[currentSlide].classList.remove('active');
      currentSlide = (n + slides.length) % slides.length;
      slides[currentSlide].classList.add('active');
    }

    function next() { showSlide(currentSlide + 1); }
    function prev() { showSlide(currentSlide - 1); }

    function startSlider() {
      slideInterval = setInterval(next, 5000); // Change slide every 5 seconds
    }
    
    function stopSlider() {
      clearInterval(slideInterval);
    }

    nextBtn.addEventListener('click', (e) => {
        e.preventDefault();
        next();
        stopSlider();
        startSlider();
    });
    prevBtn.addEventListener('click', (e) => {
        e.preventDefault();
        prev();
        stopSlider();
        startSlider();
    });
    
    startSlider();
  } else if (slides.length <= 1) {
      const navButtons = document.querySelectorAll('.slider-nav');
      navButtons.forEach(btn => btn.style.display = 'none');
  }
});
</script>

</body>
</html>
"""

# --- YOUR ORIGINAL detail_html TEMPLATE ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{ movie.title if movie else "Movie Not Found" }} - MovieZone Details</title>
<style>
  /* General styles (similar to index_html for consistency) */
  * { box-sizing: border-box; margin: 0; padding: 0;}
  body { margin: 0; background: #121212; color: #eee; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
  a { text-decoration: none; color: inherit; }
  a:hover { color: #1db954; }

  header {
    position: sticky; top: 0; left: 0; right: 0;
    background: #181818; padding: 10px 20px;
    display: flex; justify-content: flex-start; align-items: center; z-index: 100;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.8);
  }
  header h1 {
    margin: 0; font-weight: 700; font-size: 24px;
    background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
    background-size: 400% 400%; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: gradientShift 10s ease infinite;
    flex-grow: 1;
    text-align: center;
  }
  @keyframes gradientShift {
    0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; }
  }
  .back-button {
      color: #1db954;
      font-size: 18px;
      position: absolute;
      left: 20px;
      z-index: 101;
  }
  .back-button i { margin-right: 5px; }

  /* Detail Page Specific Styles */
  .movie-detail-container {
    max-width: 1000px;
    margin: 20px auto;
    padding: 25px;
    background: #181818;
    border-radius: 8px;
    box-shadow: 0 0 15px rgba(0,0,0,0.7);
    display: flex;
    flex-direction: column;
    gap: 25px;
  }

  .main-info {
      display: flex;
      flex-direction: column;
      gap: 25px;
  }

  .detail-poster-wrapper {
      position: relative;
      width: 100%;
      max-width: 300px;
      flex-shrink: 0;
      align-self: center;
  }
  .detail-poster {
    width: 100%;
    height: auto;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    display: block;
  }
  .detail-poster-wrapper .badge {
      position: absolute;
      top: 10px;
      left: 10px;
      font-size: 14px;
      padding: 4px 8px;
      border-radius: 5px;
      background: #1db954; /* Consistent badge color */
      color: #000;
      font-weight: 700;
      text-transform: uppercase;
  }
  .detail-poster-wrapper .badge.trending {
    background: linear-gradient(45deg, #ff0077, #ff9900);
    color: #fff;
  }
  .detail-poster-wrapper .coming-soon-badge {
      position: absolute;
      top: 10px;
      left: 10px;
      font-size: 14px;
      padding: 4px 8px;
      border-radius: 5px;
      background-color: #007bff; /* Blue for Coming Soon */
      color: #fff;
      font-weight: 700;
      text-transform: uppercase;
  }

  .detail-info {
    flex-grow: 1;
  }
  .detail-title {
    font-size: 38px;
    font-weight: 700;
    margin: 0 0 10px 0;
    color: #eee;
    text-shadow: 0 0 5px rgba(0,0,0,0.5);
  }
  .detail-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 15px;
      margin-bottom: 20px;
      font-size: 16px;
      color: #ccc;
  }
  .detail-meta span {
      background: #282828;
      padding: 5px 10px;
      border-radius: 5px;
      white-space: nowrap;
  }
  .detail-meta strong {
      color: #fff;
  }

  .detail-overview {
    font-size: 17px;
    line-height: 1.7;
    color: #ccc;
    margin-bottom: 30px;
  }

  /* --- DOWNLOAD LINKS SECTION --- */
  .download-section {
    width: 100%;
    text-align: center;
    margin-top: 30px;
    background: #1f1f1f;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
  }
  .download-section h3 {
    font-size: 24px;
    font-weight: 700;
    color: #00ff00; /* Green color for heading */
    margin-bottom: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 10px;
  }
  .download-section h3::before,
  .download-section h3::after {
    content: '[↓]';
    color: #00ff00;
    font-size: 20px;
  }

  .download-item {
    margin-bottom: 15px;
  }
  .download-quality-info {
    font-size: 18px;
    color: #ff9900; /* Orange color for quality info */
    margin-bottom: 10px;
    font-weight: 600;
  }
  .download-button-wrapper {
    width: 100%;
    max-width: 300px; /* Limit button width */
    margin: 0 auto;
  }
  .download-button {
    display: block; /* Make button full width of its wrapper */
    padding: 12px 20px;
    border-radius: 30px; /* Pill shape */
    background: linear-gradient(to right, #6a0dad, #8a2be2, #4b0082); /* Purple gradient */
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    border: none;
  }
  .download-button:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 15px rgba(0,0,0,0.7);
    background: linear-gradient(to right, #7b2df2, #9a4beb, #5c1bb2); /* Slightly brighter purple */
  }

  .no-link-message {
      color: #999;
      font-size: 16px;
      text-align: center;
      width: 100%;
      padding: 20px;
      background: #1f1f1f;
      border-radius: 8px;
  }


  /* Responsive Adjustments for Detail Page */
  @media (min-width: 769px) {
      .main-info {
          flex-direction: row;
          align-items: flex-start;
      }
      .detail-poster-wrapper {
          margin-right: 40px;
      }
      .detail-title {
          font-size: 44px;
      }
  }

  @media (max-width: 768px) {
    header h1 { font-size: 20px; margin: 0; }
    .back-button { font-size: 16px; left: 15px; }
    .movie-detail-container { padding: 15px; margin: 15px auto; gap: 15px; }
    .main-info { gap: 15px; }
    .detail-poster-wrapper { max-width: 180px; }
    .detail-poster-wrapper .badge, .detail-poster-wrapper .coming-soon-badge { font-size: 12px; padding: 2px 6px; top: 8px; left: 8px; }
    .detail-title { font-size: 28px; }
    .detail-meta { font-size: 14px; gap: 10px; margin-bottom: 15px; }
    .detail-overview { font-size: 15px; margin-bottom: 20px; }
    
    .download-section h3 { font-size: 20px; }
    .download-section h3::before,
    .download-section h3::after { font-size: 18px; }
    .download-quality-info { font-size: 16px; }
    .download-button { font-size: 16px; padding: 10px 15px; }
  }

  @media (max-width: 480px) {
      .detail-title { font-size: 22px; }
      .detail-meta { font-size: 13px; }
      .detail-overview { font-size: 14px; }
      .download-section h3 { font-size: 18px; }
      .download-section h3::before,
      .download-section h3::after { font-size: 16px; }
      .download-quality-info { font-size: 14px; }
      .download-button { font-size: 14px; padding: 8px 12px; }
  }
  .bottom-nav {
      position: fixed; bottom: 0; left: 0; right: 0;
      background: #1f1f1f; display: flex; justify-content: space-around;
      padding: 10px 0; box-shadow: 0 -2px 5px rgba(0,0,0,0.7); z-index: 200;
    }
  .nav-item {
      display: flex; flex-direction: column; align-items: center;
      color: #ccc; font-size: 12px; text-align: center; transition: color 0.2s ease;
  }
  .nav-item:hover { color: #e44d26; }
  .nav-item i { font-size: 24px; margin-bottom: 4px; }
  @media (max-width: 768px) {
      .bottom-nav { padding: 8px 0; }
      .nav-item { font-size: 10px; }
      .nav-item i { font-size: 20px; margin-bottom: 2px; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body>
<header>
  <a href="javascript:history.back()" class="back-button"><i class="fas fa-arrow-left"></i>Back</a>
  <h1>MovieZone</h1>
</header>
<main>
  {% if movie %}
  <div class="movie-detail-container">
    <div class="main-info">
        <div class="detail-poster-wrapper">
            <img class="detail-poster" src="{{ movie.poster if movie.poster else 'https://via.placeholder.com/300x450.png/1f1f1f/808080?text=No+Image' }}" alt="{{ movie.title }}">
            {% if movie.is_coming_soon %}
                <div class="coming-soon-badge">COMING SOON</div>
            {% elif movie.quality %}
              <div class="badge {% if movie.quality == 'TRENDING' %}trending{% endif %}">{{ movie.quality }}</div>
            {% endif %}
        </div>
        <div class="detail-info">
          <h2 class="detail-title">{{ movie.title }}</h2>
          <div class="detail-meta">
              {% if movie.release_date and movie.release_date != 'N/A' %}<span><strong>Release:</strong> {{ movie.release_date }}</span>{% endif %}
              {% if movie.vote_average %}<span><strong>Rating:</strong> {{ "%.1f"|format(movie.vote_average) }}/10 <i class="fas fa-star" style="color:#FFD700;"></i></span>{% endif %}
              {% if movie.original_language and movie.original_language != 'N/A' %}<span><strong>Language:</strong> {{ movie.original_language | upper }}</span>{% endif %}
              {% if movie.genres %}<span><strong>Genres:</strong> {{ movie.genres | join(', ') }}</span>{% endif %}
          </div>
          <p class="detail-overview">{{ movie.overview }}</p>
        </div>
    </div>
    
    <div class="download-section">
      {% if movie.is_coming_soon %}
        <p class="no-link-message">This content is coming soon. Links will be available after release.</p>
      {% elif movie.type == 'movie' %}
        <h3>Download Links</h3>
        {% if movie.links and movie.links|length > 0 %}
          {% for link_item in movie.links %}
          <div class="download-item">
            <p class="download-quality-info">({{ link_item.quality }}) [{{ link_item.size }}]</p>
            <div class="download-button-wrapper">
              <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">Download</a>
            </div>
          </div>
          {% endfor %}
        {% else %}
          <p class="no-link-message">No download links available yet.</p>
        {% endif %}
      {% elif movie.type == 'series' %}
        <h3>Episodes</h3>
        {% if movie.episodes and movie.episodes|length > 0 %}
            {% for episode in movie.episodes | sort(attribute='episode_number') %}
            <div class="download-item" style="border-top: 1px solid #333; padding-top: 15px; margin-top: 15px;">
              <h4 style="color: #1db954; font-size: 20px; margin-bottom: 10px;">Episode {{ episode.episode_number }}: {{ episode.title }}</h4>
              {% if episode.overview %}<p style="color: #ccc; font-size: 15px; margin-bottom: 10px;">{{ episode.overview }}</p>{% endif %}
              {% if episode.links and episode.links|length > 0 %}
                {% for link_item in episode.links %}
                <div class="download-button-wrapper" style="margin-bottom: 10px;">
                  <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">Download ({{ link_item.quality }}) [{{ link_item.size }}]</a>
                </div>
                {% endfor %}
              {% else %}
                <p class="no-link-message" style="margin-top: 0; padding: 0; background: none;">No download links for this episode.</p>
              {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <p class="no-link-message">No episodes available yet.</p>
        {% endif %}
      {% else %}
        <p class="no-link-message">No download links or episodes available for this content.</p>
      {% endif %}
    </div>

  </div>
  {% else %}
    <p style="text-align:center; color:#999; margin-top: 40px;">Movie not found.</p>
  {% endif %}
</main>
<nav class="bottom-nav">
    <a href="{{ url_for('home') }}" class="nav-item"><i class="fas fa-home"></i><span>Home</span></a>
    <a href="{{ url_for('movies_only') }}" class="nav-item"><i class="fas fa-film"></i><span>Movies</span></a>
    <a href="https://t.me/Movie_Request_Group_23" class="nav-item" target="_blank" rel="noopener"><i class="fas fa-plus-circle"></i><span>Request</span></a>
    <a href="{{ url_for('webseries') }}" class="nav-item"><i class="fas fa-tv"></i><span>Series</span></a>
    <a href="#" class="nav-item" onclick="document.querySelector('.search-input').focus(); return false;"><i class="fas fa-search"></i><span>Search</span></a>
</nav>
</body>
</html>
"""

# --- YOUR ORIGINAL admin_html TEMPLATE ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title>
  <style>
    body { font-family: Arial, sans-serif; background: #121212; color: #eee; padding: 20px; }
    h2 { 
      background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
      background-size: 400% 400%;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: gradientShift 10s ease infinite;
      display: inline-block;
      font-size: 28px;
      margin-bottom: 20px;
    }
    @keyframes gradientShift {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    form { max-width: 600px; margin-bottom: 40px; border: 1px solid #333; padding: 20px; border-radius: 8px;}
    
    .form-group {
        margin-bottom: 15px;
    }
    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: bold;
        color: #ddd;
    }
    input[type="text"], input[type="url"], textarea, button, select, input[type="number"], input[type="search"] { /* Added input[type="search"] */
      width: 100%;
      padding: 10px;
      margin-bottom: 15px;
      border-radius: 5px;
      border: none;
      font-size: 16px;
      background: #222;
      color: #eee;
    }
    input[type="checkbox"] { /* Style for checkbox */
        width: auto; /* Revert width for checkbox */
        margin-right: 10px;
    }
    textarea {
        resize: vertical; /* Allow vertical resizing of textarea */
        min-height: 80px;
    }
    .link-input-group input[type="url"] {
        margin-bottom: 5px;
    }
    .link-input-group p {
        font-size: 14px;
        color: #bbb;
        margin-bottom: 5px;
    }

    button {
      background: #1db954;
      color: #000;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    button:hover {
      background: #17a34a;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }
    th, td {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #333;
    }
    th {
        background: #282828;
        color: #eee;
    }
    td {
        background: #181818;
    }
    .action-buttons {
        display: flex;
        gap: 5px;
    }
    .delete-btn {
        background: #e44d26;
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        transition: background 0.3s ease;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
    }
    .delete-btn:hover {
        background: #d43d16;
    }
    .edit-btn {
        background: #007bff; /* Blue color for edit */
        color: #fff;
        padding: 5px 10px;
        border-radius: 5px;
        text-decoration: none;
        font-size: 14px;
        width: auto;
        margin-bottom: 0;
        display: inline-block; /* Allows padding and margin */
        transition: background 0.3s ease;
    }
    .edit-btn:hover {
        background: #0056b3;
    }
    .movie-list-container {
        max-width: 800px;
        margin-top: 40px;
        background: #181818;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 0 10px rgba(0,0,0,0.5);
    }
  </style>
</head>
<body>
  <h2>Add New Content</h2>
  <form method="post">
    <div class="form-group">
        <label for="title">Movie/Series Title:</label>
        <input type="text" name="title" id="title" placeholder="Movie or Series Title" required />
    </div>

    <div class="form-group">
        <label for="content_type">Content Type:</label>
        <select name="content_type" id="content_type" onchange="toggleEpisodeFields()">
            <option value="movie">Movie</option>
            <option value="series">TV Series / Web Series</option>
        </select>
    </div>

    <div class="form-group" id="movie_download_links_group"> {# Group for movie links #}
        <label>Download Links (only paste URL):</label>
        <div class="link-input-group">
            <p>480p Download Link [Approx. 590MB]:</p>
            <input type="url" name="link_480p" placeholder="Enter 480p download link" />
        </div>
        <div class="link-input-group">
            <p>720p Download Link [Approx. 1.4GB]:</p>
            <input type="url" name="link_720p" placeholder="Enter 720p download link" />
        </div>
        <div class="link-input-group">
            <p>1080p Download Link [Approx. 2.9GB]:</p>
            <input type="url" name="link_1080p" placeholder="Enter 1080p download link" />
        </div>
    </div>

    <div id="episode_fields" style="display: none;"> {# Initially hidden for series episodes #}
        <h3>Episodes</h3>
        <div id="episodes_container">
            {# Episodes will be dynamically added here by JavaScript #}
        </div>
        <button type="button" onclick="addEpisodeField()">Add New Episode</button>
    </div>


    <div class="form-group">
        <label for="quality">Quality Tag (e.g., HD, Hindi Dubbed):</label>
        <input type="text" name="quality" id="quality" placeholder="Quality tag" />
    </div>

    <div class="form-group">
        <label for="top_label">Poster Top Label (Optional, e.g., Special Offer, New):</label>
        <input type="text" name="top_label" id="top_label" placeholder="Custom label on poster top" />
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_trending" id="is_trending" value="true">
        <label for="is_trending" style="display: inline-block;">Is Trending?</label>
    </div>

    <div class="form-group">
        <input type="checkbox" name="is_coming_soon" id="is_coming_soon" value="true">
        <label for="is_coming_soon" style="display: inline-block;">Is Coming Soon?</label>
    </div>

    <div class="form-group">
        <label for="overview">Overview (Optional - used if TMDb info not found):</label>
        <textarea name="overview" id="overview" rows="5" placeholder="Enter movie/series overview or synopsis"></textarea>
    </div>

    <div class="form-group">
        <label for="poster_url">Poster URL (Optional - direct image link, used if TMDb info not found):</label>
        <input type="url" name="poster_url" id="poster_url" placeholder="e.g., https://example.com/poster.jpg" />
    </div>

    <div class="form-group">
        <label for="year">Release Year (Optional - used if TMDb info not found):</label>
        <input type="text" name="year" id="year" placeholder="e.g., 2023" />
    </div>

    <div class="form-group">
        <label for="original_language">Original Language (Optional - used if TMDb info not found):</label>
        <input type="text" name="original_language" id="original_language" placeholder="e.g., Bengali, English" />
    </div>

    <div class="form-group">
        <label for="genres">Genres (Optional - comma-separated, used if TMDb info not found):</label>
        <input type="text" name="genres" id="genres" placeholder="e.g., Action, Drama, Thriller" />
    </div>
    
    <button type="submit">Add Content</button>
  </form>

  <h2 style="margin-top: 40px;">Search Content</h2> {# New Search Section #}
  <form method="GET" action="{{ url_for('admin') }}">
    <div class="form-group">
      <label for="admin_search_query">Search by Title:</label>
      <input type="search" name="q" id="admin_search_query" placeholder="Search content by title..." value="{{ admin_query|default('') }}" />
    </div>
    <button type="submit">Search</button>
  </form>

  <hr>

  <h2>Manage Existing Content {% if admin_query %}for "{{ admin_query }}"{% endif %}</h2> {# Updated Heading #}
  <div class="movie-list-container">
    {% if movies %}
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Quality</th>
          <th>Trending</th>
          <th>Coming Soon</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for movie in movies %}
        <tr>
          <td>{{ movie.title }}</td>
          <td>{{ movie.type | title }}</td>
          <td>{% if movie.quality %}{{ movie.quality }}{% else %}N/A{% endif %}</td>
          <td>{% if movie.quality == 'TRENDING' %}Yes{% else %}No{% endif %}</td>
          <td>{% if movie.is_coming_soon %}Yes{% else %}No{% endif %}</td>
          <td class="action-buttons">
            <a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a>
            <button class="delete-btn" onclick="confirmDelete('{{ movie._id }}', '{{ movie.title }}')">Delete</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="text-align:center; color:#999;">No content found.</p>
    {% endif %}
  </div>

  <script>
    function confirmDelete(movieId, movieTitle) {
      if (confirm('Are you sure you want to delete "' + movieTitle + '"?')) {
        window.location.href = '/delete_movie/' + movieId;
      }
    }

    function toggleEpisodeFields() {
        var contentType = document.getElementById('content_type').value;
        var episodeFields = document.getElementById('episode_fields');
        var movieDownloadLinksGroup = document.getElementById('movie_download_links_group');
        
        if (contentType === 'series') {
            episodeFields.style.display = 'block';
            movieDownloadLinksGroup.style.display = 'none';
        } else {
            episodeFields.style.display = 'none';
            movieDownloadLinksGroup.style.display = 'block';
        }
    }

    function addEpisodeField(episode = {}) {
        const container = document.getElementById('episodes_container');
        const newEpisodeDiv = document.createElement('div');
        newEpisodeDiv.className = 'episode-item';
        newEpisodeDiv.style.cssText = 'border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;';
        
        const episodeNumber = episode.episode_number || (container.children.length + 1);
        const episodeTitle = episode.title || '';
        const episodeOverview = episode.overview || '';

        newEpisodeDiv.innerHTML = `
            <div class="form-group">
                <label>Episode Number:</label>
                <input type="number" name="episode_number[]" value="${episodeNumber}" required />
            </div>
            <div class="form-group">
                <label>Episode Title:</label>
                <input type="text" name="episode_title[]" value="${episodeTitle}" placeholder="e.g., The Beginning" required />
            </div>
            <div class="form-group">
                <label>Episode Overview (Optional):</label>
                <textarea name="episode_overview[]" rows="3" placeholder="Overview for this episode">${episodeOverview}</textarea>
            </div>
            <div class="link-input-group">
                <p>480p Link:</p>
                <input type="url" name="episode_link_480p[]" placeholder="Enter 480p download link" />
            </div>
            <div class="link-input-group">
                <p>720p Link:</p>
                <input type="url" name="episode_link_720p[]" placeholder="Enter 720p download link" />
            </div>
            <div class="link-input-group">
                <p>1080p Link:</p>
                <input type="url" name="episode_link_1080p[]" placeholder="Enter 1080p download link" />
            </div>
            <button type="button" onclick="this.closest('.episode-item').remove()" class="delete-btn">Remove Episode</button>
        `;
        container.appendChild(newEpisodeDiv);
    }

    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body>
</html>
"""

# --- YOUR ORIGINAL edit_html TEMPLATE ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieZone</title>
  <style>
    body { font-family: Arial, sans-serif; background: #121212; color: #eee; padding: 20px; }
    h2 { 
      background: linear-gradient(270deg, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
      background-size: 400% 400%; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      animation: gradientShift 10s ease infinite; display: inline-block; font-size: 28px; margin-bottom: 20px;
    }
    @keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    form { max-width: 600px; margin-bottom: 40px; border: 1px solid #333; padding: 20px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: bold; color: #ddd; }
    input[type="text"], input[type="url"], textarea, button, select, input[type="number"] { width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 5px; border: none; font-size: 16px; background: #222; color: #eee; }
    input[type="checkbox"] { width: auto; margin-right: 10px; }
    textarea { resize: vertical; min-height: 80px; }
    .link-input-group p { font-size: 14px; color: #bbb; margin-bottom: 5px; }
    button { background: #1db954; color: #000; font-weight: 700; cursor: pointer; transition: background 0.3s ease; }
    button:hover { background: #17a34a; }
    .back-to-admin { display: inline-block; margin-bottom: 20px; color: #1db954; text-decoration: none; font-weight: bold; }
    .delete-btn { background: #e44d26; color: #fff; padding: 5px 10px; border-radius: 5px; border: none; cursor: pointer; font-size: 14px; width: auto; margin-bottom: 0; }
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">← Back to Admin Panel</a>
  <h2>Edit Content: {{ movie.title }}</h2>
  <form method="post">
    <div class="form-group"><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option><option value="series" {% if movie.type == 'series' %}selected{% endif %}>Series</option></select></div>
    
    <div class="form-group" id="movie_download_links_group">
        <label>Download Links:</label>
        <div class="link-input-group"><p>480p:</p><input type="url" name="link_480p" value="{% for link in movie.links %}{% if link.quality == '480p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
        <div class="link-input-group"><p>720p:</p><input type="url" name="link_720p" value="{% for link in movie.links %}{% if link.quality == '720p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
        <div class="link-input-group"><p>1080p:</p><input type="url" name="link_1080p" value="{% for link in movie.links %}{% if link.quality == '1080p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
    </div>

    <div id="episode_fields" style="display: none;">
        <h3>Episodes</h3>
        <div id="episodes_container">
            {% if movie.type == 'series' and movie.episodes %}{% for episode in movie.episodes %}
            <div class="episode-item" style="border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;">
                <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" value="{{ episode.episode_number }}" required /></div>
                <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" value="{{ episode.title }}" required /></div>
                <div class="form-group"><label>Ep Overview:</label><textarea name="episode_overview[]" rows="3">{{ episode.overview }}</textarea></div>
                <div class="link-input-group"><p>480p Link:</p><input type="url" name="episode_link_480p[]" value="{% for link in episode.links %}{% if link.quality == '480p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
                <div class="link-input-group"><p>720p Link:</p><input type="url" name="episode_link_720p[]" value="{% for link in episode.links %}{% if link.quality == '720p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
                <div class="link-input-group"><p>1080p Link:</p><input type="url" name="episode_link_1080p[]" value="{% for link in episode.links %}{% if link.quality == '1080p' %}{{ link.url }}{% endif %}{% endfor %}" /></div>
                <button type="button" onclick="this.closest('.episode-item').remove()" class="delete-btn">Remove Episode</button>
            </div>
            {% endfor %}{% endif %}
        </div>
        <button type="button" onclick="addEpisodeField()">Add New Episode</button>
    </div>

    <div class="form-group"><label>Quality Tag:</label><input type="text" name="quality" value="{{ movie.quality or '' }}" /></div>
    <div class="form-group"><label>Poster Top Label:</label><input type="text" name="top_label" value="{{ movie.top_label or '' }}" /></div>
    <div class="form-group"><input type="checkbox" name="is_trending" value="true" {% if movie.quality == 'TRENDING' %}checked{% endif %}><label style="display:inline-block;">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}><label style="display:inline-block;">Is Coming Soon?</label></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview" rows="5">{{ movie.overview }}</textarea></div>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster }}" /></div>
    <div class="form-group"><label>Year:</label><input type="text" name="year" value="{{ movie.year }}" /></div>
    <div class="form-group"><label>Language:</label><input type="text" name="original_language" value="{{ movie.original_language }}" /></div>
    <div class="form-group"><label>Genres (comma-separated):</label><input type="text" name="genres" value="{{ movie.genres|join(', ') }}" /></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() {
        var contentType = document.getElementById('content_type').value;
        document.getElementById('episode_fields').style.display = contentType === 'series' ? 'block' : 'none';
        document.getElementById('movie_download_links_group').style.display = contentType === 'movie' ? 'block' : 'none';
    }
    function addEpisodeField() { /* Reuse admin addEpisodeField JS */
        const container = document.getElementById('episodes_container');
        const newEpisodeDiv = document.createElement('div');
        newEpisodeDiv.className = 'episode-item';
        newEpisodeDiv.style.cssText = 'border: 1px solid #444; padding: 10px; margin-bottom: 10px; border-radius: 5px;';
        newEpisodeDiv.innerHTML = `
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" value="${container.children.length + 1}" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div>
            <div class="form-group"><label>Ep Overview:</label><textarea name="episode_overview[]" rows="3"></textarea></div>
            <div class="link-input-group"><p>480p Link:</p><input type="url" name="episode_link_480p[]" /></div>
            <div class="link-input-group"><p>720p Link:</p><input type="url" name="episode_link_720p[]" /></div>
            <div class="link-input-group"><p>1080p Link:</p><input type="url" name="episode_link_1080p[]" /></div>
            <button type="button" onclick="this.closest('.episode-item').remove()" class="delete-btn">Remove</button>
        `;
        container.appendChild(newEpisodeDiv);
    }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body>
</html>
"""

# ==============================================================================
# END OF HTML TEMPLATES
# ==============================================================================


# ==============================================================================
# START OF FLASK ROUTES
# ==============================================================================

@app.route('/')
def home():
    query = request.args.get('q')

    # If there is a search query, render the full page list
    if query:
        search_results = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
        for m in search_results:
            m['_id'] = str(m['_id'])
        return render_template_string(
            index_html,
            is_full_page_list=True,
            movies=search_results,
            page_title=f'Search Results for "{query}"',
            query=query
        )

    # --- Fetch data for homepage sections ---
    # For slider: top 5 trending movies with a poster
    slider_movies_list = list(movies.find({"quality": "TRENDING", "poster": {"$exists": True, "$ne": ""}}).sort('_id', -1).limit(5))
    
    # Other sections with a limit
    trending_movies_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(12))
    recently_added_list = list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(12))
    latest_movies_list = list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(12))
    latest_series_list = list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(12))
    coming_soon_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(12))

    # Convert all ObjectIds to strings
    all_lists = [slider_movies_list, trending_movies_list, recently_added_list, latest_movies_list, latest_series_list, coming_soon_list]
    for movie_list in all_lists:
        for m in movie_list:
            m['_id'] = str(m['_id'])

    return render_template_string(
        index_html,
        is_full_page_list=False,
        slider_movies=slider_movies_list,
        trending_movies=trending_movies_list,
        recently_added=recently_added_list,
        latest_movies=latest_movies_list,
        latest_series=latest_series_list,
        coming_soon_movies=coming_soon_list,
        query=query
    )


def fetch_and_update_tmdb_data(movie_id, movie_doc):
    """Helper function to fetch data from TMDb and update the DB if needed."""
    if not TMDB_API_KEY:
        return movie_doc

    # Check if essential data is missing
    if movie_doc.get("poster") and movie_doc.get("overview") != "No overview available.":
        return movie_doc

    try:
        content_type = movie_doc.get("type", "movie")
        tmdb_search_type = "tv" if content_type == "series" else "movie"
        
        search_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={movie_doc['title']}"
        res = requests.get(search_url, timeout=5).json()
        if not res.get("results"):
            return movie_doc

        data = res["results"][0]
        update_fields = {}

        if not movie_doc.get("poster") and data.get("poster_path"):
            update_fields["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
        if movie_doc.get("overview") == "No overview available." and data.get("overview"):
            update_fields["overview"] = data.get("overview")
        if (not movie_doc.get("year") or movie_doc.get("year") == "N/A"):
            release_key = "first_air_date" if tmdb_search_type == "tv" else "release_date"
            if data.get(release_key):
                update_fields["year"] = data[release_key][:4]
                update_fields["release_date"] = data[release_key]
        if not movie_doc.get("genres") and data.get("genre_ids"):
            update_fields["genres"] = [TMDb_Genre_Map.get(gid) for gid in data["genre_ids"] if TMDb_Genre_Map.get(gid)]
        
        if data.get("vote_average"):
            update_fields["vote_average"] = data.get("vote_average")
        if data.get("original_language"):
            update_fields["original_language"] = data.get("original_language")

        if update_fields:
            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_fields})
            movie_doc.update(update_fields)
            print(f"Updated TMDb data for {movie_doc['title']}")

    except Exception as e:
        print(f"Could not fetch TMDb data for {movie_doc['title']}: {e}")
    
    return movie_doc


@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie = fetch_and_update_tmdb_data(movie_id, movie)
            movie['_id'] = str(movie['_id'])
            # Ensure vote_average is a float for formatting
            if 'vote_average' in movie and movie['vote_average'] is not None:
                try:
                    movie['vote_average'] = float(movie['vote_average'])
                except (ValueError, TypeError):
                    movie['vote_average'] = 0.0
            return render_template_string(detail_html, movie=movie)
        return "Movie not found", 404
    except Exception as e:
        print(f"Error in movie_detail for ID {movie_id}: {e}")
        return render_template_string(detail_html, movie=None)


@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        title = request.form.get("title")
        content_type = request.form.get("content_type", "movie")
        quality_tag = request.form.get("quality", "").upper()
        
        manual_overview = request.form.get("overview")
        manual_poster_url = request.form.get("poster_url")
        manual_year = request.form.get("year")
        manual_original_language = request.form.get("original_language")
        manual_genres_str = request.form.get("genres")
        manual_top_label = request.form.get("top_label")
        is_trending = request.form.get("is_trending") == "true"
        is_coming_soon = request.form.get("is_coming_soon") == "true"

        manual_genres_list = [g.strip() for g in manual_genres_str.split(',') if g.strip()] if manual_genres_str else []

        if is_trending:
            quality_tag = "TRENDING"

        movie_data = {
            "title": title, "quality": quality_tag, "type": content_type,
            "overview": manual_overview or "No overview available.",
            "poster": manual_poster_url or "",
            "year": manual_year or "N/A",
            "release_date": manual_year or "N/A", 
            "vote_average": None,
            "original_language": manual_original_language or "N/A",
            "genres": manual_genres_list,
            "top_label": manual_top_label or "",
            "is_coming_soon": is_coming_soon
        }

        # Handle links or episodes
        if content_type == "movie":
            links_list = []
            if request.form.get("link_480p"): links_list.append({"quality": "480p", "size": "590MB", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"): links_list.append({"quality": "720p", "size": "1.4GB", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"): links_list.append({"quality": "1080p", "size": "2.9GB", "url": request.form.get("link_1080p")})
            movie_data["links"] = links_list
        else: # series
            episodes_list = []
            episode_numbers = request.form.getlist('episode_number[]')
            episode_titles = request.form.getlist('episode_title[]')
            episode_overviews = request.form.getlist('episode_overview[]')
            episode_link_480ps = request.form.getlist('episode_link_480p[]')
            episode_link_720ps = request.form.getlist('episode_link_720p[]')
            episode_link_1080ps = request.form.getlist('episode_link_1080p[]')

            for i in range(len(episode_numbers)):
                episode_links = []
                if episode_link_480ps[i]: episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                if episode_link_720ps[i]: episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                if episode_link_1080ps[i]: episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                
                episodes_list.append({
                    "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                    "title": episode_titles[i], "overview": episode_overviews[i], "links": episode_links
                })
            movie_data["episodes"] = episodes_list

        try:
            result = movies.insert_one(movie_data)
            # Fetch TMDb data for the newly added movie
            fetch_and_update_tmdb_data(result.inserted_id, movie_data)
            print(f"Content '{movie_data['title']}' added successfully!")
        except Exception as e:
            print(f"Error inserting content into MongoDB: {e}")
        
        return redirect(url_for('admin'))

    # GET request logic
    admin_query = request.args.get('q')
    query_filter = {"title": {"$regex": admin_query, "$options": "i"}} if admin_query else {}
    all_content = list(movies.find(query_filter).sort('_id', -1))
    
    for content in all_content:
        content['_id'] = str(content['_id']) 
    return render_template_string(admin_html, movies=all_content, admin_query=admin_query)


@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Movie not found!", 404

        if request.method == "POST":
            is_trending = request.form.get("is_trending") == "true"
            quality_tag = "TRENDING" if is_trending else request.form.get("quality", "").upper()
            
            updated_data = {
                "title": request.form.get("title"),
                "quality": quality_tag,
                "type": request.form.get("content_type"),
                "overview": request.form.get("overview"),
                "poster": request.form.get("poster_url"),
                "year": request.form.get("year"),
                "release_date": request.form.get("year"),
                "original_language": request.form.get("original_language"),
                "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()],
                "top_label": request.form.get("top_label"),
                "is_coming_soon": request.form.get("is_coming_soon") == "true"
            }

            if updated_data["type"] == "movie":
                links_list = []
                if request.form.get("link_480p"): links_list.append({"quality": "480p", "size": "590MB", "url": request.form.get("link_480p")})
                if request.form.get("link_720p"): links_list.append({"quality": "720p", "size": "1.4GB", "url": request.form.get("link_720p")})
                if request.form.get("link_1080p"): links_list.append({"quality": "1080p", "size": "2.9GB", "url": request.form.get("link_1080p")})
                updated_data["links"] = links_list
                if "episodes" in movie: updated_data["episodes"] = [] # Clear episodes if switching to movie
            else: # series
                episodes_list = []
                # Same logic as admin to parse episode lists
                episode_numbers = request.form.getlist('episode_number[]')
                # ... (rest of the list gets)
                # Loop and build the episodes_list
                updated_data["episodes"] = episodes_list # Add your detailed parsing logic here
                if "links" in movie: updated_data["links"] = [] # Clear links if switching to series

            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_data})
            print(f"Content '{updated_data['title']}' updated successfully!")
            return redirect(url_for('admin'))

        # GET request
        movie['_id'] = str(movie['_id']) 
        return render_template_string(edit_html, movie=movie)

    except Exception as e:
        print(f"Error processing edit for movie ID {movie_id}: {e}")
        return "An error occurred during editing.", 500


@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    try:
        movies.delete_one({"_id": ObjectId(movie_id)})
        print(f"Content with ID {movie_id} deleted successfully!")
    except Exception as e:
        print(f"Error deleting content with ID {movie_id}: {e}")
    return redirect(url_for('admin'))


# --- Category Page Routes ---
def render_category_page(filter, title):
    movie_list = list(movies.find(filter).sort('_id', -1))
    for m in movie_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, is_full_page_list=True, movies=movie_list, page_title=title)

@app.route('/trending')
def trending_movies():
    return render_category_page({"quality": "TRENDING"}, "Trending on MovieZone")

@app.route('/movies')
def movies_only():
    return render_category_page({"type": "movie", "is_coming_soon": {"$ne": True}}, "All Movies")

@app.route('/series')
def webseries():
    return render_category_page({"type": "series", "is_coming_soon": {"$ne": True}}, "All Web Series")

@app.route('/coming-soon')
def coming_soon():
    return render_category_page({"is_coming_soon": True}, "Coming Soon")

@app.route('/recently-added')
def recently_added_all():
    return render_category_page({"is_coming_soon": {"$ne": True}}, "Recently Added")


# --- Main Execution ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000), debug=True)
