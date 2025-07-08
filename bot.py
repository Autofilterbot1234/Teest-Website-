from flask import Flask, render_template_string, request, redirect, url_for, Response, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন
load_dotenv()

app = Flask(__name__)

# Environment variables
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

# --- অ্যাডমিন অথেন্টিকেশন ফাংশন ---
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
# --- অথেন্টিকেশন শেষ ---

# Check if environment variables are set
if not MONGO_URI:
    print("Error: MONGO_URI environment variable must be set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY is not set. Movie details will not be auto-fetched.")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    settings = db["settings"]
    feedback = db["feedback"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)


# === Context Processor: সমস্ত টেমপ্লেটে বিজ্ঞাপনের কোড সহজলভ্য করার জন্য ===
@app.context_processor
def inject_ads():
    ad_codes = settings.find_one()
    return dict(ad_settings=(ad_codes or {}))


# --- START OF index_html TEMPLATE ---
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
      background: linear-gradient(to bottom, rgba(0,0,0,0.8) 10%, rgba(0,0,0,0));
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

  .tags-section {
    padding: 80px 50px 20px 50px;
    background-color: var(--netflix-black);
  }
  .tags-container {
    display: flex; flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }
  .tag-link {
    padding: 6px 16px;
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid #444; border-radius: 50px;
    font-weight: 500; font-size: 0.85rem;
    transition: background-color 0.3s, border-color 0.3s, color 0.3s;
  }
  .tag-link:hover { background-color: var(--netflix-red); border-color: var(--netflix-red); color: white; }

  .hero-section { height: 85vh; position: relative; color: white; overflow: hidden; }
  .hero-slide {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background-size: cover; background-position: center top;
      display: flex; align-items: flex-end; padding: 50px;
      opacity: 0; transition: opacity 1.5s ease-in-out; z-index: 1;
  }
  .hero-slide.active { opacity: 1; z-index: 2; }
  .hero-slide::before {
      content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, var(--netflix-black) 10%, transparent 50%),
                  linear-gradient(to right, rgba(0,0,0,0.8) 0%, transparent 60%);
  }
  .hero-content { position: relative; z-index: 3; max-width: 50%; }
  .hero-title { font-family: 'Bebas Neue', sans-serif; font-size: 5rem; font-weight: 700; margin-bottom: 1rem; line-height: 1; }
  .hero-overview {
      font-size: 1.1rem; line-height: 1.5; margin-bottom: 1.5rem; max-width: 600px;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  .hero-buttons .btn {
      padding: 8px 20px;
      margin-right: 0.8rem;
      border: none; border-radius: 4px;
      font-size: 0.9rem;
      font-weight: 700; cursor: pointer; transition: opacity 0.3s ease;
      display: inline-flex; align-items: center; gap: 8px;
  }
  .btn.btn-primary { background-color: var(--netflix-red); color: white; }
  .btn.btn-secondary { background-color: rgba(109, 109, 110, 0.7); color: white; }
  .btn:hover { opacity: 0.8; }

  main { padding-top: 0; }
  .carousel-row { margin: 40px 0; position: relative; }
  .carousel-header {
      display: flex; justify-content: space-between; align-items: center;
      margin: 0 50px 15px 50px;
  }
  .carousel-title { font-family: 'Roboto', sans-serif; font-weight: 700; font-size: 1.6rem; margin: 0; }
  .see-all-link { color: var(--text-dark); font-weight: 700; font-size: 0.9rem; }
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

  .movie-card {
      flex: 0 0 16.66%; min-width: 220px; border-radius: 4px; overflow: hidden;
      cursor: pointer; transition: transform 0.3s ease, box-shadow 0.3s ease;
      position: relative; background-color: #222; display: block;
  }
  .movie-poster { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; }
  .poster-badge {
    position: absolute; top: 10px; left: 10px; background-color: var(--netflix-red);
    color: white; padding: 5px 10px; font-size: 12px; font-weight: 700;
    border-radius: 4px; z-index: 3; box-shadow: 0 2px 5px rgba(0,0,0,0.5);
  }
  .card-info-overlay {
      position: absolute; bottom: 0; left: 0; right: 0; padding: 20px 10px 10px 10px;
      background: linear-gradient(to top, rgba(0,0,0,0.95) 20%, transparent 100%);
      color: white; text-align: center; opacity: 0;
      transform: translateY(20px); transition: opacity 0.3s ease, transform 0.3s ease; z-index: 2;
  }
  .card-info-title { font-size: 1rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  @keyframes rgb-glow {
    0% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; }
    33% { box-shadow: 0 0 12px #4158D0, 0 0 4px #4158D0; }
    66% { box-shadow: 0 0 12px #C850C0, 0 0 4px #C850C0; }
    100% { box-shadow: 0 0 12px #e50914, 0 0 4px #e50914; }
  }
  @media (hover: hover) {
    .movie-card:hover { 
        transform: scale(1.05); z-index: 5;
        animation: rgb-glow 2.5s infinite linear;
    }
    .movie-card:hover .card-info-overlay { opacity: 1; transform: translateY(0); }
  }

  .full-page-grid-container { padding: 100px 50px 50px 50px; }
  .full-page-grid-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 30px; }
  .full-page-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;
  }
  .full-page-grid .movie-card { min-width: 0; }
  
  .bottom-nav {
      display: none; position: fixed; bottom: 0; left: 0; right: 0;
      height: var(--nav-height); background-color: #181818;
      border-top: 1px solid #282828; justify-content: space-around;
      align-items: center; z-index: 200;
  }
  .nav-item {
      display: flex; flex-direction: column; align-items: center;
      color: var(--text-dark); font-size: 10px; flex-grow: 1;
      padding: 5px 0; transition: color 0.2s ease;
  }
  .nav-item i { font-size: 20px; margin-bottom: 4px; }
  .nav-item.active { color: var(--text-light); }
  .nav-item.active .fa-home, .nav-item.active .fa-envelope, .nav-item.active .fa-layer-group { color: var(--netflix-red); }
  .ad-container { margin: 40px 50px; display: flex; justify-content: center; align-items: center; }

  .telegram-join-section {
    background-color: #181818; padding: 40px 20px;
    margin-top: 50px; text-align: center;
  }
  .telegram-join-section .telegram-icon {
    font-size: 4rem; color: #2AABEE; margin-bottom: 15px;
  }
  .telegram-join-section h2 {
    font-family: 'Bebas Neue', sans-serif; font-size: 2.5rem;
    color: var(--text-light); margin-bottom: 10px;
  }
  .telegram-join-section p {
    font-size: 1.1rem; color: var(--text-dark); max-width: 600px;
    margin: 0 auto 25px auto;
  }
  .telegram-join-button {
    display: inline-flex; align-items: center; gap: 10px;
    background-color: #2AABEE; color: white;
    padding: 12px 30px; border-radius: 50px;
    font-size: 1.1rem; font-weight: 700;
    transition: transform 0.2s ease, background-color 0.2s ease;
  }
  .telegram-join-button:hover { transform: scale(1.05); background-color: #1e96d1; }
  .telegram-join-button i { font-size: 1.3rem; }

  @media (max-width: 768px) {
      body { padding-bottom: var(--nav-height); }
      .main-nav { padding: 10px 15px; }
      .logo { font-size: 24px; }
      .search-input { width: 150px; }
      .tags-section { padding: 80px 15px 15px 15px; }
      .tag-link { padding: 6px 15px; font-size: 0.8rem; }
      .hero-section { height: 60vh; }
      .hero-slide { padding: 15px; align-items: center; }
      .hero-content { max-width: 90%; text-align: center; }
      .hero-title { font-size: 2.8rem; }
      .hero-overview { display: none; }
      .carousel-row { margin: 25px 0; }
      .carousel-header { margin: 0 15px 10px 15px; }
      .carousel-title { font-size: 1.2rem; }
      .carousel-content { padding: 0 15px; gap: 8px; }
      .movie-card { min-width: 130px; }
      .full-page-grid-container { padding: 80px 15px 30px; }
      .full-page-grid-title { font-size: 1.8rem; }
      .full-page-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; }
      .bottom-nav { display: flex; }
      .ad-container { margin: 25px 15px; }
      .telegram-join-section h2 { font-size: 2rem; }
      .telegram-join-section p { font-size: 1rem; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
<header class="main-nav">
  <a href="{{ url_for('home') }}" class="logo">MovieZone</a>
  <form method="GET" action="/" class="search-form">
    <input type="search" name="q" class="search-input" placeholder="Search..." value="{{ query|default('') }}" />
  </form>
</header>

<main>
  {% macro render_movie_card(m) %}
    <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
      {% if m.poster_badge %}<div class="poster-badge">{{ m.poster_badge }}</div>{% endif %}
      <img class="movie-poster" loading="lazy" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
      <div class="card-info-overlay"><h4 class="card-info-title">{{ m.title }}</h4></div>
    </a>
  {% endmacro %}

  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      {% if movies|length == 0 %}<p style="text-align:center; color: var(--text-dark); margin-top: 40px;">No content found.</p>
      {% else %}<div class="full-page-grid">{% for m in movies %}{{ render_movie_card(m) }}{% endfor %}</div>{% endif %}
    </div>
  {% else %}
    {% if all_badges %}
    <div class="tags-section">
        <div class="tags-container">
            {% for badge in all_badges %}<a href="{{ url_for('movies_by_badge', badge_name=badge) }}" class="tag-link">{{ badge }}</a>{% endfor %}
        </div>
    </div>
    {% endif %}
    {% if recently_added %}
      <div class="hero-section">
        {% for movie in recently_added %}
          <div class="hero-slide {% if loop.first %}active{% endif %}" style="background-image: url('{{ movie.poster or '' }}');">
            <div class="hero-content">
              <h1 class="hero-title">{{ movie.title }}</h1>
              <p class="hero-overview">{{ movie.overview }}</p>
              <div class="hero-buttons">
                 {% if movie.watch_link and not movie.is_coming_soon %}
                    <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>
                 {% endif %}
                <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
              </div>
            </div>
          </div>
        {% endfor %}
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
          <div class="carousel-content">{% for m in movies_list %}{{ render_movie_card(m) }}{% endfor %}</div>
          <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
          <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
        </div>
      </div>
      {% endif %}
    {% endmacro %}
    
    {{ render_carousel('Trending Now', trending_movies, 'trending_movies') }}
    {% if ad_settings.banner_ad_code %}<div class="ad-container">{{ ad_settings.banner_ad_code|safe }}</div>{% endif %}
    {{ render_carousel('Latest Movies', latest_movies, 'movies_only') }}
    {% if ad_settings.native_banner_code %}<div class="ad-container">{{ ad_settings.native_banner_code|safe }}</div>{% endif %}
    {{ render_carousel('Web Series', latest_series, 'webseries') }}
    {{ render_carousel('Recently Added', recently_added_full, 'recently_added_all') }}
    {{ render_carousel('Coming Soon', coming_soon_movies, 'coming_soon') }}
    
    <div class="telegram-join-section">
        <i class="fa-brands fa-telegram telegram-icon"></i>
        <h2>Join Our Telegram Channel</h2>
        <p>Get the latest movie updates, news, and direct download links right on your phone!</p>
        <a href="https://t.me/+60goZWp-FpkxNzVl" target="_blank" class="telegram-join-button">
            <i class="fa-brands fa-telegram"></i> Join Main Channel
        </a>
    </div>
  {% endif %}
</main>

<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item {% if request.endpoint == 'home' %}active{% endif %}"><i class="fas fa-home"></i><span>Home</span></a>
  <a href="{{ url_for('genres_page') }}" class="nav-item {% if request.endpoint == 'genres_page' %}active{% endif %}"><i class="fas fa-layer-group"></i><span>Genres</span></a>
  <a href="{{ url_for('movies_only') }}" class="nav-item {% if request.endpoint == 'movies_only' %}active{% endif %}"><i class="fas fa-film"></i><span>Movies</span></a>
  <a href="{{ url_for('webseries') }}" class="nav-item {% if request.endpoint == 'webseries' %}active{% endif %}"><i class="fas fa-tv"></i><span>Series</span></a>
  <a href="{{ url_for('contact') }}" class="nav-item {% if request.endpoint == 'contact' %}active{% endif %}"><i class="fas fa-envelope"></i><span>Request</span></a>
</nav>

<script>
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => { window.scrollY > 50 ? nav.classList.add('scrolled') : nav.classList.remove('scrolled'); });
    document.querySelectorAll('.carousel-arrow').forEach(button => {
        button.addEventListener('click', () => {
            const carousel = button.closest('.carousel-wrapper').querySelector('.carousel-content');
            const scroll = carousel.clientWidth * 0.8;
            carousel.scrollLeft += button.classList.contains('next') ? scroll : -scroll;
        });
    });
    document.addEventListener('DOMContentLoaded', function() {
        const slides = document.querySelectorAll('.hero-slide');
        if (slides.length > 1) {
            let currentSlide = 0;
            const showSlide = (index) => slides.forEach((s, i) => s.classList.toggle('active', i === index));
            setInterval(() => { currentSlide = (currentSlide + 1) % slides.length; showSlide(currentSlide); }, 5000);
        }
    });
</script>
{% if ad_settings.popunder_code %}{{ ad_settings.popunder_code|safe }}{% endif %}
{% if ad_settings.social_bar_code %}{{ ad_settings.social_bar_code|safe }}{% endif %}
</body>
</html>
"""

# --- START OF genres_html TEMPLATE ---
genres_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ title }} - MovieZone</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root { --netflix-red: #E50914; --netflix-black: #141414; --text-light: #f5f5f5; --text-dark: #a0a0a0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Roboto', sans-serif; background-color: var(--netflix-black); color: var(--text-light); }
  a { text-decoration: none; color: inherit; }
  
  .main-container { padding: 100px 50px 50px; }
  .page-title { font-family: 'Bebas Neue', sans-serif; font-size: 3rem; color: var(--netflix-red); margin-bottom: 30px; }
  .back-button { color: var(--text-light); font-size: 1rem; margin-bottom: 20px; display: inline-block; }
  .back-button:hover { color: var(--netflix-red); }
  
  .genre-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 20px;
  }
  .genre-card {
    background: linear-gradient(45deg, #2c2c2c, #1a1a1a);
    border-radius: 8px;
    padding: 30px 20px;
    text-align: center;
    font-size: 1.4rem;
    font-weight: 700;
    transition: transform 0.3s ease, background 0.3s ease;
    border: 1px solid #444;
  }
  .genre-card:hover {
    transform: translateY(-5px) scale(1.03);
    background: linear-gradient(45deg, var(--netflix-red), #b00710);
    border-color: var(--netflix-red);
  }
  @media (max-width: 768px) {
    .main-container { padding: 80px 15px 30px; }
    .page-title { font-size: 2.2rem; }
    .genre-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }
    .genre-card { font-size: 1.1rem; padding: 25px 15px; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
  <div class="main-container">
    <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a>
    <h1 class="page-title">{{ title }}</h1>
    <div class="genre-grid">
      {% for genre in genres %}
        <a href="{{ url_for('movies_by_genre', genre_name=genre) }}" class="genre-card">
          <span>{{ genre }}</span>
        </a>
      {% endfor %}
    </div>
  </div>
</body>
</html>
"""

# --- START OF detail_html TEMPLATE (FULLY REBUILT FOR CUSTOM PLAYER) ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieZone</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');
  :root { --netflix-red: #E50914; --netflix-black: #141414; --text-light: #f5f5f5; --text-dark: #a0a0a0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); }
  .detail-header { position: absolute; top: 0; left: 0; right: 0; padding: 20px 50px; z-index: 100; }
  .back-button { color: var(--text-light); font-size: 1.2rem; font-weight: 700; text-decoration: none; display: flex; align-items: center; gap: 10px; }
  .detail-hero { position: relative; width: 100%; display: flex; align-items: center; justify-content: center; padding: 100px 0; }
  .detail-hero-background { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-size: cover; background-position: center; filter: blur(20px) brightness(0.4); transform: scale(1.1); }
  .detail-hero::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(to top, rgba(20,20,20,1) 0%, rgba(20,20,20,0.6) 50%, rgba(20,20,20,1) 100%); }
  .detail-content-wrapper { position: relative; z-index: 2; display: flex; gap: 40px; max-width: 1200px; padding: 0 50px; width: 100%; }
  .detail-poster { width: 300px; height: 450px; flex-shrink: 0; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); object-fit: cover; }
  .detail-info { flex-grow: 1; max-width: 65%; }
  .detail-title { font-family: 'Bebas Neue', sans-serif; font-size: 4.5rem; line-height: 1.1; margin-bottom: 20px; }
  .detail-meta { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 25px; font-size: 1rem; color: var(--text-dark); }
  .detail-overview { font-size: 1.1rem; line-height: 1.6; margin-bottom: 30px; }
  .watch-now-btn, .episode-watch-button { background-color: var(--netflix-red); color: white; padding: 15px 30px; font-size: 1.2rem; font-weight: 700; border: none; border-radius: 5px; cursor: pointer; display: inline-flex; align-items: center; gap: 10px; width: 100%; justify-content: center; }
  .episode-watch-button { font-size: 1rem; padding: 12px 20px; }
  .episode-item { margin-bottom: 10px; }
  
  /* Custom Player Modal Styles */
  .modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.9); z-index: 1000; display: none;
    justify-content: center; align-items: center; backdrop-filter: blur(5px);
  }
  .modal-container { width: 95%; max-width: 1200px; }
  .player-wrapper { position: relative; width: 100%; aspect-ratio: 16 / 9; background: #000; }
  #custom-video-player { width: 100%; height: 100%; border-radius: 8px 8px 0 0; }
  .player-controls { padding: 15px 20px; background: #181818; border-radius: 0 0 8px 8px; }
  .controls-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
  #modal-title { font-size: 1.5rem; font-weight: 700; color: white; }
  .close-modal-btn { background: none; border: none; color: white; font-size: 2.2rem; cursor: pointer; line-height: 1; }
  .controls-bottom { display: flex; align-items: center; gap: 20px; }
  .info-group { display: flex; align-items: center; gap: 15px; font-size: 0.9rem; color: var(--text-dark); }
  .like-btn { background: none; border: none; color: white; cursor: pointer; font-size: 1.5rem; padding: 0; }
  .like-btn.liked { color: #00aaff; }

  @media (max-width: 992px) {
    .detail-content-wrapper { flex-direction: column; align-items: center; text-align: center; }
    .detail-info { max-width: 100%; }
    .watch-now-btn, .episode-watch-button { max-width: 400px; margin-left: auto; margin-right: auto; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
<header class="detail-header"><a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a></header>
{% if movie %}
<div class="detail-hero">
    <div class="detail-hero-background" style="background-image: url('{{ movie.poster or '' }}');"></div>
    <div class="detail-content-wrapper">
        <img class="detail-poster" src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}">
        <div class="detail-info">
            <h1 class="detail-title">{{ movie.title }}</h1>
            <p class="detail-overview">{{ movie.overview }}</p>

            {% if movie.type == 'movie' and movie.watch_link %}
                <button class="watch-now-btn" onclick="openPlayerModal('{{ movie._id }}', '{{ movie.title }}', '{{ movie.watch_link }}')">
                    <i class="fas fa-play"></i> Watch Now
                </button>
            {% elif movie.type == 'series' %}
                <h3>Episodes</h3>
                {% for ep in movie.episodes | sort(attribute='episode_number') %}
                    {% if ep.watch_link %}
                    <div class="episode-item">
                        <button class="episode-watch-button" onclick="openPlayerModal('{{ movie._id }}', '{{ movie.title }} - E{{ ep.episode_number }}', '{{ ep.watch_link }}')">
                            E{{ ep.episode_number }}: {{ ep.title }}
                        </button>
                    </div>
                    {% endif %}
                {% endfor %}
            {% else %}
                <p>No watchable links available.</p>
            {% endif %}
        </div>
    </div>
</div>
{% else %}
  <div style="text-align:center; padding-top:150px;"><h2>Content not found.</h2></div>
{% endif %}

<!-- Custom Player Modal -->
<div id="playerModal" class="modal-overlay">
    <div class="modal-container">
        <div class="player-wrapper">
            <video id="custom-video-player" controls controlsList="nodownload"></video>
        </div>
        <div class="player-controls">
            <div class="controls-top">
                <h3 id="modal-title"></h3>
                <button class="close-modal-btn">×</button>
            </div>
            <div class="controls-bottom">
                <button id="modal-like-btn" class="like-btn"><i class="far fa-thumbs-up"></i></button>
                <div class="info-group">
                    <span id="like-count">0 Likes</span>
                    <span>•</span>
                    <span id="view-count">0 Views</span>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const playerModal = document.getElementById('playerModal');
const videoPlayer = document.getElementById('custom-video-player');
const modalTitle = document.getElementById('modal-title');
const likeBtn = document.getElementById('modal-like-btn');
const likeCountSpan = document.getElementById('like-count');
const viewCountSpan = document.getElementById('view-count');
const closeBtn = document.querySelector('.close-modal-btn');
let currentMovieId = null;
let viewTriggered = false;

function openPlayerModal(movieId, title, videoUrl) {
    currentMovieId = movieId;
    modalTitle.textContent = title;
    videoPlayer.src = videoUrl;
    playerModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    viewTriggered = false;
    updateInteractionCounts();
}

function closePlayerModal() {
    playerModal.style.display = 'none';
    videoPlayer.pause();
    videoPlayer.src = "";
    document.body.style.overflow = 'auto';
}

closeBtn.addEventListener('click', closePlayerModal);
playerModal.addEventListener('click', (e) => {
    if (e.target === playerModal) closePlayerModal();
});

videoPlayer.addEventListener('play', () => {
    if (!viewTriggered) {
        fetch(`/api/movie/${currentMovieId}/view`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    const currentViews = parseInt(viewCountSpan.textContent) || 0;
                    viewCountSpan.textContent = `${currentViews + 1} Views`;
                }
            });
        viewTriggered = true;
    }
});

likeBtn.addEventListener('click', () => {
    if (likeBtn.classList.contains('liked')) return;
    fetch(`/api/movie/${currentMovieId}/like`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                localStorage.setItem(`liked_${currentMovieId}`, 'true');
                updateInteractionCounts();
            }
        });
});

