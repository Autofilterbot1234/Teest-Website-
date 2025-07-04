from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv
import re # রেগুলার এক্সপ্রেশন ব্যবহারের জন্য

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")
BOT_SECRET_KEY = os.getenv("BOT_SECRET_KEY") # বট ইন্টিগ্রেশনের জন্য নতুন কী

# --- অথেন্টিকেশন ফাংশন ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- ভেরিয়েবল ও কানেকশন চেক ---
if not all([MONGO_URI, TMDB_API_KEY, BOT_SECRET_KEY]):
    print("Error: MONGO_URI, TMDB_API_KEY, or BOT_SECRET_KEY environment variable not set. Exiting.")
    exit(1)

try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)

# TMDb Genre Map (Not used directly but good for reference)
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10402: "Music", 9648: "Mystery",
    10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller",
    10752: "War", 37: "Western", 10751: "Family", 14: "Fantasy", 36: "History"
}

# --- টেমপ্লেটগুলো এখানে থাকবে (আপনার প্রদত্ত কোডের মতোই) ---
# index_html, detail_html, admin_html, edit_html টেমপ্লেটগুলো এখানে পেস্ট করুন
# ... (পূর্ববর্তী কোডের বিশাল টেমপ্লেট স্ট্রিংগুলো এখানে থাকবে) ...
# --- START OF index_html TEMPLATE (Final Mobile-First Polish with all updates) ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>MovieZone - Your Entertainment Hub</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --text-light: #f5f5f5; --text-dark: #a0a0a0;
      --nav-height: 60px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto', sans-serif; background-color: var(--netflix-black);
    color: var(--text-light); overflow-x: hidden;
    padding-bottom: var(--nav-height); /* Space for bottom nav */
  }
  a { text-decoration: none; color: inherit; }
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: #222; }
  ::-webkit-scrollbar-thumb { background: #555; }
  ::-webkit-scrollbar-thumb:hover { background: var(--netflix-red); }

  .main-nav {
      position: fixed; top: 0; left: 0; width: 100%; padding: 15px 50px;
      display: flex; justify-content: space-between; align-items: center; z-index: 100;
      transition: background-color 0.3s ease;
      background: linear-gradient(to bottom, rgba(0,0,0,0.7) 10%, rgba(0,0,0,0));
  }
  .main-nav.scrolled { background-color: var(--netflix-black); }
  .logo {
      font-family: 'Bebas Neue', sans-serif; font-size: 32px; color: var(--netflix-red);
      font-weight: 700; letter-spacing: 1px;
  }
  .search-input {
      background-color: rgba(0,0,0,0.7); border: 1px solid #777;
      color: var(--text-light); padding: 8px 15px; border-radius: 4px;
      transition: width 0.3s ease, background-color 0.3s ease; width: 250px;
  }
  .search-input:focus { background-color: rgba(0,0,0,0.9); border-color: var(--text-light); outline: none; }

  .hero-section {
      height: 90vh; position: relative; display: flex; align-items: flex-end;
      padding: 50px; background-size: cover; background-position: center top; color: white;
  }
  .hero-section::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, var(--netflix-black) 10%, transparent 50%),
                  linear-gradient(to right, rgba(0,0,0,0.8) 0%, transparent 60%);
  }
  .hero-content { position: relative; z-index: 2; max-width: 50%; }
  .hero-title { font-family: 'Bebas Neue', sans-serif; font-size: 5rem; font-weight: 700; margin-bottom: 1rem; line-height: 1; }
  .hero-overview {
      font-size: 1.1rem; line-height: 1.5; margin-bottom: 1.5rem; max-width: 600px;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  .hero-buttons .btn {
      padding: 10px 25px; margin-right: 1rem; border: none; border-radius: 4px;
      font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity 0.3s ease, transform 0.15s ease;
  }
  .btn.btn-primary { background-color: var(--netflix-red); color: white; }
  .btn.btn-secondary { background-color: rgba(109, 109, 110, 0.7); color: white; }
  .btn:hover { opacity: 0.8; }
  .btn:active { transform: scale(0.97); opacity: 0.7; } /* NEW: Tap feedback for buttons */

  main { padding-top: 0; }
  .carousel-row { margin: 40px 0; position: relative; }
  .carousel-header {
      display: flex; justify-content: space-between; align-items: center;
      margin: 0 50px 15px 50px;
  }
  .carousel-title { font-family: 'Roboto', sans-serif; font-weight: 700; font-size: 1.6rem; margin: 0; }
  .see-all-link { color: var(--text-dark); font-weight: 700; font-size: 0.9rem; }
  .see-all-link:hover { color: var(--text-light); }
  .carousel-wrapper { position: relative; }
  .carousel-content {
      display: flex; gap: 10px; padding: 0 50px; overflow-x: scroll;
      scrollbar-width: none; -ms-overflow-style: none; scroll-behavior: smooth;
  }
  .carousel-content::-webkit-scrollbar { display: none; }

  .carousel-arrow {
      position: absolute; top: 0; height: 100%; transform: translateY(0);
      background-color: rgba(20, 20, 20, 0.5); border: none; color: white;
      font-size: 2.5rem; cursor: pointer; z-index: 10; width: 50px;
      display: flex; align-items: center; justify-content: center;
      opacity: 0; transition: opacity 0.3s ease;
  }
  .carousel-row:hover .carousel-arrow { opacity: 1; }
  .carousel-arrow.prev { left: 0; }
  .carousel-arrow.next { right: 0; }
  .carousel-arrow:hover { background-color: rgba(20, 20, 20, 0.8); }

  .movie-card {
      flex: 0 0 16.66%; min-width: 220px; border-radius: 4px; overflow: hidden;
      cursor: pointer; transition: transform 0.2s ease; position: relative; background-color: #222;
  }
  .movie-poster { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; }

  /* NEW: Skeleton Loader for posters for a better loading experience */
  .skeleton-poster {
      width: 100%; aspect-ratio: 2 / 3;
      background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%);
      background-size: 200% 100%;
      animation: skeleton-loading 1.5s infinite linear;
      display: block;
  }
  @keyframes skeleton-loading {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
  }

  @media (hover: hover) {
    .movie-card:hover { transform: scale(1.05); z-index: 5; }
  }
  /* NEW: Tap feedback for movie cards on touch devices */
  .movie-card:active {
      transform: scale(0.98);
      transition: transform 0.1s ease-in-out;
  }

  .full-page-grid-container { padding: 100px 50px 50px 50px; }
  .full-page-grid-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 30px; }
  .full-page-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;
  }
  .full-page-grid .movie-card { min-width: 0; }
  
  /* --- BOTTOM NAVIGATION BAR (IMPROVED) --- */
  .bottom-nav {
      display: none; position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-height); background-color: #181818;
      border-top: 1px solid #282828;
      justify-content: space-around; align-items: center;
      z-index: 200;
  }
  .nav-item {
      display: flex; flex-direction: column; align-items: center;
      color: var(--text-dark); font-size: 10px; flex-grow: 1;
      padding: 5px 0; transition: color 0.2s ease, font-weight 0.2s ease;
  }
  .nav-item i { font-size: 20px; margin-bottom: 4px; transition: transform 0.2s ease; }
  /* IMPROVEMENT: Made active state more prominent */
  .nav-item.active {
      color: var(--text-light);
      font-weight: 700;
  }
  .nav-item.active i {
      transform: scale(1.1);
  }
  .nav-item.active .fa-home { color: var(--netflix-red); }

  /* --- MOBILE ENHANCEMENTS --- */
  @media (max-width: 768px) {
      body { padding-bottom: var(--nav-height); }
      .main-nav { padding: 10px 15px; }
      .logo { font-size: 24px; }
      .search-input { width: 150px; padding: 6px 10px; font-size: 14px; }
      
      .hero-section { height: 60vh; padding: 15px; align-items: center; }
      .hero-content { max-width: 90%; text-align: center; }
      .hero-title { font-size: 2.8rem; }
      .hero-overview { display: none; }
      .hero-buttons .btn { padding: 8px 18px; font-size: 0.9rem; }
      
      .carousel-arrow { display: none; }
      .carousel-row { margin: 25px 0; }
      .carousel-header { margin: 0 15px 10px 15px; }
      .carousel-title { font-size: 1.2rem; }
      .carousel-content { padding: 0 15px; gap: 8px; }
      .movie-card { min-width: 130px; }
      
      .full-page-grid-container { padding: 80px 15px 30px; }
      .full-page-grid-title { font-size: 1.8rem; }
      .full-page-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; }
      
      .bottom-nav { display: flex; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
</head>
<body>
<header class="main-nav">
  <a href="{{ url_for('home') }}" class="logo">MovieZone</a>
  <form method="GET" action="/" class="search-form">
    <input type="search" name="q" class="search-input" placeholder="Search..." value="{{ query|default('') }}" />
  </form>
</header>

<main>
  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      {% if movies|length == 0 %}
        <p style="text-align:center; color: var(--text-dark); margin-top: 40px;">No content found.</p>
      {% else %}
        <div class="full-page-grid">
          {% for m in movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            {% if m.poster %}
              <img class="movie-poster" loading="lazy" src="{{ m.poster }}" alt="{{ m.title }}">
            {% else %}
              <span class="skeleton-poster"></span>
            {% endif %}
          </a>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  {% else %} {# Homepage with carousels #}
    {% if trending_movies %}
      <div class="hero-section" style="background-image: url('{{ trending_movies[0].poster or '' }}');">
        <div class="hero-content">
          <h1 class="hero-title">{{ trending_movies[0].title }}</h1>
          <p class="hero-overview">{{ trending_movies[0].overview }}</p>
          <div class="hero-buttons">
            <a href="{{ url_for('movie_detail', movie_id=trending_movies[0]._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>
            <a href="{{ url_for('movie_detail', movie_id=trending_movies[0]._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
          </div>
        </div>
      </div>
    {% endif %}

    {% macro render_carousel(title, movies_list, endpoint) %}
      {% if movies_list %}
      <div class="carousel-row">
        <div class="carousel-header">
          <h2 class="carousel-title">{{ title }}</h2>
          <a href="{{ url_for(endpoint) }}" class="see-all-link">See All ></a>
        </div>
        <div class="carousel-wrapper">
          <div class="carousel-content">
            {% for m in movies_list %}
            <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
              {% if m.poster %}
                <img class="movie-poster" loading="lazy" src="{{ m.poster }}" alt="{{ m.title }}">
              {% else %}
                <span class="skeleton-poster"></span>
              {% endif %}
            </a>
            {% endfor %}
          </div>
          <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
          <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
        </div>
      </div>
      {% endif %}
    {% endmacro %}
    
    {{ render_carousel('Trending Now', trending_movies, 'trending_movies') }}
    {{ render_carousel('Latest Movies', latest_movies, 'movies_only') }}
    {{ render_carousel('Web Series', latest_series, 'webseries') }}
    {{ render_carousel('Recently Added', recently_added, 'recently_added_all') }}
    {{ render_carousel('Coming Soon', coming_soon_movies, 'coming_soon') }}
  {% endif %}
</main>

<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' %}active{% endif %}">
      <i class="fas fa-home"></i><span>Home</span>
  </a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}">
      <i class="fas fa-film"></i><span>Movies</span>
  </a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}">
      <i class="fas fa-tv"></i><span>Series</span>
  </a>
  <a href="{{ url_for('coming_soon') }}" class="nav-item {% if request.endpoint == 'coming_soon' %}active{% endif %}">
      <i class="fas fa-clock"></i><span>Coming Soon</span>
  </a>
</nav>

<script>
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => { window.scrollY > 50 ? nav.classList.add('scrolled') : nav.classList.remove('scrolled'); });
    document.querySelectorAll('.carousel-arrow').forEach(button => {
        button.addEventListener('click', () => {
            const carousel = button.parentElement.querySelector('.carousel-content');
            const scroll = carousel.clientWidth * 0.8;
            carousel.scrollLeft += button.classList.contains('next') ? scroll : -scroll;
        });
    });
