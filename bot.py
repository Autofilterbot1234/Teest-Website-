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
# index_html টেমপ্লেট অপরিবর্তিত থাকবে, তাই এখানে এটি আর যুক্ত করছি না।
# আগের উত্তরের index_html কোডটি এখানে ব্যবহার করুন।
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
  
  .full-page-grid-container { padding: 100px 50px 50px 50px; }
  .full-page-grid-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 30px; }
  .full-page-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;
  }
  
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
  .nav-item.active i { color: var(--netflix-red); }

  @media (max-width: 768px) {
      body { padding-bottom: var(--nav-height); }
      .main-nav { padding: 10px 15px; }
      .hero-section { height: 60vh; }
      .hero-content { max-width: 90%; text-align: center; }
      .hero-title { font-size: 2.8rem; }
      .hero-overview { display: none; }
      .carousel-row { margin: 25px 0; }
      .carousel-header { margin: 0 15px 10px 15px; }
      .carousel-title { font-size: 1.2rem; }
      .carousel-content { padding: 0 15px; gap: 8px; }
      .movie-card { min-width: 130px; }
      .bottom-nav { display: flex; }
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
    </a>
  {% endmacro %}

  {% if is_full_page_list %}
    <div class="full-page-grid-container">
      <h2 class="full-page-grid-title">{{ query }}</h2>
      <div class="full-page-grid">
        {% for m in movies %}{{ render_movie_card(m) }}{% endfor %}
      </div>
    </div>
  {% else %}
    {% if recently_added %}
      <div class="hero-section">
        {% for movie in recently_added %}
          <div class="hero-slide {% if loop.first %}active{% endif %}" style="background-image: url('{{ movie.poster or '' }}');">
            <div class="hero-content">
              <h1 class="hero-title">{{ movie.title }}</h1>
              <p class="hero-overview">{{ movie.overview }}</p>
              <div class="hero-buttons">
                 <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-primary"><i class="fas fa-play"></i> Watch Now</a>
                 <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="btn btn-secondary"><i class="fas fa-info-circle"></i> More Info</a>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
    {% endif %}

    {% macro render_carousel(title, movies_list, endpoint) %}
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
    {% endmacro %}
    
    {{ render_carousel('Trending Now', trending_movies, 'trending_movies') }}
    {{ render_carousel('Latest Movies', latest_movies, 'movies_only') }}
    {{ render_carousel('Web Series', latest_series, 'webseries') }}

  {% endif %}
</main>
<nav class="bottom-nav">
  <a href="{{ url_for('home') }}" class="nav-item active"><i class="fas fa-home"></i><span>Home</span></a>
  <a href="{{ url_for('movies_only') }}" class="nav-item"><i class="fas fa-film"></i><span>Movies</span></a>
  <a href="{{ url_for('webseries') }}" class="nav-item"><i class="fas fa-tv"></i><span>Series</span></a>
  <a href="{{ url_for('contact') }}" class="nav-item"><i class="fas fa-envelope"></i><span>Request</span></a>
</nav>
<script>
    const nav = document.querySelector('.main-nav');
    window.addEventListener('scroll', () => { window.scrollY > 50 ? nav.classList.add('scrolled') : nav.classList.remove('scrolled'); });
    document.querySelectorAll('.carousel-arrow').forEach(button => {
        button.addEventListener('click', () => {
            const carousel = button.closest('.carousel-wrapper').querySelector('.carousel-content');
            carousel.scrollLeft += button.classList.contains('next') ? (carousel.clientWidth * 0.8) : -(carousel.clientWidth * 0.8);
        });
    });
    const slides = document.querySelectorAll('.hero-slide');
    if (slides.length > 1) {
        let currentSlide = 0;
        setInterval(() => {
            currentSlide = (currentSlide + 1) % slides.length;
            slides.forEach((s, i) => s.classList.toggle('active', i === currentSlide));
        }, 5000);
    }
</script>
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
  .back-button { color: var(--text-light); font-size: 1.2rem; text-decoration: none; }
  .detail-content-wrapper { display: flex; gap: 40px; max-width: 1200px; margin: 120px auto 50px auto; padding: 0 50px; }
  .detail-poster { width: 300px; height: 450px; flex-shrink: 0; border-radius: 8px; }
  .detail-info h1 { font-family: 'Bebas Neue', sans-serif; font-size: 4.5rem; margin-bottom: 20px; }
  .detail-overview { line-height: 1.6; margin-bottom: 30px; }
  .watch-now-btn { background-color: var(--netflix-red); color: white; padding: 15px 30px; font-size: 1.2rem; border: none; border-radius: 5px; cursor: pointer; }
  
  /* NEW: Custom Player Modal Styles */
  .modal-overlay {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.9); z-index: 1000; display: flex;
    justify-content: center; align-items: center; backdrop-filter: blur(5px);
  }
  .modal-container { width: 90%; max-width: 1200px; background: #000; border-radius: 8px; box-shadow: 0 0 30px rgba(0,0,0,0.5); }
  #custom-video-player { width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 8px 8px 0 0; }
  .player-controls { padding: 15px 20px; background: #181818; border-radius: 0 0 8px 8px; }
  .controls-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  #modal-title { font-size: 1.5rem; font-weight: 700; }
  .close-modal-btn { background: none; border: none; color: white; font-size: 2rem; cursor: pointer; }
  .controls-bottom { display: flex; align-items: center; gap: 20px; }
  .info-group { display: flex; align-items: center; gap: 15px; font-size: 0.9rem; color: var(--text-dark); }
  .info-group i { color: var(--text-light); }
  .like-btn { background: none; border: none; color: white; cursor: pointer; font-size: 1.5rem; }
  .like-btn.liked { color: #00aaff; }

  @media (max-width: 768px) {
    .detail-content-wrapper { flex-direction: column; align-items: center; text-align: center; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>
<header class="detail-header"><a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back to Home</a></header>
{% if movie %}
<div class="detail-content-wrapper">
  <img class="detail-poster" src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}">
  <div class="detail-info">
    <h1>{{ movie.title }}</h1>
    <p class="detail-overview">{{ movie.overview }}</p>
    {% if movie.watch_link %}
    <button class="watch-now-btn" onclick="openPlayerModal('{{ movie._id }}', '{{ movie.title }}', '{{ movie.watch_link }}')">
        <i class="fas fa-play"></i> Watch Now
    </button>
    {% else %}
    <p>No watchable link available.</p>
    {% endif %}
  </div>
</div>
{% else %}
  <div style="text-align:center; padding-top:150px;"><h2>Content not found.</h2></div>
{% endif %}

<!-- Custom Player Modal -->
<div id="playerModal" class="modal-overlay" style="display: none;">
    <div class="modal-container">
        <video id="custom-video-player" controls controlsList="nodownload"></video>
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

// Function to open the player
function openPlayerModal(movieId, title, videoUrl) {
    currentMovieId = movieId;
    modalTitle.textContent = title;
    videoPlayer.src = videoUrl;
    playerModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    viewTriggered = false; // Reset view trigger
    updateInteractionCounts();
}

// Function to close the player
function closePlayerModal() {
    playerModal.style.display = 'none';
    videoPlayer.pause();
    videoPlayer.src = ""; // Detach source to stop background loading
    document.body.style.overflow = 'auto';
}

// Event Listeners
closeBtn.addEventListener('click', closePlayerModal);
playerModal.addEventListener('click', (e) => {
    if (e.target === playerModal) {
        closePlayerModal();
    }
});

videoPlayer.addEventListener('play', () => {
    if (!viewTriggered) {
        fetch(`/api/movie/${currentMovieId}/view`, { method: 'POST' });
        viewTriggered = true;
        // Optimistically update view count on frontend
        const currentViews = parseInt(viewCountSpan.textContent) || 0;
        viewCountSpan.textContent = `${currentViews + 1} Views`;
    }
});

likeBtn.addEventListener('click', async () => {
    if (likeBtn.classList.contains('liked')) return;
    try {
        const response = await fetch(`/api/movie/${currentMovieId}/like`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            updateInteractionCounts(); // Re-fetch counts from server
            localStorage.setItem(`liked_${currentMovieId}`, 'true');
        }
    } catch (error) {
        console.error('Like failed:', error);
    }
});

// Function to update likes and views from server
async function updateInteractionCounts() {
    try {
        const response = await fetch(`/api/movie/${currentMovieId}/interactions`);
        const data = await response.json();
        if (data.success) {
            likeCountSpan.textContent = `${data.likes} Likes`;
            viewCountSpan.textContent = `${data.views} Views`;
            // Update like button state
            if (localStorage.getItem(`liked_${currentMovieId}`) === 'true') {
                likeBtn.classList.add('liked');
                likeBtn.querySelector('i').className = 'fas fa-thumbs-up';
            } else {
                likeBtn.classList.remove('liked');
                likeBtn.querySelector('i').className = 'far fa-thumbs-up';
            }
        }
    } catch (error) {
        console.error('Could not fetch interactions', error);
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
    h2 { font-size: 2.5rem; } h3 { font-size: 1.5rem; }
    form { max-width: 800px; margin: 20px auto; background: var(--dark-gray); padding: 25px; border-radius: 8px;}
    label { display: block; margin-bottom: 8px; font-weight: bold; }
    input[type="text"], input[type="url"], textarea { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid var(--light-gray); background: var(--light-gray); color: var(--text-light); }
    button[type="submit"] { background: var(--netflix-red); color: white; font-weight: 700; cursor: pointer; border: none; padding: 12px 25px; border-radius: 4px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--light-gray); }
    .action-buttons a { padding: 6px 12px; border-radius: 4px; text-decoration: none; color: white; }
    .edit-btn { background: #007bff; } .delete-btn { background: #dc3545; }
  </style>
</head>
<body>
  <h2>Add New Content</h2>
  <form method="post" action="{{ url_for('admin') }}">
    <p><label>Title:</label><input type="text" name="title" required></p>
    <!-- MODIFIED: Changed label to specify direct link -->
    <p><label>Direct Video Link (.mp4 URL):</label><input type="url" name="watch_link" required></p>
    <p><label>Poster URL:</label><input type="url" name="poster_url"></p>
    <p><label>Overview:</label><textarea name="overview"></textarea></p>
    <button type="submit">Add Content</button>
  </form>

  <h2>Manage Content</h2>
  <table>
    <thead><tr><th>Title</th><th>Views</th><th>Likes</th><th>Actions</th></tr></thead>
    <tbody>
      {% for movie in all_content %}
      <tr>
        <td>{{ movie.title }}</td>
        <td>{{ movie.views or 0 }}</td>
        <td>{{ movie.likes or 0 }}</td>
        <td class="action-buttons">
            <a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a>
            <a href="{{ url_for('delete_movie', movie_id=movie._id) }}" class="delete-btn" onclick="return confirm('Are you sure?')">Delete</a>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""

# --- START OF edit_html TEMPLATE (MODIFIED FOR DIRECT LINK) ---
edit_html = """
<!DOCTYPE html>
<html>
<head><title>Edit Content</title>
<style>
    body { font-family: sans-serif; background: #141414; color: white; padding: 20px; }
    form { max-width: 600px; margin: auto; background: #222; padding: 20px; border-radius: 8px; }
    input, textarea { width: 100%; padding: 10px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: #E50914; color: white; border: none; padding: 10px 20px; cursor: pointer; }
</style>
</head>
<body>
  <h2>Edit: {{ movie.title }}</h2>
  <form method="post">
    <p><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required></p>
    <!-- MODIFIED: Changed label to specify direct link -->
    <p><label>Direct Video Link (.mp4 URL):</label><input type="url" name="watch_link" value="{{ movie.watch_link }}" required></p>
    <p><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster or '' }}"></p>
    <p><label>Overview:</label><textarea name="overview">{{ movie.overview or '' }}</textarea></p>
    <button type="submit">Update Content</button>
  </form>
</body>
</html>
"""

# --- Flask Routes (Fully Updated) ---

def process_movie_list(movie_list):
    for item in movie_list:
        item['_id'] = str(item['_id'])
    return movie_list

@app.route('/')
def home():
    # Simplified home page logic for this example
    movies_list = list(movies.find().sort('_id', -1))
    return render_template_string(index_html, trending_movies=process_movie_list(movies_list), latest_movies=process_movie_list(movies_list), latest_series=process_movie_list(movies_list))

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found", 404
        movie['_id'] = str(movie['_id'])
        return render_template_string(detail_html, movie=movie)
    except Exception:
        return "Invalid ID", 400

# --- NEW/MODIFIED API Endpoints ---
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
        # Simplified for direct link
        movies.insert_one({
            "title": request.form.get("title"),
            "watch_link": request.form.get("watch_link"),
            "poster": request.form.get("poster_url", "").strip(),
            "overview": request.form.get("overview", "").strip(),
            "likes": 0,
            "views": 0
        })
        return redirect(url_for('admin'))
    
    all_content = process_movie_list(list(movies.find().sort('_id', -1)))
    return render_template_string(admin_html, all_content=all_content)

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    if request.method == "POST":
        update_data = {
            "title": request.form.get("title"),
            "watch_link": request.form.get("watch_link"),
            "poster": request.form.get("poster_url", "").strip(),
            "overview": request.form.get("overview", "").strip(),
        }
        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        return redirect(url_for('admin'))
    
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>')
@requires_auth
def delete_movie(movie_id):
    movies.delete_one({"_id": ObjectId(movie_id)})
    return redirect(url_for('admin'))

# --- Dummy routes from index.html for it to run without errors ---
@app.route('/movies_only')
def movies_only(): return redirect(url_for('home'))
@app.route('/webseries')
def webseries(): return redirect(url_for('home'))
@app.route('/contact')
def contact(): return "Contact page not implemented in this version."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