async function updateInteractionCounts() {
    const response = await fetch(`/api/movie/${currentMovieId}/interactions`);
    const data = await response.json();
    if (data.success) {
        likeCountSpan.textContent = `${data.likes} Likes`;
        viewCountSpan.textContent = `${data.views} Views`;
        if (localStorage.getItem(`liked_${currentMovieId}`) === 'true') {
            likeBtn.classList.add('liked');
            likeBtn.querySelector('i').className = 'fas fa-thumbs-up';
        } else {
            likeBtn.classList.remove('liked');
            likeBtn.querySelector('i').className = 'far fa-thumbs-up';
        }
    }
}
</script>
</body>
</html>
"""

# --- START OF admin_html TEMPLATE (MODIFIED FOR DIRECT LINK) ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title><meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2, h3 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); }
    h2 { font-size: 2.5rem; margin-bottom: 20px; } h3 { font-size: 1.5rem; margin: 20px 0 10px 0;}
    form { max-width: 800px; margin: 0 auto 40px auto; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; } .form-group label { display: block; margin-bottom: 8px; font-weight: bold; }
    input[type="text"], input[type="url"], textarea, select, input[type="number"], input[type="email"] { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); font-size: 1rem; background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    button[type="submit"], .add-episode-btn { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem; transition: background 0.3s ease; }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    table { display: block; overflow-x: auto; white-space: nowrap; width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--light-gray); }
    th { background: #252525; } td { background: var(--dark-gray); }
    .action-buttons { display: flex; gap: 10px; }
    .action-buttons a, .action-buttons button { padding: 6px 12px; border-radius: 4px; text-decoration: none; color: white; border: none; cursor: pointer; transition: opacity 0.3s ease; }
    .edit-btn { background: #007bff; } .delete-btn { background: #dc3545; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    hr.section-divider { border: 0; height: 2px; background-color: var(--light-gray); margin: 40px 0; }
  </style>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
  <h2>বিজ্ঞাপন পরিচালনা (Ad Management)</h2>
  <form action="{{ url_for('save_ads') }}" method="post">
    <div class="form-group"><label>Pop-Under Ad Code</label><textarea name="popunder_code" rows="4">{{ ad_settings.popunder_code or '' }}</textarea></div>
    <div class="form-group"><label>Social Bar Ad Code</label><textarea name="social_bar_code" rows="4">{{ ad_settings.social_bar_code or '' }}</textarea></div>
    <div class="form-group"><label>Banner Ad Code</label><textarea name="banner_ad_code" rows="4">{{ ad_settings.banner_ad_code or '' }}</textarea></div>
    <div class="form-group"><label>Native Banner Code</label><textarea name="native_banner_code" rows="4">{{ ad_settings.native_banner_code or '' }}</textarea></div>
    <button type="submit">Save Ad Codes</button>
  </form>
  <hr class="section-divider">
  <h2>Add New Content</h2>
  <form method="post" action="{{ url_for('admin') }}">
    <div class="form-group"><label>Title (Required):</label><input type="text" name="title" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie">Movie</option><option value="series">TV/Web Series</option></select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Direct Video Link (.mp4):</label><input type="url" name="watch_link" /></div>
    </div>
    <div id="episode_fields" style="display: none;"><h3>Episodes</h3><div id="episodes_container"></div><button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button></div>
    <hr style="border-color: #333; margin: 20px 0;">
    <h3>Manual Details (Optional)</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview"></textarea></div>
    <div class="form-group"><label>Genres (Comma-separated):</label><input type="text" name="genres" /></div>
    <div class="form-group"><label>Poster Badge:</label><input type="text" name="poster_badge" /></div>
    <div class="form-group"><input type="checkbox" name="is_trending" value="true"><label style="display:inline-block">Is Trending?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true"><label style="display:inline-block">Is Coming Soon?</label></div>
    <button type="submit">Add Content</button>
  </form>
  <hr class="section-divider">
  <h2>Manage Content</h2>
  <table><thead><tr><th>Title</th><th>Type</th><th>Views</th><th>Likes</th><th>Actions</th></tr></thead><tbody>
    {% for movie in all_content %}<tr><td>{{ movie.title }}</td><td>{{ movie.type | title }}</td><td>{{ movie.views or 0 }}</td><td>{{ movie.likes or 0 }}</td><td class="action-buttons"><a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a><button class="delete-btn" onclick="confirmDelete('{{ movie._id }}', '{{ movie.title }}')">Delete</button></td></tr>{% endfor %}
  </tbody></table>
  <hr class="section-divider">
  <h2>User Feedback / Reports</h2>
  {% if feedback_list %}<table...>{% else %}<p>No new feedback.</p>{% endif %}
  <script>
    function confirmDelete(id, title) { if (confirm('Delete "' + title + '"?')) window.location.href = '/delete_movie/' + id; }
    function toggleEpisodeFields() { var isSeries = document.getElementById('content_type').value === 'series'; document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none'; document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block'; }
    function addEpisodeField() { const c = document.getElementById('episodes_container'), d = document.createElement('div'); d.className = 'episode-item'; d.innerHTML = `<div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div><div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div><div class="form-group"><label>Direct Video Link (.mp4):</label><input type="url" name="episode_watch_link[]" /></div><button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>`; c.appendChild(d); }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""

# --- START OF edit_html TEMPLATE (MODIFIED FOR DIRECT LINK) ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieZone</title><meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2, h3 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); }
    form { max-width: 800px; margin: auto; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    .form-group { margin-bottom: 15px; } label { display: block; margin-bottom: 8px; font-weight: bold; }
    input, textarea, select { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
    button[type="submit"], .add-episode-btn { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    .delete-btn { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  </style>
</head>
<body>
  <h2>Edit: {{ movie.title }}</h2>
  <form method="post">
    <div class="form-group"><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required /></div>
    <div class="form-group"><label>Content Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option><option value="series" {% if movie.type == 'series' %}selected{% endif %}>TV/Web Series</option></select></div>
    <div id="movie_fields"><div class="form-group"><label>Direct Video Link (.mp4):</label><input type="url" name="watch_link" value="{{ movie.watch_link or '' }}" /></div></div>
    <div id="episode_fields" style="display: none;">
        <h3>Episodes</h3><div id="episodes_container">
        {% if movie.type == 'series' and movie.episodes %}{% for ep in movie.episodes | sort(attribute='episode_number') %}
        <div class="episode-item">
            <div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" value="{{ ep.episode_number }}" required /></div>
            <div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" value="{{ ep.title }}" required /></div>
            <div class="form-group"><label>Direct Video Link (.mp4):</label><input type="url" name="episode_watch_link[]" value="{{ ep.watch_link or '' }}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>
        </div>
        {% endfor %}{% endif %}</div><button type="button" onclick="addEpisodeField()" class="add-episode-btn">Add Episode</button>
    </div>
    <hr>
    <h3>Manual Details</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster or '' }}" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview">{{ movie.overview or '' }}</textarea></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() { var isSeries = document.getElementById('content_type').value === 'series'; document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none'; document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block'; }
    function addEpisodeField() { const c = document.getElementById('episodes_container'), d = document.createElement('div'); d.className = 'episode-item'; d.innerHTML = `<div class="form-group"><label>Ep Number:</label><input type="number" name="episode_number[]" required /></div><div class="form-group"><label>Ep Title:</label><input type="text" name="episode_title[]" required /></div><div class="form-group"><label>Direct Video Link (.mp4):</label><input type="url" name="episode_watch_link[]" /></div><button type="button" onclick="this.parentElement.remove()" class="delete-btn">Remove Ep</button>`; c.appendChild(d); }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""

# --- START OF contact_html TEMPLATE ---
contact_html = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Contact Us / Report - MovieZone</title>
    <style>
        :root { --netflix-red: #E50914; --netflix-black: #141414; --dark-gray: #222; --light-gray: #333; --text-light: #f5f5f5; }
        body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .contact-container { max-width: 600px; width: 100%; background: var(--dark-gray); padding: 30px; border-radius: 8px; }
        h2 { font-family: 'Bebas Neue', sans-serif; color: var(--netflix-red); font-size: 2.5rem; text-align: center; margin-bottom: 25px; }
        .form-group { margin-bottom: 20px; } label { display: block; margin-bottom: 8px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); font-size: 1rem; background: var(--light-gray); color: var(--text-light); box-sizing: border-box; }
        textarea { resize: vertical; min-height: 120px; }
        button[type="submit"] { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; font-size: 1.1rem; width: 100%; transition: background 0.3s ease; }
        .success-message { text-align: center; padding: 20px; background-color: #1f4e2c; color: #d4edda; border-radius: 5px; margin-bottom: 20px; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: var(--netflix-red); text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="contact-container">
        <h2>Contact Us</h2>
        {% if message_sent %}
            <div class="success-message"><p>আপনার বার্তা সফলভাবে পাঠানো হয়েছে। ধন্যবাদ!</p></div>
            <a href="{{ url_for('home') }}" class="back-link">← Back to Home</a>
        {% else %}
            <form method="post">
                <div class="form-group"><label for="type">বিষয় (Subject):</label>
                    <select name="type" id="type">
                        <option value="Movie Request">Movie/Series Request</option>
                        <option value="Problem Report">Report a Problem</option>
                        <option value="General Feedback">General Feedback</option>
                    </select>
                </div>
                <div class="form-group"><label for="content_title">মুভি/সিরিজের নাম (Title):</label><input type="text" name="content_title" id="content_title" value="{{ prefill_title }}" required></div>
                <div class="form-group"><label for="message">আপনার বার্তা (Message):</label><textarea name="message" id="message" required></textarea></div>
                <button type="submit">Submit Message</button>
            </form>
            <a href="{{ url_for('home') }}" class="back-link">← Cancel and Go Home</a>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Flask Routes (Fully Updated for Custom Player) ---

def process_movie_list(movie_list): # <--- এই ফাংশনটি আবার যোগ করা হয়েছে
    for item in movie_list:
        if '_id' in item:
            item['_id'] = str(item['_id'])
    return movie_list

@app.route('/')
def home():
    query = request.args.get('q')
    if query:
        movies_list = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
        return render_template_string(index_html, movies=process_movie_list(movies_list), query=f'Results for "{query}"', is_full_page_list=True)
    
    all_badges = movies.distinct("poster_badge")
    all_badges = sorted([badge for badge in all_badges if badge])

    limit = 12
    context = {
        "trending_movies": process_movie_list(list(movies.find({"is_trending": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_movies": process_movie_list(list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "latest_series": process_movie_list(list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "coming_soon_movies": process_movie_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))),
        "recently_added": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(6))),
        "recently_added_full": process_movie_list(list(movies.find({"is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))),
        "is_full_page_list": False, "query": "", "all_badges": all_badges
    }
    return render_template_string(index_html, **context)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found", 404
        movie['_id'] = str(movie['_id'])
        return render_template_string(detail_html, movie=movie)
    except Exception:
        return "Invalid ID", 400

# --- API Endpoints for Custom Player ---
@app.route('/api/movie/<movie_id>/view', methods=['POST'])
def record_view(movie_id):
    try:
        movies.update_one({'_id': ObjectId(movie_id)}, {'$inc': {'views': 1}}, upsert=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/movie/<movie_id>/like', methods=['POST'])
def like_movie(movie_id):
    try:
        movies.update_one({'_id': ObjectId(movie_id)}, {'$inc': {'likes': 1}}, upsert=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/movie/<movie_id>/interactions')
def get_interactions(movie_id):
    try:
        movie = movies.find_one({'_id': ObjectId(movie_id)}, {'likes': 1, 'views': 1})
        if movie:
            return jsonify({
                'success': True,
                'likes': movie.get('likes', 0),
                'views': movie.get('views', 0)
            })
        return jsonify({'success': False, 'message': 'Movie not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Admin Routes ---
@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        movie_data = {
            "title": request.form.get("title"),
            "type": content_type,
            "poster": request.form.get("poster_url", "").strip(),
            "overview": request.form.get("overview", "").strip(),
            "genres": [g.strip() for g in request.form.get("genres", "").split(',') if g.strip()],
            "poster_badge": request.form.get("poster_badge", "").strip(),
            "is_trending": request.form.get("is_trending") == "true",
            "is_coming_soon": request.form.get("is_coming_soon") == "true",
            "likes": 0, "views": 0
        }
        if content_type == "movie":
            movie_data["watch_link"] = request.form.get("watch_link", "")
        else:
            episodes = []
            for i in range(len(request.form.getlist('episode_number[]'))):
                episodes.append({
                    "episode_number": int(request.form.getlist('episode_number[]')[i]),
                    "title": request.form.getlist('episode_title[]')[i],
                    "watch_link": request.form.getlist('episode_watch_link[]')[i]
                })
            movie_data["episodes"] = episodes
        movies.insert_one(movie_data)
        return redirect(url_for('admin'))
    
    all_content = process_movie_list(list(movies.find().sort('_id', -1)))
    ad_settings = settings.find_one() or {}
    feedback_list = list(feedback.find().sort('timestamp', -1))
    return render_template_string(admin_html, all_content=all_content, ad_settings=ad_settings, feedback_list=feedback_list)

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404
    if request.method == "POST":
        content_type = request.form.get("content_type", "movie")
        update_data = {
            "title": request.form.get("title"),
            "type": content_type,
            "poster": request.form.get("poster_url", "").strip(),
            "overview": request.form.get("overview", "").strip()
        }
        if content_type == "movie":
            update_data["watch_link"] = request.form.get("watch_link", "")
            if "episodes" in movie_obj:
                movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
        else:
            episodes = []
            for i in range(len(request.form.getlist('episode_number[]'))):
                episodes.append({
                    "episode_number": int(request.form.getlist('episode_number[]')[i]),
                    "title": request.form.getlist('episode_title[]')[i],
                    "watch_link": request.form.getlist('episode_watch_link[]')[i]
                })
            update_data["episodes"] = episodes
            if "watch_link" in movie_obj:
                movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"watch_link": ""}})

        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        return redirect(url_for('admin'))
    
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    movies.delete_one({"_id": ObjectId(movie_id)})
    return redirect(url_for('admin'))

@app.route('/admin/save_ads', methods=['POST'])
@requires_auth
def save_ads():
    ad_codes = {
        "popunder_code": request.form.get("popunder_code", ""),
        "social_bar_code": request.form.get("social_bar_code", ""),
        "banner_ad_code": request.form.get("banner_ad_code", ""),
        "native_banner_code": request.form.get("native_banner_code", "")
    }
    settings.update_one({}, {"$set": ad_codes}, upsert=True)
    return redirect(url_for('admin'))
    
@app.route('/feedback/delete/<feedback_id>')
@requires_auth
def delete_feedback(feedback_id):
    feedback.delete_one({"_id": ObjectId(feedback_id)})
    return redirect(url_for('admin'))

# --- Other Page Routes ---
def render_full_list(content_list, title):
    return render_template_string(index_html, movies=process_movie_list(content_list), query=title, is_full_page_list=True)

@app.route('/badge/<badge_name>')
def movies_by_badge(badge_name):
    return render_full_list(list(movies.find({"poster_badge": badge_name}).sort('_id', -1)), f'Tag: {badge_name}')

@app.route('/genres')
def genres_page():
    all_genres = movies.distinct("genres")
    all_genres = sorted([g for g in all_genres if g])
    return render_template_string(genres_html, genres=all_genres, title="Browse by Genre")

@app.route('/genre/<genre_name>')
def movies_by_genre(genre_name):
    return render_full_list(list(movies.find({"genres": genre_name}).sort('_id', -1)), f'Genre: {genre_name}')

@app.route('/trending_movies')
def trending_movies():
    return render_full_list(list(movies.find({"is_trending": True}).sort('_id', -1)), "Trending Now")

@app.route('/movies_only')
def movies_only():
    return render_full_list(list(movies.find({"type": "movie"}).sort('_id', -1)), "All Movies")

@app.route('/webseries')
def webseries():
    return render_full_list(list(movies.find({"type": "series"}).sort('_id', -1)), "All Web Series")

@app.route('/coming_soon')
def coming_soon():
    return render_full_list(list(movies.find({"is_coming_soon": True}).sort('_id', -1)), "Coming Soon")

@app.route('/recently_added')
def recently_added_all():
    return render_full_list(list(movies.find().sort('_id', -1)), "Recently Added")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        feedback_data = {
            "type": request.form.get("type"), "content_title": request.form.get("content_title"),
            "message": request.form.get("message"), "timestamp": datetime.utcnow()
        }
        feedback.insert_one(feedback_data)
        return render_template_string(contact_html, message_sent=True)
    prefill_title = request.args.get('title', '')
    return render_template_string(contact_html, message_sent=False, prefill_title=prefill_title)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