</script>
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# --- START OF detail_html TEMPLATE (Final Mobile-First Polish with updates) ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieZone</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --text-light: #f5f5f5; --text-dark: #a0a0a0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); }
  .detail-header {
      position: absolute; top: 0; left: 0; right: 0; padding: 20px 50px; z-index: 100;
  }
  .back-button {
      color: var(--text-light); font-size: 1.2rem; font-weight: 700; text-decoration: none;
      display: flex; align-items: center; gap: 10px; transition: color 0.3s ease;
  }
  .back-button:hover { color: var(--netflix-red); }

  .detail-hero {
      position: relative; width: 100%; min-height: 100vh; overflow: hidden;
      display: flex; align-items: center; justify-content: center; padding: 100px 0;
  }
  .detail-hero-background {
      position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background-size: cover; background-position: center;
      filter: blur(20px) brightness(0.4); transform: scale(1.1);
  }
  .detail-hero::after {
      content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, rgba(20,20,20,1) 0%, rgba(20,20,20,0.6) 50%, rgba(20,20,20,1) 100%);
  }
  .detail-content-wrapper {
      position: relative; z-index: 2; display: flex; gap: 40px;
      max-width: 1200px; padding: 0 50px; width: 100%;
  }
  .detail-poster {
      width: 300px; height: 450px; flex-shrink: 0; border-radius: 8px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5); object-fit: cover;
  }
  .detail-info { flex-grow: 1; max-width: 65%; }
  .detail-title {
      font-family: 'Bebas Neue', sans-serif; font-size: 4.5rem;
      font-weight: 700; line-height: 1.1; margin-bottom: 20px;
  }
  .detail-meta {
      display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 25px;
      font-size: 1rem; color: var(--text-dark);
  }
  .detail-meta span { font-weight: 700; color: var(--text-light); }
  .detail-overview { font-size: 1.1rem; line-height: 1.6; margin-bottom: 30px; }
  
  .download-section h3 {
      font-size: 1.5rem; font-weight: 700; margin-bottom: 20px;
      padding-bottom: 5px; border-bottom: 2px solid var(--netflix-red); display: inline-block;
  }
  .download-item, .episode-item { margin-bottom: 20px; }
  .download-button, .episode-download-button {
      display: inline-block; padding: 12px 25px; background-color: var(--netflix-red);
      color: white; text-decoration: none; border-radius: 4px; font-weight: 700;
      transition: background-color 0.3s ease, transform 0.15s ease; /* IMPROVEMENT: Added transform transition */
      margin-right: 10px; margin-bottom: 10px;
      text-align: center;
  }
  .download-button:hover, .episode-download-button:hover { background-color: #b00710; }
  /* NEW: Tap feedback for download buttons */
  .download-button:active, .episode-download-button:active {
      transform: scale(0.97);
  }
  .no-link-message { color: var(--text-dark); font-style: italic; }
  .episode-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .episode-overview-text { font-size: 0.9rem; color: var(--text-dark); margin-bottom: 10px; }

  @media (max-width: 992px) {
      .detail-content-wrapper { flex-direction: column; align-items: center; text-align: center; }
      .detail-info { max-width: 100%; }
      .detail-title { font-size: 3.5rem; }
      .detail-meta { justify-content: center; }
  }
  @media (max-width: 768px) {
      .detail-header { padding: 20px; }
      .back-button { font-size: 1rem; }
      .detail-hero { min-height: 0; height: auto; padding: 80px 20px 40px; }
      .detail-content-wrapper { padding: 0; gap: 30px; }
      .detail-poster { width: 60%; max-width: 220px; height: auto; }
      .detail-title { font-size: 2.2rem; }
      .detail-meta { font-size: 0.9rem; gap: 15px; }
      .detail-overview { font-size: 1rem; line-height: 1.5; }
      .download-section h3 { font-size: 1.3rem; }
      .episode-title { font-size: 1.1rem; }
      .download-button, .episode-download-button { display: block; width: 100%; max-width: 320px; margin: 0 auto 10px auto; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
</head>
<body>
<header class="detail-header">
  <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a>
</header>
{% if movie %}
<div class="detail-hero">
  <div class="detail-hero-background" style="background-image: url('{{ movie.poster }}');"></div>
  <div class="detail-content-wrapper">
    <img class="detail-poster" loading="lazy" src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}">
    <div class="detail-info">
      <h1 class="detail-title">{{ movie.title }}</h1>
      <div class="detail-meta">
        {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
        {% if movie.vote_average %}<span><i class="fas fa-star" style="color:#f5c518;"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
        {% if movie.genres %}<span>{{ movie.genres | join(' • ') }}</span>{% endif %}
      </div>
      <p class="detail-overview">{{ movie.overview }}</p>
      
      <div class="download-section">
        {% if movie.is_coming_soon %}<h3>Coming Soon</h3>
        {% elif movie.type == 'movie' %}
          <h3>Download Links</h3>
          {% if movie.links %}
            {% for link_item in movie.links %}
            <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">
              <i class="fas fa-download"></i> {{ link_item.quality }} {% if link_item.size %}[{{ link_item.size }}]{% endif %}
            </a>
            {% endfor %}
          {% else %}<p class="no-link-message">No links available.</p>{% endif %}
        {% elif movie.type == 'series' and movie.episodes %}
          <h3>Episodes</h3>
          {% for episode in movie.episodes | sort(attribute='episode_number') %}
          <div class="episode-item">
            <h4 class="episode-title">E{{ episode.episode_number }}: {{ episode.title }}</h4>
            {% if episode.overview %}<p class="episode-overview-text">{{ episode.overview }}</p>{% endif %}
            {% if episode.links %}
              {% for link_item in episode.links %}<a class="episode-download-button" href="{{ link_item.url }}" target="_blank" rel="noopener"><i class="fas fa-download"></i> {{ link_item.quality }}</a>{% endfor %}
            {% else %}<p class="no-link-message">No links for this episode.</p>{% endif %}
          </div>
          {% endfor %}
        {% else %}<p class="no-link-message">No download links available.</p>{% endif %}
      </div>
    </div>
  </div>
</div>
{% else %}
<div style="display:flex; justify-content:center; align-items:center; height:100vh;">
  <h2>Content not found.</h2>
</div>
{% endif %}
</body>
</html>
"""
# --- END OF detail_html TEMPLATE ---


# --- START OF admin_html TEMPLATE (Dark theme update with mobile viewport) ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5;
    }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2 { 
      font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red);
      font-size: 2.5rem; margin-bottom: 20px;
    }
    form { max-width: 800px; margin-bottom: 40px; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 8px; font-weight: bold; }
    input[type="text"], input[type="url"], textarea, select, input[type="number"], input[type="search"] {
      width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray);
      font-size: 1rem; background: var(--light-gray); color: var(--text-light);
    }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    button[type="submit"], .add-episode-btn {
      background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer;
      border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem;
      transition: background 0.3s ease, transform 0.15s ease;
    }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    button[type="submit"]:active, .add-episode-btn:active { transform: scale(0.97); } /* NEW: Tap feedback */
    table { display: block; overflow-x: auto; white-space: nowrap; width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--light-gray); }
    th { background: #252525; }
    td { background: var(--dark-gray); }
    .action-buttons { display: flex; gap: 10px; }
    .action-buttons a, .action-buttons button {
        padding: 6px 12px; border-radius: 4px; text-decoration: none;
        color: white; border: none; cursor: pointer; transition: opacity 0.3s ease, transform 0.15s ease;
    }
    .edit-btn { background: #007bff; }
    .delete-btn { background: #dc3545; }
    .action-buttons a:hover, .action-buttons button:hover { opacity: 0.8; }
    .action-buttons a:active, .action-buttons button:active { transform: scale(0.96); opacity: 0.8; } /* NEW: Tap feedback */
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <h2>Add New Content</h2>
  <form method="post">
    <div class="form-group"><label for="title">Title:</label><input type="text" name="title" id="title" required /></div>
    <div class="form-group"><label for="content_type">Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie">Movie</option><option value="series">TV/Web Series</option></select></div>
    <div id="movie_download_links_group">
      <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" /></div>
      <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" /></div>
      <div class="form-group"><label>1080p Link:</label><input type="url" name="link_1080p" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
      <h3>Episodes</h3><div id="episodes_container"></div>
      <button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button>
    </div>
    <hr style="border-color: #333; margin: 20px 0;">
    <div class="form-group"><label for="quality">Quality Tag (e.g., HD):</label><input type="text" name="quality" id="quality" /></div>
    <div class="form-group"><label for="top_label">Poster Top Label (Optional):</label><input type="text" name="top_label" id="top_label" /></div>
    <div class="form-group"><input type="checkbox" name="is_trending" id="is_trending" value="true"><label for="is_trending" style="display: inline-block;">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" id="is_coming_soon" value="true"><label for="is_coming_soon" style="display: inline-block;">Is Coming Soon?</label></div>
    <div class="form-group"><label for="overview">Overview (Optional):</label><textarea name="overview" id="overview"></textarea></div>
    <div class="form-group"><label for="poster_url">Poster URL (Optional):</label><input type="url" name="poster_url" id="poster_url" /></div>
    <div class="form-group"><label for="year">Year (Optional):</label><input type="text" name="year" id="year" /></div>
    <div class="form-group"><label for="original_language">Language (Optional):</label><input type="text" name="original_language" id="original_language" /></div>
    <div class="form-group"><label for="genres">Genres (Comma-separated, Optional):</label><input type="text" name="genres" id="genres" /></div>
    <button type="submit">Add Content</button>
  </form>

  <h2>Search Content</h2>
  <form method="GET" action="{{ url_for('admin') }}">
    <div class="form-group"><label for="admin_search_query">Search by Title:</label><input type="search" name="q" id="admin_search_query" value="{{ admin_query|default('') }}" /></div>
    <button type="submit">Search</button>
  </form>

  <h2>Manage Existing Content {% if admin_query %}for "{{ admin_query }}"{% endif %}</h2>
  <table><thead><tr><th>Title</th><th>Type</th><th>Quality</th><th>Trending</th><th>Coming Soon</th><th>Actions</th></tr></thead>
  <tbody>
    {% for movie in movies %}
    <tr>
      <td>{{ movie.title }}</td><td>{{ movie.type | title }}</td><td>{{ movie.quality or 'N/A' }}</td>
      <td>{% if movie.quality == 'TRENDING' %}Yes{% else %}No{% endif %}</td><td>{% if movie.is_coming_soon %}Yes{% else %}No{% endif %}</td>
      <td class="action-buttons">
        <a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a>
        <button class="delete-btn" onclick="confirmDelete('{{ movie._id }}', '{{ movie.title }}')">Delete</button>
      </td>
    </tr>
    {% endfor %}
  </tbody></table>
  {% if not movies %}<p>No content found.</p>{% endif %}

  <script>
    function confirmDelete(id, title) { if (confirm('Delete "' + title + '"?')) window.location.href = '/delete_movie/' + id; }
    function toggleEpisodeFields() {
        var isSeries = document.getElementById('content_type').value === 'series';
        document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none';
        document.getElementById('movie_download_links_group').style.display = isSeries ? 'none' : 'block';
    }
    function addEpisodeField() {
        const container = document.getElementById('episodes_container');
        const div = document.createElement('div');
        div.className = 'episode-item';
        div.innerHTML = `
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div>
            <div class="form-group"><label>Ep Overview:</label><textarea name="episode_overview[]"></textarea></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" /></div>
            <div class="form-group"><label>1080p Link:</label><input type="url" name="episode_link_1080p[]" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="delete-btn" style="background:#dc3545; padding: 6px 12px;">Remove Ep</button>
        `;
        container.appendChild(div);
    }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""
# --- END OF admin_html TEMPLATE ---


# --- START OF edit_html TEMPLATE (Dark theme update with mobile viewport) ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieZone</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --netflix-red: #E50914; --netflix-black: #141414;
      --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5;
    }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); font-size: 2.5rem; margin-bottom: 20px; }
    form { max-width: 800px; margin-bottom: 40px; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 8px; font-weight: bold; }
    input[type="text"], input[type="url"], textarea, select, input[type="number"] {
      width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray);
      font-size: 1rem; background: var(--light-gray); color: var(--text-light);
    }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    button[type="submit"], .add-episode-btn {
      background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer;
      border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem;
      transition: background 0.3s ease, transform 0.15s ease;
    }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    button[type="submit"]:active, .add-episode-btn:active { transform: scale(0.97); } /* NEW: Tap feedback */
    .back-to-admin { display: inline-block; margin-bottom: 20px; color: var(--netflix-red); text-decoration: none; font-weight: bold; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    .delete-btn { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; transition: transform 0.15s ease; }
    .delete-btn:active { transform: scale(0.96); } /* NEW: Tap feedback */
  </style>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <a href="{{ url_for('admin') }}" class="back-to-admin">← Back to Admin</a>
  <h2>Edit: {{ movie.title }}</h2>
  <form method="post">
    <div class="form-group"><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()">
        <option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option>
        <option value="series" {% if movie.type == 'series' %}selected{% endif %}>TV/Web Series</option>
    </select></div>
    <div id="movie_download_links_group">
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" value="{% for l in movie.links %}{% if l.quality == '480p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
        <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" value="{% for l in movie.links %}{% if l.quality == '720p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
        <div class="form-group"><label>1080p Link:</label><input type="url" name="link_1080p" value="{% for l in movie.links %}{% if l.quality == '1080p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
        <h3>Episodes</h3><div id="episodes_container">
        {% if movie.type == 'series' and movie.episodes %}{% for ep in movie.episodes %}
        <div class="episode-item">
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" value="{{ ep.episode_number }}" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" value="{{ ep.title }}" required /></div>
            <div class="form-group"><label>Ep Overview:</label><textarea name="episode_overview[]">{{ ep.overview }}</textarea></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" value="{% for l in ep.links %}{% if l.quality=='480p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" value="{% for l in ep.links %}{% if l.quality=='720p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <div class="form-group"><label>1080p Link:</label><input type="url" name="episode_link_1080p[]" value="{% for l in ep.links %}{% if l.quality=='1080p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>
        </div>
        {% endfor %}{% endif %}
        </div>
        <button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button>
    </div>
    <hr style="border-color: #333; margin: 20px 0;">
    <div class="form-group"><label>Quality Tag:</label><input type="text" name="quality" value="{{ movie.quality }}" /></div>
    <div class="form-group"><label>Poster Top Label:</label><input type="text" name="top_label" value="{{ movie.top_label }}" /></div>
    <div class="form-group"><input type="checkbox" name="is_trending" value="true" {% if movie.quality == 'TRENDING' %}checked{% endif %}><label style="display: inline-block;">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}><label style="display: inline-block;">Is Coming Soon?</label></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview">{{ movie.overview }}</textarea></div>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster }}" /></div>
    <div class="form-group"><label>Year:</label><input type="text" name="year" value="{{ movie.year }}" /></div>
    <div class="form-group"><label>Language:</label><input type="text" name="original_language" value="{{ movie.original_language }}" /></div>
    <div class="form-group"><label>Genres:</label><input type="text" name="genres" value="{{ movie.genres|join(', ') }}" /></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() {
        var isSeries = document.getElementById('content_type').value === 'series';
        document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none';
        document.getElementById('movie_download_links_group').style.display = isSeries ? 'none' : 'block';
    }
    function addEpisodeField() {
        const container = document.getElementById('episodes_container');
        const div = document.createElement('div');
        div.className = 'episode-item';
        div.innerHTML = `
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div>
            <div class="form-group"><label>Ep Overview:</label><textarea name="episode_overview[]"></textarea></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p[]" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p[]" /></div>
            <div class="form-group"><label>1080p Link:</label><input type="url" name="episode_link_1080p[]" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>
        `;
        container.appendChild(div);
    }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""
# --- END OF edit_html TEMPLATE ---


# --- পুরনো রুটগুলো (Home, Detail, Admin, etc.) ---
@app.route('/')
def home():
    query = request.args.get('q')
    movies_list, trending_movies_list, latest_movies_list, latest_series_list, coming_soon_movies_list, recently_added_list = [], [], [], [], [], []
    is_full_page_list = bool(query)

    if query:
        result = movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1)
        movies_list = list(result)
        query = f'Results for "{query}"'
    else:
        limit = 18
        trending_movies_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(limit))
        latest_movies_list = list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))
        latest_series_list = list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))
        coming_soon_movies_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))
        recently_added_list = list(movies.find().sort('_id', -1).limit(limit))

    all_content = movies_list + trending_movies_list + latest_movies_list + latest_series_list + coming_soon_movies_list + recently_added_list
    for m in all_content: m['_id'] = str(m['_id'])
    
    return render_template_string(index_html, movies=movies_list, query=query, trending_movies=trending_movies_list, latest_movies=latest_movies_list, latest_series=latest_series_list, coming_soon_movies=coming_soon_movies_list, recently_added=recently_added_list, is_full_page_list=is_full_page_list)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie['_id'] = str(movie['_id'])
            # এখানে TMDb ফেচিং লজিক দরকার নেই কারণ আমরা একবারই ফেচ করছি
        return render_template_string(detail_html, movie=movie)
    except Exception as e:
        print(f"Error fetching movie detail: {e}")
        return render_template_string(detail_html, movie=None)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        is_trending = request.form.get("is_trending") == "true"
        quality_tag = "TRENDING" if is_trending else request.form.get("quality", "").upper()
        
        movie_data = {
            "title": request.form.get("title"), "type": content_type, "quality": quality_tag,
            "top_label": request.form.get("top_label", ""), "is_trending": is_trending,
            "is_coming_soon": request.form.get("is_coming_soon") == "true",
            "overview": request.form.get("overview", "No overview available."),
            "poster": request.form.get("poster_url", ""), "year": request.form.get("year", "N/A"),
            "original_language": request.form.get("original_language", "N/A"),
            "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()],
            "tmdb_id": None,
        }

        # মুভি লিঙ্ক যোগ করা
        if content_type == 'movie':
            links = []
            if request.form.get("link_480p"):
                links.append({"quality": "480p", "size": "N/A", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"):
                links.append({"quality": "720p", "size": "N/A", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"):
                links.append({"quality": "1080p", "size": "N/A", "url": request.form.get("link_1080p")})
            movie_data["links"] = links
            movie_data["episodes"] = [] # মুভি হলে এপিসোড খালি থাকবে
        
        # সিরিজ এপিসোড যোগ করা
        elif content_type == 'series':
            episodes_data = []
            episode_numbers = request.form.getlist('episode_number[]')
            episode_titles = request.form.getlist('episode_title[]')
            episode_overviews = request.form.getlist('episode_overview[]')
            episode_link_480p = request.form.getlist('episode_link_480p[]')
            episode_link_720p = request.form.getlist('episode_link_720p[]')
            episode_link_1080p = request.form.getlist('episode_link_1080p[]')

            for i in range(len(episode_numbers)):
                ep_links = []
                if episode_link_480p[i]:
                    ep_links.append({"quality": "480p", "size": "N/A", "url": episode_link_480p[i]})
                if episode_link_720p[i]:
                    ep_links.append({"quality": "720p", "size": "N/A", "url": episode_link_720p[i]})
                if episode_link_1080p[i]:
                    ep_links.append({"quality": "1080p", "size": "N/A", "url": episode_link_1080p[i]})
                
                episodes_data.append({
                    "episode_number": int(episode_numbers[i]),
                    "title": episode_titles[i],
                    "overview": episode_overviews[i],
                    "links": ep_links
                })
            movie_data["episodes"] = episodes_data
            movie_data["links"] = [] # সিরিজ হলে মুভি লিঙ্ক খালি থাকবে

        movies.insert_one(movie_data)
        return redirect(url_for('admin'))

    admin_query = request.args.get('q')
    if admin_query:
        all_content = list(movies.find({"title": {"$regex": admin_query, "$options": "i"}}).sort('_id', -1))
    else:
        all_content = list(movies.find().sort('_id', -1))
    
    for content in all_content: content['_id'] = str(content['_id'])
    return render_template_string(admin_html, movies=all_content, admin_query=admin_query)

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404

    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        is_trending = request.form.get("is_trending") == "true"
        quality_tag = "TRENDING" if is_trending else request.form.get("quality", "").upper()

        updated_data = {
            "title": request.form.get("title"), "type": content_type, "quality": quality_tag,
            "top_label": request.form.get("top_label", ""), "is_trending": is_trending,
            "is_coming_soon": request.form.get("is_coming_soon") == "true",
            "overview": request.form.get("overview", "No overview available."),
            "poster": request.form.get("poster_url", ""), "year": request.form.get("year", "N/A"),
            "original_language": request.form.get("original_language", "N/A"),
            "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()],
        }

        if content_type == 'movie':
            links = []
            if request.form.get("link_480p"):
                links.append({"quality": "480p", "size": "N/A", "url": request.form.get("link_480p")})
            if request.form.get("link_720p"):
                links.append({"quality": "720p", "size": "N/A", "url": request.form.get("link_720p")})
            if request.form.get("link_1080p"):
                links.append({"quality": "1080p", "size": "N/A", "url": request.form.get("link_1080p")})
            updated_data["links"] = links
            updated_data["episodes"] = [] # মুভি হলে এপিসোড খালি থাকবে
        elif content_type == 'series':
            episodes_data = []
            episode_numbers = request.form.getlist('episode_number[]')
            episode_titles = request.form.getlist('episode_title[]')
            episode_overviews = request.form.getlist('episode_overview[]')
            episode_link_480p = request.form.getlist('episode_link_480p[]')
            episode_link_720p = request.form.getlist('episode_link_720p[]')
            episode_link_1080p = request.form.getlist('episode_link_1080p[]')

            for i in range(len(episode_numbers)):
                ep_links = []
                if episode_link_480p[i]:
                    ep_links.append({"quality": "480p", "size": "N/A", "url": episode_link_480p[i]})
                if episode_link_720p[i]:
                    ep_links.append({"quality": "720p", "size": "N/A", "url": episode_link_720p[i]})
                if episode_link_1080p[i]:
                    ep_links.append({"quality": "1080p", "size": "N/A", "url": episode_link_1080p[i]})
                
                episodes_data.append({
                    "episode_number": int(episode_numbers[i]),
                    "title": episode_titles[i],
                    "overview": episode_overviews[i],
                    "links": ep_links
                })
            updated_data["episodes"] = episodes_data
            updated_data["links"] = [] # সিরিজ হলে মুভি লিঙ্ক খালি থাকবে

        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_data})
        return redirect(url_for('admin'))
    
    # ObjectId কে স্ট্রিং এ রূপান্তর করে টেমপ্লেটে পাঠানো
    movie_obj['_id'] = str(movie_obj['_id'])
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    try:
        movies.delete_one({"_id": ObjectId(movie_id)})
        print(f"Deleted movie with ID: {movie_id}")
    except Exception as e:
        print(f"DB delete error: {e}")
    return redirect(url_for('admin'))

# --- Category/Full List Pages ---
def render_full_list(content_list, title):
    for m in content_list: m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=content_list, query=title, is_full_page_list=True)
    
@app.route('/trending_movies')
def trending_movies():
    trending_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1))
    return render_full_list(trending_list, "Trending Now")

@app.route('/movies_only')
def movies_only():
    movie_list = list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    return render_full_list(movie_list, "All Movies")

@app.route('/webseries')
def webseries():
    series_list = list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    return render_full_list(series_list, "All Web Series")

@app.route('/coming_soon')
def coming_soon():
    coming_soon_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1))
    return render_full_list(coming_soon_list, "Coming Soon")

@app.route('/recently_added')
def recently_added_all():
    all_recent_content = list(movies.find().sort('_id', -1))
    return render_full_list(all_recent_content, "Recently Added")

# ===================================================================
# === নতুন API এন্ডপয়েন্ট: টেলিগ্রাম বট থেকে কন্টেন্ট যোগ করার জন্য ===
# ===================================================================
@app.route('/api/add_from_bot', methods=['POST'])
def add_from_bot():
    # --- ধাপ ১: নিরাপত্তা যাচাই ---
    bot_key_header = request.headers.get('X-Bot-Secret-Key')
    if not bot_key_header or bot_key_header != BOT_SECRET_KEY:
        print(f"Unauthorized attempt to access bot API. Key used: {bot_key_header}")
        return {"status": "error", "message": "Unauthorized"}, 401

    # --- ধাপ ২: বট থেকে পাঠানো JSON ডেটা গ্রহণ ---
    data = request.get_json()
    # বট থেকে শুধুমাত্র 'link' প্যারামিটারটি অত্যাবশ্যক
    if not data or 'link' not in data:
        return {"status": "error", "message": "Missing 'link' in request"}, 400

    download_link = data.get('link')
    
    # টাইটেল, কোয়ালিটি এবং সাইজ লিঙ্ক থেকে অনুমান করার চেষ্টা করা হবে
    title = data.get('title') # যদি বট থেকে টাইটেল আসে, সেটা ব্যবহার করবে
    if not title: # যদি টাইটেল না আসে, লিঙ্ক থেকে অনুমান করবে
        title = extract_title_from_link(download_link)
        if not title:
            # যদি লিঙ্ক থেকেও টাইটেল বের করা না যায়, একটা ডিফল্ট বা এরর হ্যান্ডেলিং
            print(f"Could not extract title from link: {download_link}")
            return {"status": "error", "message": "Could not determine content title from link."}, 400

    quality = data.get('quality') # যদি বট থেকে কোয়ালিটি আসে, সেটা ব্যবহার করবে
    if not quality: # যদি না আসে, লিঙ্ক থেকে অনুমান করবে
        quality = extract_quality_from_link(download_link)
        if not quality:
            quality = 'HD' # অনুমান করা না গেলে ডিফল্ট

    size = data.get('size') # যদি বট থেকে সাইজ আসে, সেটা ব্যবহার করবে
    if not size: # যদি না আসে, লিঙ্ক থেকে অনুমান করবে
        size = extract_size_from_link(download_link)
        if not size:
            size = 'N/A' # অনুমান করা না গেলে ডিফল্ট

    # টাইপও লিঙ্ক থেকে অনুমান করা যেতে পারে, অথবা TMDb থেকে আসবে
    initial_content_type = data.get('type', 'movie') # বট থেকে না পেলে ডিফল্ট 'movie'

    print(f"Received from bot (after processing): Title='{title}', Quality='{quality}', Size='{size}', Link='{download_link}'")

    # --- ধাপ ৩: TMDb থেকে স্বয়ংক্রিয়ভাবে তথ্য সংগ্রহ (টাইটেল ব্যবহার করে) ---
    overview, poster, year, genres, release_date, tmdb_id, actual_content_type = \
        "No overview available.", "", "N/A", [], "", None, initial_content_type

    try:
        # TMDb সার্চের জন্য URL তৈরি করা। movie এবং tv (series) উভয়ই সার্চ করা।
        # এটি টাইটেল দিয়ে সঠিক কন্টেন্ট টাইপ খুঁজে বের করতে সাহায্য করবে।
        search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={requests.utils.quote(title)}"
        search_res = requests.get(search_url, timeout=10).json()
        
        if search_res and search_res.get("results"):
            tmdb_result = None
            for res_item in search_res["results"]:
                if res_item.get("media_type") in ["movie", "tv"]:
                    tmdb_result = res_item
                    break
            
            if tmdb_result:
                tmdb_id = tmdb_result.get("id")
                actual_content_type = "movie" if tmdb_result.get("media_type") == "movie" else "series"

                detail_url = f"https://api.themoviedb.org/3/{tmdb_result.get('media_type')}/{tmdb_id}?api_key={TMDB_API_KEY}"
                res = requests.get(detail_url, timeout=10).json()
                
                overview = res.get("overview", overview)
                if res.get("poster_path"):
                    poster = f"https://image.tmdb.org/t/p/w400{res['poster_path']}"
                elif res.get("backdrop_path"):
                    poster = f"https://image.tmdb.org/t/p/w400{res['backdrop_path']}"
                
                release_date = res.get("release_date") or res.get("first_air_date")
                if release_date:
                    year = release_date[:4]
                
                if res.get("genres"):
                    genres = [g['name'] for g in res['genres']]
                
                original_language = res.get("original_language", "N/A")

                print(f"Successfully fetched details for '{title}' from TMDb (Type: {actual_content_type}).")
            else:
                print(f"No relevant movie/series found on TMDb for '{title}'.")

    except requests.exceptions.Timeout:
        print(f"TMDb API request timed out for '{title}'.")
    except requests.exceptions.RequestException as e:
        print(f"Error making TMDb API request for '{title}': {e}")
    except Exception as e:
        print(f"General error fetching data from TMDb for '{title}': {e}")

    # --- ধাপ ৪: ডাটাবেসে সেভ করার জন্য ডেটা প্রস্তুত করা ---
    query_filter = {"title": title, "type": actual_content_type}
    if tmdb_id:
        query_filter["tmdb_id"] = tmdb_id

    existing_content = movies.find_one(query_filter)

    if existing_content:
        print(f"Updating existing content: '{title}' (ID: {existing_content['_id']})")
        
        link_exists = False
        existing_links = existing_content.get("links", [])
        for link_item in existing_links:
            if link_item.get("quality") == quality and link_item.get("url") == download_link:
                link_exists = True
                break
        
        if not link_exists:
            new_link_entry = {"quality": quality, "size": size, "url": download_link}
            
            if "links" not in existing_content:
                existing_content["links"] = []
            
            existing_content["links"].append(new_link_entry)
            
            movies.update_one(
                {"_id": existing_content["_id"]},
                {"$set": {
                    "links": existing_content["links"],
                    "overview": overview,
                    "poster": poster,
                    "year": year,
                    "release_date": release_date,
                    "genres": genres,
                    "original_language": original_language,
                    "tmdb_id": tmdb_id
                }}
            )
            print(f"Added new link ({quality}) to existing content '{title}'.")
            return {"status": "success", "message": f"Added new link ({quality}) to existing content '{title}'."}, 200
        else:
            print(f"Link with quality '{quality}' and URL '{download_link}' already exists for '{title}'. Skipping.")
            return {"status": "info", "message": f"Link with quality '{quality}' already exists for '{title}'. Skipping."}, 200
    else:
        print(f"Adding new content: '{title}' (Type: {actual_content_type})")
        new_content = {
            "title": title,
            "type": actual_content_type,
            "quality": quality,
            "top_label": "", 
            "is_trending": False,
            "is_coming_soon": False,
            "overview": overview,
            "poster": poster,
            "year": year,
            "release_date": release_date,
            "genres": genres,
            "original_language": original_language,
            "links": [{"quality": quality, "size": size, "url": download_link}],
            "episodes": [],
            "tmdb_id": tmdb_id
        }
        
        try:
            movies.insert_one(new_content)
            print(f"SUCCESS: Automatically added '{title}' to the database via bot.")
            return {"status": "success", "message": f"'{title}' added successfully."}, 201
        except Exception as e:
            print(f"DATABASE ERROR: Failed to insert '{title}'. Error: {e}")
            return {"status": "error", "message": "Failed to save to database."}, 500

# --- নতুন ইউটিলিটি ফাংশন: লিঙ্ক থেকে টাইটেল, কোয়ালিটি, সাইজ অনুমান করার জন্য ---
def extract_title_from_link(link):
    # এই ফাংশনটি আরও উন্নত হতে পারে ফাইল নামের প্যাটার্নের উপর ভিত্তি করে
    # উদাহরণ: https://example.com/movies/The.Movie.Title.2023.720p.mp4
    # এই ক্ষেত্রে 'The.Movie.Title.2023.720p.mp4' থেকে 'The Movie Title' বের করবে
    try:
        # URL থেকে ফাইলের নাম বের করা
        filename = link.split('/')[-1]
        # এক্সটেনশন এবং সম্ভাব্য অন্যান্য মেটাডেটা অপসারণ
        # যেমন: .mp4, .mkv, .avi, .720p, .1080p, .x264, .webdl ইত্যাদি
        cleaned_filename = re.sub(r'\.(mp4|mkv|avi|webm|m3u8)$', '', filename, flags=re.IGNORECASE)
        cleaned_filename = re.sub(r'\.\d{3,4}p|\.x\d{3}|\.web-?dl|\.bluray|\.hdrip|\.brrip|\.dvdrip|\.dubbed|\.hindi|\.english|\.dual\.audio', '', cleaned_filename, flags=re.IGNORECASE)
        cleaned_filename = re.sub(r'\.\d{4}', '', cleaned_filename) # বছর অপসারণ
        cleaned_filename = cleaned_filename.replace('.', ' ').strip() # ডট স্পেস দিয়ে প্রতিস্থাপন
        
        # কিছু সাধারণ কীওয়ার্ড যা টাইটেলে থাকা উচিত নয়
        keywords_to_remove = ["movies", "series", "full", "movie", "official"]
        for kw in keywords_to_remove:
            cleaned_filename = re.sub(r'\b' + re.escape(kw) + r'\b', '', cleaned_filename, flags=re.IGNORECASE).strip()

        # অতিরিক্ত স্পেস অপসারণ
        cleaned_filename = re.sub(r'\s+', ' ', cleaned_filename).strip()

        return cleaned_filename if cleaned_filename else None
    except Exception as e:
        print(f"Error extracting title from link {link}: {e}")
        return None

def extract_quality_from_link(link):
    qualities = re.findall(r'(\d{3,4}p|HD|FHD|UHD|HDR)', link, re.IGNORECASE)
    if qualities:
        # যদি একাধিক কোয়ালিটি পাওয়া যায়, সবচেয়ে বড়টা বা প্রথমটা নেওয়া
        # যেমন: 1080p, 720p -> 1080p
        sorted_qualities = sorted(qualities, key=lambda x: int(re.sub(r'\D', '', x)) if re.sub(r'\D', '', x).isdigit() else 0, reverse=True)
        if sorted_qualities:
            return sorted_qualities[0].upper()
    return "HD" # কিছু পাওয়া না গেলে ডিফল্ট

def extract_size_from_link(link):
    sizes = re.findall(r'(\d+\.?\d*(?:GB|MB))', link, re.IGNORECASE)
    if sizes:
        # একাধিক সাইজ থাকলে প্রথমটি নেওয়া
        return sizes[0].upper()
    return "N/A" # কিছু পাওয়া না গেলে ডিফল্ট


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
