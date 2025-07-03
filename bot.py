from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests, os
from functools import wraps
from dotenv import load_dotenv

# .env ফাইল থেকে এনভায়রনমেন্ট ভেরিয়েবল লোড করুন (শুধুমাত্র লোকাল ডেভেলপমেন্টের জন্য)
load_dotenv()

app = Flask(__name__)

# Environment variables for MongoDB URI and TMDb API Key
MONGO_URI = os.getenv("MONGO_URI")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# --- অ্যাডমিন অথেন্টিকেশনের জন্য নতুন ভেরিয়েবল ও ফাংশন ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin") # এনভায়রনমেন্ট ভেরিয়েবল থেকে ইউজারনেম নিন, ডিফল্ট 'admin'
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password") # এনভায়রনমেন্ট ভেরিয়েবল থেকে পাসওয়ার্ড নিন, ডিফল্ট 'password'

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
# --- অথেন্টিকেশন সংক্রান্ত পরিবর্তন শেষ ---

# Check if environment variables are set
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Error: TMDB_API_KEY environment variable not set. Exiting.")
    exit(1)

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)

# TMDb Genre Map (for converting genre IDs to names) - অপরিবর্তিত
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10402: "Music", 9648: "Mystery",
    10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller",
    10752: "War", 37: "Western", 10751: "Family", 14: "Fantasy", 36: "History"
}

# --- START OF index_html TEMPLATE (Netflix-style Redesign) ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MovieZone - Your Entertainment Hub</title>
<style>
  /* Google Fonts Import */
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');

  :root {
      --netflix-red: #E50914;
      --netflix-black: #141414;
      --text-light: #f5f5f5;
      --text-dark: #a0a0a0;
  }

  /* Reset & Basics */
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: 'Roboto', sans-serif;
    background-color: var(--netflix-black);
    color: var(--text-light);
    overflow-x: hidden;
  }
  a { text-decoration: none; color: inherit; }

  /* Custom Scrollbar for a cleaner look */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: #222; }
  ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--netflix-red); }

  /* Main Navigation Header */
  .main-nav {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      padding: 15px 50px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 100;
      transition: background-color 0.3s ease;
      background: linear-gradient(to bottom, rgba(0,0,0,0.7) 10%, rgba(0,0,0,0));
  }
  .main-nav.scrolled {
      background-color: var(--netflix-black);
  }
  .logo {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 32px;
      color: var(--netflix-red);
      font-weight: 700;
      letter-spacing: 1px;
  }
  .search-container {
      position: relative;
  }
  .search-input {
      background-color: rgba(0,0,0,0.7);
      border: 1px solid #777;
      color: var(--text-light);
      padding: 8px 15px;
      border-radius: 4px;
      transition: width 0.3s ease, background-color 0.3s ease;
      width: 250px;
  }
  .search-input:focus {
      background-color: rgba(0,0,0,0.9);
      border-color: var(--text-light);
      outline: none;
  }

  /* --- Netflix-style Hero Section --- */
  .hero-section {
      height: 90vh;
      position: relative;
      display: flex;
      align-items: flex-end;
      padding: 50px;
      background-size: cover;
      background-position: center top;
      color: white;
  }
  .hero-section::before { /* Gradient overlay for text readability */
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, var(--netflix-black) 10%, transparent 50%),
                  linear-gradient(to right, rgba(0,0,0,0.8) 0%, transparent 60%);
  }
  .hero-content {
      position: relative;
      z-index: 2;
      max-width: 50%;
  }
  .hero-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 5rem;
      font-weight: 700;
      margin-bottom: 1rem;
      line-height: 1;
  }
  .hero-overview {
      font-size: 1.1rem;
      line-height: 1.5;
      margin-bottom: 1.5rem;
      max-width: 600px;
      /* Clamp text to 3 lines */
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;  
      overflow: hidden;
  }
  .hero-buttons .btn {
      padding: 10px 25px;
      margin-right: 1rem;
      border: none;
      border-radius: 4px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.3s ease;
  }
  .btn.btn-primary {
      background-color: var(--netflix-red);
      color: white;
  }
  .btn.btn-secondary {
      background-color: rgba(109, 109, 110, 0.7);
      color: white;
  }
  .btn:hover { opacity: 0.8; }

  /* --- Carousel / Row Structure --- */
  main {
      padding: 0 0 50px 0;
  }
  .carousel-row {
      margin: 40px 0;
      position: relative;
  }
  .carousel-title {
      font-family: 'Roboto', sans-serif;
      font-weight: 700;
      font-size: 1.6rem;
      margin: 0 0 15px 50px;
  }
  .carousel-wrapper {
      position: relative;
  }
  .carousel-content {
      display: flex;
      gap: 10px;
      padding: 0 50px;
      overflow-x: scroll;
      scrollbar-width: none; /* For Firefox */
      -ms-overflow-style: none;  /* For IE and Edge */
      scroll-behavior: smooth;
  }
  .carousel-content::-webkit-scrollbar {
      display: none; /* For Chrome, Safari, and Opera */
  }

  /* Carousel Arrow Buttons */
  .carousel-arrow {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background-color: rgba(20, 20, 20, 0.5);
      border: none;
      color: white;
      font-size: 2.5rem;
      cursor: pointer;
      z-index: 10;
      width: 50px;
      height: 100%; /* Full height of the card row */
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.3s ease;
  }
  .carousel-row:hover .carousel-arrow {
      opacity: 1;
  }
  .carousel-arrow.prev { left: 0; border-radius: 0 4px 4px 0; }
  .carousel-arrow.next { right: 0; border-radius: 4px 0 0 4px; }
  .carousel-arrow:hover { background-color: rgba(20, 20, 20, 0.8); }

  /* Movie Card in Carousel */
  .movie-card {
      flex: 0 0 16.66%; /* 6 cards on large screens */
      min-width: 220px;
      border-radius: 4px;
      overflow: hidden;
      cursor: pointer;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      position: relative;
      background-color: #222;
  }
  .movie-card:hover {
      transform: scale(1.05);
      z-index: 5;
      box-shadow: 0 10px 20px rgba(0,0,0,0.5);
  }
  .movie-poster {
      width: 100%;
      aspect-ratio: 2 / 3;
      object-fit: cover;
      display: block;
  }

  /* Search results / full page list styles */
  .full-page-grid-container {
      padding: 100px 50px 50px 50px; /* Padding to account for fixed header */
  }
  .full-page-grid-title {
      font-size: 2.5rem;
      font-weight: 700;
      margin-bottom: 30px;
  }
  .full-page-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 15px;
  }
  .full-page-grid .movie-card {
      min-width: 0; /* Override min-width for grid layout */
  }
  
  /* Media Queries for Responsiveness */
  @media (max-width: 1200px) {
      .movie-card { flex: 0 0 20%; } /* 5 cards */
  }
  @media (max-width: 992px) {
      .hero-title { font-size: 3.5rem; }
      .hero-overview { font-size: 1rem; }
      .hero-content { max-width: 70%; }
      .movie-card { flex: 0 0 25%; } /* 4 cards */
      .main-nav { padding: 15px 30px; }
      .carousel-title, .carousel-content, .full-page-grid-container { padding-left: 30px; padding-right: 30px; }
      .carousel-arrow { width: 30px; font-size: 2rem; }
  }
  @media (max-width: 768px) {
      .logo { font-size: 24px; }
      .search-input { width: 150px; }
      .hero-section { height: 70vh; }
      .hero-title { font-size: 2.5rem; }
      .hero-overview { display: none; } /* Hide overview on smaller screens */
      .hero-content { max-width: 100%; }
      .movie-card { flex: 0 0 33.33%; } /* 3 cards */
  }
  @media (max-width: 576px) {
      .movie-card { flex: 0 0 45%; } /* 2 cards */
      .main-nav { padding: 10px 15px; }
      .carousel-title, .carousel-content, .full-page-grid-container { padding-left: 15px; padding-right: 15px; }
  }

</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body>
<header class="main-nav">
  <a href="{{ url_for('home') }}" class="logo">MovieZone</a>
  <div class="search-container">
    <form method="GET" action="/">
      <input type="search" name="q" class="search-input" placeholder="Titles, genres..." value="{{ query|default('') }}" />
    </form>
  </div>
</header>

<main>
  {# Conditional rendering: Search results/full list vs. Homepage with carousels #}
  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      {% if movies|length == 0 %}
        <p style="text-align:center; color: var(--text-dark); margin-top: 40px;">No content found.</p>
      {% else %}
        <div class="full-page-grid">
          {% for m in movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  {% else %} {# Original home page with carousels #}
    
    {# --- Netflix-style Hero Section --- #}
    {% if trending_movies %}
      {% set hero_movie = trending_movies[0] %}
      <div class="hero-section" style="background-image: url('{{ hero_movie.poster or '' }}');">
        <div class="hero-content">
          <h1 class="hero-title">{{ hero_movie.title }}</h1>
          <p class="hero-overview">{{ hero_movie.overview }}</p>
          <div class="hero-buttons">
            <a href="{{ url_for('movie_detail', movie_id=hero_movie._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>
            <a href="{{ url_for('movie_detail', movie_id=hero_movie._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
          </div>
        </div>
      </div>
    {% endif %}

    {# --- Carousel for Trending Movies --- #}
    {% if trending_movies %}
    <div class="carousel-row" id="trending">
      <h2 class="carousel-title">Trending on MovieZone</h2>
      <div class="carousel-wrapper">
        <div class="carousel-content">
          {% for m in trending_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
        <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
        <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    {% endif %}

    {# --- Carousel for Latest Movies --- #}
    {% if latest_movies %}
    <div class="carousel-row" id="latest-movies">
      <h2 class="carousel-title">Latest Movies</h2>
      <div class="carousel-wrapper">
        <div class="carousel-content">
          {% for m in latest_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
        <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
        <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    {% endif %}
    
    {# --- Carousel for Web Series --- #}
    {% if latest_series %}
    <div class="carousel-row" id="web-series">
      <h2 class="carousel-title">Web Series</h2>
      <div class="carousel-wrapper">
        <div class="carousel-content">
          {% for m in latest_series %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
        <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
        <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    {% endif %}

    {# --- Carousel for Recently Added --- #}
    {% if recently_added %}
    <div class="carousel-row" id="recently-added">
      <h2 class="carousel-title">Recently Added</h2>
      <div class="carousel-wrapper">
        <div class="carousel-content">
          {% for m in recently_added %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
        <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
        <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    {% endif %}

    {# --- Carousel for Coming Soon --- #}
    {% if coming_soon_movies %}
    <div class="carousel-row" id="coming-soon">
      <h2 class="carousel-title">Coming Soon</h2>
      <div class="carousel-wrapper">
        <div class="carousel-content">
          {% for m in coming_soon_movies %}
          <a href="{{ url_for('movie_detail', movie_id=m._id) }}" class="movie-card">
            <img class="movie-poster" src="{{ m.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ m.title }}">
          </a>
          {% endfor %}
        </div>
        <button class="carousel-arrow prev"><i class="fas fa-chevron-left"></i></button>
        <button class="carousel-arrow next"><i class="fas fa-chevron-right"></i></button>
      </div>
    </div>
    {% endif %}

  {% endif %} {# End of is_full_page_list block #}
</main>

<script>
    // Navbar scroll effect
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    });

    // Carousel arrow functionality
    document.querySelectorAll('.carousel-arrow').forEach(button => {
        button.addEventListener('click', () => {
            const carouselContent = button.parentElement.querySelector('.carousel-content');
            const scrollAmount = carouselContent.clientWidth * 0.8; // Scroll 80% of the visible width
            if (button.classList.contains('next')) {
                carouselContent.scrollLeft += scrollAmount;
            } else {
                carouselContent.scrollLeft -= scrollAmount;
            }
        });
    });
</script>
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# --- START OF detail_html TEMPLATE (Netflix-style Redesign) ---
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieZone Details</title>
<style>
  /* Google Fonts Import */
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap');

  :root {
      --netflix-red: #E50914;
      --netflix-black: #141414;
      --text-light: #f5f5f5;
      --text-dark: #a0a0a0;
  }
  
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto', sans-serif;
    background: var(--netflix-black);
    color: var(--text-light);
  }

  /* Header with back button */
  .detail-header {
      position: absolute; top: 0; left: 0; right: 0;
      padding: 20px 50px;
      z-index: 100;
  }
  .back-button {
      color: var(--text-light);
      font-size: 1.2rem;
      font-weight: 700;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: color 0.3s ease;
  }
  .back-button:hover {
      color: var(--netflix-red);
  }

  /* --- Detail Hero with Blurred Background --- */
  .detail-hero {
      position: relative;
      width: 100%;
      height: 100vh;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
  }
  .detail-hero-background {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background-size: cover;
      background-position: center;
      filter: blur(20px) brightness(0.4);
      transform: scale(1.1); /* To avoid blurred edges */
  }
  .detail-hero::after { /* Gradient overlay */
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(to top, rgba(20,20,20,1) 0%, rgba(20,20,20,0.6) 50%, rgba(20,20,20,1) 100%);
  }

  /* --- Main Content Area on Top --- */
  .detail-content-wrapper {
      position: relative;
      z-index: 2;
      display: flex;
      gap: 40px;
      max-width: 1200px;
      padding: 0 50px;
      width: 100%;
  }

  .detail-poster {
      width: 300px;
      height: 450px;
      flex-shrink: 0;
      border-radius: 8px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      object-fit: cover;
  }
  .detail-info {
      flex-grow: 1;
      max-width: 65%;
  }
  .detail-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 4.5rem;
      font-weight: 700;
      line-height: 1.1;
      margin-bottom: 20px;
  }
  .detail-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 15px;
      margin-bottom: 25px;
      font-size: 1rem;
      color: var(--text-dark);
  }
  .detail-meta span {
      font-weight: 500;
      color: var(--text-light);
  }
  .detail-overview {
      font-size: 1.1rem;
      line-height: 1.6;
      margin-bottom: 30px;
  }
  
  /* --- Download Section --- */
  .download-section {
    width: 100%;
  }
  .download-section h3 {
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 15px;
      padding-bottom: 5px;
      border-bottom: 2px solid var(--netflix-red);
      display: inline-block;
  }
  .download-item, .episode-item {
      margin-bottom: 15px;
  }
  .download-button, .episode-download-button {
      display: inline-block;
      padding: 10px 20px;
      background-color: var(--netflix-red);
      color: white;
      text-decoration: none;
      border-radius: 4px;
      font-weight: 700;
      transition: background-color 0.3s ease;
      margin-right: 10px;
  }
  .download-button:hover, .episode-download-button:hover {
      background-color: #b00710;
  }
  .no-link-message {
      color: var(--text-dark);
      font-style: italic;
  }
  .episode-title {
      font-size: 1.2rem;
      font-weight: 700;
      margin-bottom: 8px;
      color: #fff;
  }
  .episode-overview-text {
      font-size: 0.9rem;
      color: var(--text-dark);
      margin-bottom: 10px;
  }

  /* Responsive Adjustments */
  @media (max-width: 992px) {
      .detail-content-wrapper { flex-direction: column; align-items: center; text-align: center; }
      .detail-info { max-width: 100%; }
      .detail-title { font-size: 3.5rem; }
      .detail-meta { justify-content: center; }
  }
  @media (max-width: 768px) {
      .detail-hero { height: auto; padding: 120px 0 50px 0; }
      .detail-content-wrapper { padding: 0 20px; gap: 30px; }
      .detail-poster { width: 200px; height: 300px; }
      .detail-title { font-size: 2.5rem; }
      .detail-header { padding: 20px; }
  }

</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body>
<header class="detail-header">
  <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a>
</header>
{% if movie %}
<div class="detail-hero">
  <div class="detail-hero-background" style="background-image: url('{{ movie.poster }}');"></div>
  
  <div class="detail-content-wrapper">
    <img class="detail-poster" src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}">
    <div class="detail-info">
      <h1 class="detail-title">{{ movie.title }}</h1>
      <div class="detail-meta">
        {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
        {% if movie.vote_average %}<span><i class="fas fa-star" style="color:#f5c518;"></i> {{ "%.1f"|format(movie.vote_average) }}/10</span>{% endif %}
        {% if movie.original_language %}<span>{{ movie.original_language | upper }}</span>{% endif %}
      </div>
      <p class="detail-overview">{{ movie.overview }}</p>
      
      <div class="download-section">
        {% if movie.type == 'movie' %}
          <h3>Download Links</h3>
          {% if movie.links and movie.links|length > 0 %}
            {% for link_item in movie.links %}
            <a class="download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">
              <i class="fas fa-download"></i> {{ link_item.quality }} [{{ link_item.size }}]
            </a>
            {% endfor %}
          {% else %}
            <p class="no-link-message">No download links available yet.</p>
          {% endif %}
        
        {% elif movie.type == 'series' and movie.episodes and movie.episodes|length > 0 %}
          <h3>Episodes</h3>
          {% for episode in movie.episodes | sort(attribute='episode_number') %}
          <div class="episode-item">
            <h4 class="episode-title">E{{ episode.episode_number }}: {{ episode.title }}</h4>
            {% if episode.overview %}<p class="episode-overview-text">{{ episode.overview }}</p>{% endif %}
            {% if episode.links and episode.links|length > 0 %}
              {% for link_item in episode.links %}
              <a class="episode-download-button" href="{{ link_item.url }}" target="_blank" rel="noopener">
                <i class="fas fa-download"></i> {{ link_item.quality }}
              </a>
              {% endfor %}
            {% else %}
              <p class="no-link-message">No links for this episode.</p>
            {% endif %}
          </div>
          {% endfor %}
        
        {% else %}
          <p class="no-link-message">Coming Soon...</p>
        {% endif %}
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


# --- START OF admin_html TEMPLATE (Dark theme update) ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieZone</title>
  <style>
    :root {
      --netflix-red: #E50914;
      --netflix-black: #141414;
      --dark-gray: #222;
      --light-gray: #333;
      --text-light: #f5f5f5;
    }
    body { font-family: 'Roboto', sans-serif; background: var(--netflix-black); color: var(--text-light); padding: 20px; }
    h2 { 
      font-family: 'Bebas Neue', sans-serif;
      color: var(--netflix-red);
      font-size: 2.5rem;
      margin-bottom: 20px;
    }
    form { max-width: 800px; margin-bottom: 40px; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    
    .form-group { margin-bottom: 15px; }
    .form-group label {
        display: block; margin-bottom: 8px; font-weight: bold;
    }
    input[type="text"], input[type="url"], textarea, select, input[type="number"], input[type="search"] {
      width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray);
      font-size: 1rem; background: var(--light-gray); color: var(--text-light);
    }
    input[type="checkbox"] { width: auto; margin-right: 10px; transform: scale(1.2); }
    textarea { resize: vertical; min-height: 100px; }
    
    button[type="submit"], .add-episode-btn {
      background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer;
      border: none; padding: 12px 25px; border-radius: 4px; font-size: 1rem;
      transition: background 0.3s ease;
    }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--light-gray); }
    th { background: #252525; }
    td { background: var(--dark-gray); }

    .action-buttons { display: flex; gap: 10px; }
    .action-buttons a, .action-buttons button {
        padding: 6px 12px; border-radius: 4px; text-decoration: none;
        color: white; border: none; cursor: pointer; transition: opacity 0.3s ease;
    }
    .edit-btn { background: #007bff; }
    .delete-btn { background: #dc3545; }
    .action-buttons a:hover, .action-buttons button:hover { opacity: 0.8; }
    .episode-item {
        border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px;
    }
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


# --- START OF edit_html TEMPLATE (Dark theme update) ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieZone</title>
  <style>
    :root {
      --netflix-red: #E50914;
      --netflix-black: #141414;
      --dark-gray: #222;
      --light-gray: #333;
      --text-light: #f5f5f5;
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
      transition: background 0.3s ease;
    }
    button[type="submit"]:hover, .add-episode-btn:hover { background: #b00710; }
    .back-to-admin { display: inline-block; margin-bottom: 20px; color: var(--netflix-red); text-decoration: none; font-weight: bold; }
    .episode-item { border: 1px solid var(--light-gray); padding: 15px; margin-bottom: 15px; border-radius: 5px; }
    .delete-btn { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
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


# [নিচের Python কোডটি অপরিবর্তিত থাকবে, শুধু home() ফাংশনে সামান্য পরিবর্তন আসবে]

@app.route('/')
def home():
    query = request.args.get('q')
    
    # Initialize all lists
    movies_list = []
    trending_movies_list = []
    latest_movies_list = []
    latest_series_list = []
    coming_soon_movies_list = []
    recently_added_list = []

    is_full_page_list = False # Flag to determine layout

    if query:
        # If there's a search query, show a full grid page
        result = movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1)
        movies_list = list(result)
        is_full_page_list = True
    else:
        # Otherwise, fetch data for homepage carousels
        limit = 18 # Fetch a bit more for carousels
        trending_movies_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1).limit(limit))
        latest_movies_list = list(movies.find({"type": "movie", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))
        latest_series_list = list(movies.find({"type": "series", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(limit))
        coming_soon_movies_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1).limit(limit))
        recently_added_list = list(movies.find().sort('_id', -1).limit(limit))

    # Consolidate all lists that need ID conversion
    all_fetched_content = movies_list + trending_movies_list + latest_movies_list + latest_series_list + coming_soon_movies_list + recently_added_list
    # Use a set to avoid duplicate processing if an item is in multiple lists
    processed_ids = set()
    for m in all_fetched_content:
        if str(m['_id']) not in processed_ids:
            m['_id'] = str(m['_id'])
            processed_ids.add(m['_id'])

    return render_template_string(
        index_html, 
        movies=movies_list, 
        query=query,
        trending_movies=trending_movies_list,
        latest_movies=latest_movies_list,
        latest_series=latest_series_list,
        coming_soon_movies=coming_soon_movies_list,
        recently_added=recently_added_list,
        is_full_page_list=is_full_page_list
    )

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie['_id'] = str(movie['_id'])
            
            # Determine TMDb search type based on content type
            tmdb_search_type = "movie" if movie.get("type") == "movie" else "tv"
            
            # Only fetch if TMDb API key is available and some crucial info is missing or default
            should_fetch_tmdb = TMDB_API_KEY and (
                not movie.get("tmdb_id") or 
                movie.get("overview") == "No overview available." or 
                not movie.get("poster")
            )

            if should_fetch_tmdb:
                tmdb_id = movie.get("tmdb_id") 
                
                # If TMDb ID is not stored, search by title first
                if not tmdb_id:
                    search_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={movie['title']}"
                    try:
                        search_res = requests.get(search_url, timeout=5).json()
                        if search_res and "results" in search_res and search_res["results"]:
                            tmdb_id = search_res["results"][0].get("id")
                            # Update the movie in DB with tmdb_id for future faster access
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"tmdb_id": tmdb_id}})
                        else:
                            print(f"No search results found on TMDb for title: {movie['title']} ({tmdb_search_type})")
                            tmdb_id = None
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for search '{movie['title']}': {e}")
                        tmdb_id = None
                    except Exception as e:
                        print(f"An unexpected error occurred during TMDb search: {e}")
                        tmdb_id = None

                # If TMDb ID is found (either from DB or search), fetch full details
                if tmdb_id:
                    tmdb_detail_url = f"https://api.themoviedb.org/3/{tmdb_search_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
                    try:
                        res = requests.get(tmdb_detail_url, timeout=5).json()
                        if res:
                            # Update common fields
                            if movie.get("overview") == "No overview available." and res.get("overview"):
                                movie["overview"] = res.get("overview")
                            if not movie.get("poster") and res.get("poster_path"):
                                movie["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
                            
                            # Handle Movie specific fields
                            if tmdb_search_type == "movie":
                                release_date = res.get("release_date")
                                if movie.get("year") == "N/A" and release_date:
                                    movie["year"] = release_date[:4]
                                    movie["release_date"] = release_date
                                if movie.get("vote_average") is None and res.get("vote_average"):
                                    movie["vote_average"] = res.get("vote_average")
                                if movie.get("original_language") == "N/A" and res.get("original_language"):
                                    movie["original_language"] = res.get("original_language")
                                
                                genres_ids = res.get("genres", [])
                            # Handle TV Series specific fields
                            elif tmdb_search_type == "tv":
                                first_air_date = res.get("first_air_date")
                                if movie.get("year") == "N/A" and first_air_date:
                                    movie["year"] = first_air_date[:4]
                                    movie["release_date"] = first_air_date # Use first_air_date as release_date for series
                                if movie.get("vote_average") is None and res.get("vote_average"):
                                    movie["vote_average"] = res.get("vote_average")
                                if movie.get("original_language") == "N/A" and res.get("original_language"):
                                    movie["original_language"] = res.get("original_language")
                                
                                genres_ids = res.get("genres", [])
                                # Update title if TMDb provides a better one (e.g., from original_name to name)
                                if res.get("name") and movie["title"] == data["title"]: # Check if current title is the original input
                                    movie["title"] = res.get("name")

                            genres_names = []
                            for genre_obj in genres_ids:
                                if isinstance(genre_obj, dict) and genre_obj.get("id") in TMDb_Genre_Map:
                                    genres_names.append(TMDb_Genre_Map[genre_obj["id"]])
                            if (not movie.get("genres") or movie["genres"] == []) and genres_names:
                                movie["genres"] = genres_names

                            # Persist TMDb fetched data to DB
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {
                                "title": movie["title"], # Title might be updated for series
                                "overview": movie["overview"],
                                "poster": movie["poster"],
                                "year": movie["year"],
                                "release_date": movie["release_date"],
                                "vote_average": movie["vote_average"],
                                "original_language": movie["original_language"],
                                "genres": movie["genres"]
                            }})
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for detail '{movie_id}': {e}")
                    except Exception as e:
                        print(f"An unexpected error occurred while fetching TMDb detail data: {e}")
                else:
                    print(f"TMDb ID not found for content '{movie.get('title', movie_id)}'. Skipping TMDb detail fetch.")
            else:
                print("Skipping TMDb API call for content details (no key or data already present).")

        return render_template_string(detail_html, movie=movie)
    except Exception as e:
        print(f"Error fetching movie detail for ID {movie_id}: {e}")
        return render_template_string(detail_html, movie=None)

@app.route('/admin', methods=["GET", "POST"])
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def admin():
    if request.method == "POST":
        title = request.form.get("title")
        content_type = request.form.get("content_type", "movie") # New: 'movie' or 'series'
        quality_tag = request.form.get("quality", "").upper()
        
        # Get manual inputs
        manual_overview = request.form.get("overview")
        manual_poster_url = request.form.get("poster_url")
        manual_year = request.form.get("year")
        manual_original_language = request.form.get("original_language")
        manual_genres_str = request.form.get("genres")
        manual_top_label = request.form.get("top_label") # Get custom top label
        is_trending = request.form.get("is_trending") == "true" # New: Checkbox for trending
        is_coming_soon = request.form.get("is_coming_soon") == "true" # New: Checkbox for coming soon

        # Process manual genres (comma-separated string to list)
        manual_genres_list = [g.strip() for g in manual_genres_str.split(',') if g.strip()] if manual_genres_str else []

        # If is_trending is true, force quality to 'TRENDING'
        if is_trending:
            quality_tag = "TRENDING"

        movie_data = {
            "title": title,
            "quality": quality_tag,
            "type": content_type, # Use selected content type
            "overview": manual_overview if manual_overview else "No overview available.",
            "poster": manual_poster_url if manual_poster_url else "",
            "year": manual_year if manual_year else "N/A",
            "release_date": manual_year if manual_year else "N/A", 
            "vote_average": None,
            "original_language": manual_original_language if manual_original_language else "N/A",
            "genres": manual_genres_list,
            "tmdb_id": None,
            "top_label": manual_top_label if manual_top_label else "",
            "is_coming_soon": is_coming_soon # Store coming soon status
        }

        # Try to fetch from TMDb only if no manual poster or overview was provided
        if TMDB_API_KEY and (not manual_poster_url and not manual_overview or movie_data["overview"] == "No overview available." or not movie_data["poster"]):
            tmdb_search_type = "movie" if content_type == "movie" else "tv"
            tmdb_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={title}"
            try:
                res = requests.get(tmdb_url, timeout=5).json()
                if res and "results" in res and res["results"]:
                    data = res["results"][0]
                    
                    # Update TMDb ID
                    movie_data["tmdb_id"] = data.get("id")

                    # Overwrite only if TMDb provides a value and manual data wasn't explicitly provided
                    if not manual_overview and data.get("overview"):
                        movie_data["overview"] = data.get("overview")
                    if not manual_poster_url and data.get("poster_path"):
                        movie_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                    
                    # Specific fields for movie or series
                    if tmdb_search_type == "movie":
                        release_date = data.get("release_date")
                        if not manual_year and release_date:
                            movie_data["year"] = release_date[:4]
                            movie_data["release_date"] = release_date
                        
                        movie_data["vote_average"] = data.get("vote_average", movie_data["vote_average"])
                        if not manual_original_language and data.get("original_language"):
                            movie_data["original_language"] = data.get("original_language")
                        
                        genres_ids = data.get("genre_ids", [])
                        
                    elif tmdb_search_type == "tv":
                        first_air_date = data.get("first_air_date")
                        if not manual_year and first_air_date:
                            movie_data["year"] = first_air_date[:4]
                            movie_data["release_date"] = first_air_date
                        
                        movie_data["vote_average"] = data.get("vote_average", movie_data["vote_average"])
                        if not manual_original_language and data.get("original_language"):
                            movie_data["original_language"] = data.get("original_language")
                        
                        genres_ids = data.get("genre_ids", [])
                        # Update title from TMDb for series, as 'name' is often better than initial search query
                        movie_data["title"] = data.get("name", title)

                    genres_names = []
                    for genre_id in genres_ids:
                        if genre_id in TMDb_Genre_Map:
                            genres_names.append(TMDb_Genre_Map[genre_id])
                    if not manual_genres_list and genres_names: # Only update genres if TMDb provides them AND no manual genres
                        movie_data["genres"] = genres_names
                    
                else:
                    print(f"No results found on TMDb for title: {title} ({tmdb_search_type})")
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to TMDb API for '{title}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred while fetching TMDb data: {e}")
        else:
            print("Skipping TMDb API call (manual poster/overview provided or no key).")

        # Handle download links based on content type
        if content_type == "movie":
            links_list = []
            link_480p = request.form.get("link_480p")
            if link_480p:
                links_list.append({"quality": "480p", "size": "590MB", "url": link_480p})
            link_720p = request.form.get("link_720p")
            if link_720p:
                links_list.append({"quality": "720p", "size": "1.4GB", "url": link_720p})
            link_1080p = request.form.get("link_1080p")
            if link_1080p:
                links_list.append({"quality": "1080p", "size": "2.9GB", "url": link_1080p})
            movie_data["links"] = links_list
        else: # content_type == "series"
            episodes_list = []
            episode_numbers = request.form.getlist('episode_number[]')
            episode_titles = request.form.getlist('episode_title[]')
            episode_overviews = request.form.getlist('episode_overview[]')
            episode_link_480ps = request.form.getlist('episode_link_480p[]')
            episode_link_720ps = request.form.getlist('episode_link_720p[]')
            episode_link_1080ps = request.form.getlist('episode_link_1080p[]')

            for i in range(len(episode_numbers)):
                episode_links = []
                if episode_link_480ps and i < len(episode_link_480ps) and episode_link_480ps[i]:
                    episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                if episode_link_720ps and i < len(episode_link_720ps) and episode_link_720ps[i]:
                    episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                if episode_link_1080ps and i < len(episode_link_1080ps) and episode_link_1080ps[i]:
                    episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                
                episodes_list.append({
                    "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                    "title": episode_titles[i] if i < len(episode_titles) and episode_titles else "",
                    "overview": episode_overviews[i] if i < len(episode_overviews) and episode_overviews else "",
                    "links": episode_links
                })
            movie_data["episodes"] = episodes_list

        try:
            movies.insert_one(movie_data)
            print(f"Content '{movie_data['title']}' added successfully to MovieZone!")
            return redirect(url_for('admin')) # Redirect to admin after POST
        except Exception as e:
            print(f"Error inserting content into MongoDB: {e}")
            return redirect(url_for('admin'))

    # --- GET request handling (Modified for search) ---
    admin_query = request.args.get('q') # Get the search query from URL

    if admin_query:
        # Search content by title (case-insensitive regex)
        all_content = list(movies.find({"title": {"$regex": admin_query, "$options": "i"}}).sort('_id', -1))
    else:
        # If no search query, fetch all content (as before)
        all_content = list(movies.find().sort('_id', -1))
    
    # Convert ObjectIds to string for template
    for content in all_content:
        content['_id'] = str(content['_id']) 

    return render_template_string(admin_html, movies=all_content, admin_query=admin_query)


@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def edit_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            return "Movie not found!", 404

        if request.method == "POST":
            # Extract updated data from form
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
            
            # Prepare updated data for MongoDB
            updated_data = {
                "title": title,
                "quality": quality_tag,
                "type": content_type,
                "overview": manual_overview if manual_overview else "No overview available.",
                "poster": manual_poster_url if manual_poster_url else "",
                "year": manual_year if manual_year else "N/A",
                "release_date": manual_year if manual_year else "N/A", # Assuming release_date is same as year if manually entered
                "original_language": manual_original_language if manual_original_language else "N/A",
                "genres": manual_genres_list,
                "top_label": manual_top_label if manual_top_label else "",
                "is_coming_soon": is_coming_soon
            }

            # If TMDb API Key is available and no manual overview/poster provided, fetch and update
            if TMDB_API_KEY and (not manual_poster_url and not manual_overview or movie.get("overview") == "No overview available." or not movie.get("poster")): 
                tmdb_search_type = "movie" if content_type == "movie" else "tv"
                tmdb_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={title}"
                try:
                    res = requests.get(tmdb_url, timeout=5).json()
                    if res and "results" in res and res["results"]:
                        data = res["results"][0]
                        # Update TMDb ID
                        updated_data["tmdb_id"] = data.get("id")

                        # Only update if TMDb provides a value and manual data wasn't explicitly provided
                        if not manual_overview and data.get("overview"):
                            updated_data["overview"] = data.get("overview")
                        if not manual_poster_url and data.get("poster_path"):
                            updated_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                        
                        # Specific fields for movie or series
                        if tmdb_search_type == "movie":
                            release_date = data.get("release_date")
                            if not manual_year and release_date:
                                updated_data["year"] = release_date[:4]
                                updated_data["release_date"] = release_date
                            
                            updated_data["vote_average"] = data.get("vote_average", movie.get("vote_average"))
                            if not manual_original_language and data.get("original_language"):
                                updated_data["original_language"] = data.get("original_language")
                            
                            genres_ids = data.get("genre_ids", [])
                        
                        elif tmdb_search_type == "tv":
                            first_air_date = data.get("first_air_date")
                            if not manual_year and first_air_date:
                                updated_data["year"] = first_air_date[:4]
                                updated_data["release_date"] = first_air_date
                            
                            updated_data["vote_average"] = data.get("vote_average", movie.get("vote_average"))
                            if not manual_original_language and data.get("original_language"):
                                updated_data["original_language"] = data.get("original_language")
                            
                            genres_ids = data.get("genre_ids", [])
                            # Update title from TMDb for series, as 'name' is often better than initial search query
                            updated_data["title"] = data.get("name", title)

                        genres_names = []
                        for genre_id in genres_ids:
                            if genre_id in TMDb_Genre_Map:
                                genres_names.append(TMDb_Genre_Map[genre_id])
                        if not manual_genres_list and genres_names:
                            updated_data["genres"] = genres_names
                        
                    else:
                        print(f"No results found on TMDb for title: {title} ({tmdb_search_type}) during edit.")
                except requests.exceptions.RequestException as e:
                    print(f"Error connecting to TMDb API for '{title}' during edit: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while fetching TMDb data during edit: {e}")
            else:
                print("Skipping TMDb API call (manual poster/overview provided or no key).")

            # Handle download links based on content type
            if content_type == "movie":
                links_list = []
                link_480p = request.form.get("link_480p")
                if link_480p:
                    links_list.append({"quality": "480p", "size": "590MB", "url": link_480p})
                link_720p = request.form.get("link_720p")
                if link_720p:
                    links_list.append({"quality": "720p", "size": "1.4GB", "url": link_720p})
                link_1080p = request.form.get("link_1080p")
                if link_1080p:
                    links_list.append({"quality": "1080p", "size": "2.9GB", "url": link_1080p})
                updated_data["links"] = links_list
                # Remove episodes if present for a movie
                if "episodes" in movie:
                    movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
            else: # content_type == "series"
                episodes_list = []
                episode_numbers = request.form.getlist('episode_number[]')
                episode_titles = request.form.getlist('episode_title[]')
                episode_overviews = request.form.getlist('episode_overview[]')
                episode_link_480ps = request.form.getlist('episode_link_480p[]')
                episode_link_720ps = request.form.getlist('episode_link_720p[]')
                episode_link_1080ps = request.form.getlist('episode_link_1080p[]')

                for i in range(len(episode_numbers)):
                    episode_links = []
                    if episode_link_480ps and i < len(episode_link_480ps) and episode_link_480ps[i]:
                        episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                    if episode_link_720ps and i < len(episode_link_720ps) and episode_link_720ps[i]:
                        episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                    if episode_link_1080ps and i < len(episode_link_1080ps) and episode_link_1080ps[i]:
                        episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                    
                    episodes_list.append({
                        "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                        "title": episode_titles[i] if i < len(episode_titles) and episode_titles else "",
                        "overview": episode_overviews[i] if i < len(episode_overviews) and episode_overviews else "",
                        "links": episode_links
                    })
                updated_data["episodes"] = episodes_list
                # Remove top-level 'links' if present for series
                if "links" in movie:
                    movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": ""}})
            
            # Update the movie in MongoDB
            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_data})
            print(f"Content '{title}' updated successfully!")
            return redirect(url_for('admin')) # Redirect back to admin list after update

        else: # GET request, display the form
            # Convert ObjectId to string for template
            movie['_id'] = str(movie['_id']) 
            return render_template_string(edit_html, movie=movie)

    except Exception as e:
        print(f"Error processing edit for movie ID {movie_id}: {e}")
        return "An error occurred during editing.", 500


@app.route('/delete_movie/<movie_id>')
@requires_auth # অথেন্টিকেশন ডেকোরেটর যোগ করা হয়েছে
def delete_movie(movie_id):
    try:
        # Delete the movie from MongoDB using its ObjectId
        result = movies.delete_one({"_id": ObjectId(movie_id)})
        if result.deleted_count == 1:
            print(f"Content with ID {movie_id} deleted successfully from MovieZone!")
        else:
            print(f"Content with ID {movie_id} not found in MovieZone database.")
    except Exception as e:
        print(f"Error deleting content with ID {movie_id}: {e}")
    
    return redirect(url_for('admin')) # Redirect back to the admin page


# --- NEW: Routes for full-page category lists (to be displayed in the new grid layout) ---

# This helper function renders the full-page list
def render_full_list(content_list, title):
    for m in content_list:
        m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=content_list, query=title, is_full_page_list=True)

@app.route('/trending_movies')
def trending_movies():
    trending_list = list(movies.find({"quality": "TRENDING"}).sort('_id', -1))
    return render_full_list(trending_list, "Trending on MovieZone")

@app.route('/movies_only')
def movies_only():
    movie_list = list(movies.find({"type": "movie", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    return render_full_list(movie_list, "All Movies")

@app.route('/webseries')
def webseries():
    series_list = list(movies.find({"type": "series", "quality": {"$ne": "TRENDING"}, "is_coming_soon": {"$ne": True}}).sort('_id', -1))
    return render_full_list(series_list, "All Web Series")

@app.route('/coming_soon')
def coming_soon():
    coming_soon_list = list(movies.find({"is_coming_soon": True}).sort('_id', -1))
    return render_full_list(coming_soon_list, "Coming Soon")

@app.route('/recently_added')
def recently_added_all():
    all_recent_content = list(movies.find().sort('_id', -1))
    return render_full_list(all_recent_content, "Recently Added")


if __name__ == "__main__":
    # Use a different port if 5000 is taken, e.g., 8080
    app.run(host='0.0.0.0', port=os.getenv("PORT", 5000), debug=True)
