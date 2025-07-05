# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests
import os
from functools import wraps
from dotenv import load_dotenv
from collections import defaultdict

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
    print("Warning: TMDB_API_KEY is not set. Metadata fetching will be disabled.")

# Database connection
try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)


# --- START OF index_html TEMPLATE (NEW DESIGN) ---
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MovieDokan - Your Entertainment Hub</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@8/swiper-bundle.min.css"/>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
        :root {
            --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010;
            --text-light: #f5f5f5; --text-grey: #a0a0a0; --card-bg: #181818;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Poppins', sans-serif; background-color: var(--body-bg); color: var(--text-light); }
        a { text-decoration: none; color: inherit; }
        .container { max-width: 1400px; margin: 0 auto; padding: 0 20px; }
        
        /* Header */
        .main-header { position: fixed; top: 0; left: 0; width: 100%; z-index: 1000; padding: 20px 0; background: linear-gradient(to bottom, rgba(0,0,0,0.7), transparent); transition: background-color 0.3s; }
        .main-header.scrolled { background-color: #101010; }
        .header-content { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 2rem; font-weight: 700; color: var(--primary-color); }
        .search-box { position: relative; }
        .search-input { background: rgba(0,0,0,0.5); border: 1px solid #333; color: white; padding: 8px 15px; border-radius: 20px; width: 250px; transition: all 0.3s; }
        .search-input:focus { background: white; color: black; }

        /* Hero Slider */
        .hero-slider { height: 85vh; width: 100%; position: relative; }
        .swiper-slide { position: relative; color: white; }
        .hero-slide-bg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; filter: brightness(0.6); }
        .hero-slide-bg::after { content:''; position: absolute; inset: 0; background: linear-gradient(to top, var(--body-bg) 5%, transparent 40%); }
        .slide-content { position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; justify-content: center; max-width: 50%; padding-left: 50px; }
        .slide-title { font-size: 4rem; font-weight: 700; line-height: 1.1; margin-bottom: 1rem; }
        .slide-meta { display: flex; gap: 15px; align-items: center; margin-bottom: 1rem; }
        .slide-meta .rating { color: #ffc107; font-weight: 600; }
        .slide-overview { font-size: 1rem; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 1.5rem; }
        .slide-btn { background-color: var(--primary-color); padding: 12px 25px; border-radius: 5px; font-weight: 600; transition: transform 0.2s; display: inline-block; }
        .slide-btn:hover { transform: scale(1.05); }
        .swiper-pagination-bullet-active { background-color: var(--primary-color); }
        
        /* Content Section */
        .content-section { padding: 40px 0; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .section-title { font-size: 1.8rem; font-weight: 600; }
        .see-all-link { color: var(--text-grey); font-weight: 500; }
        .see-all-link:hover { color: var(--primary-color); }

        .content-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
        .movie-card { position: relative; border-radius: 8px; overflow: hidden; transition: transform 0.3s; background-color: var(--card-bg); }
        .movie-card:hover { transform: translateY(-10px); }
        .card-poster { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.9) 20%, transparent 60%); display: flex; flex-direction: column; justify-content: flex-end; padding: 15px; opacity: 0; transition: opacity 0.3s; }
        .movie-card:hover .card-overlay { opacity: 1; }
        .card-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 5px; }
        .card-meta { font-size: 0.8rem; color: var(--text-grey); display: flex; gap: 10px; }
        .card-meta .rating { color: #ffc107; }

        /* Full Page Grid */
        .full-page-container { padding-top: 120px; }

        @media (max-width: 768px) {
            .slide-title { font-size: 2.5rem; }
            .slide-content { max-width: 80%; padding-left: 20px; }
            .search-input { width: 180px; }
            .content-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
        }
    </style>
</head>
<body>

<header class="main-header">
    <div class="container header-content">
        <a href="{{ url_for('home') }}" class="logo">MovieDokan</a>
        <div class="search-box">
            <form method="GET" action="/">
                <input type="search" name="q" class="search-input" placeholder="Search movies, series..." value="{{ query|default('') }}">
            </form>
        </div>
    </div>
</header>

<main>
    {% if is_full_page_list %}
        <div class="container full-page-container">
            <div class="content-section">
                <div class="section-header">
                    <h2 class="section-title">{{ query }}</h2>
                </div>
                {% if movies|length > 0 %}
                <div class="content-grid">
                    {% for movie in movies %}
                    <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="movie-card">
                        <img src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}" class="card-poster">
                        <div class="card-overlay">
                            <h3 class="card-title">{{ movie.title }}</h3>
                            <div class="card-meta">
                                {% if movie.vote_average %}<span class="rating"><i class="fas fa-star"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
                                {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
                {% else %}
                <p>No content found.</p>
                {% endif %}
            </div>
        </div>
    {% else %}
        <!-- Hero Slider -->
        <div class="hero-slider swiper">
            <div class="swiper-wrapper">
                {% for movie in featured_movies %}
                <div class="swiper-slide">
                    <img src="{{ movie.poster or '' }}" class="hero-slide-bg" alt="{{ movie.title }}">
                    <div class="slide-content">
                        <h1 class="slide-title">{{ movie.title }}</h1>
                        <div class="slide-meta">
                            {% if movie.vote_average %}<span class="rating"><i class="fas fa-star"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
                            {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
                            {% if movie.genres %}<span>{{ movie.genres|first }}</span>{% endif %}
                        </div>
                        <p class="slide-overview">{{ movie.overview }}</p>
                        <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="slide-btn">View Details <i class="fas fa-arrow-right"></i></a>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="swiper-pagination"></div>
        </div>

        <div class="container">
            <!-- Latest Movies Section -->
            {% if latest_movies %}
            <div class="content-section">
                <div class="section-header">
                    <h2 class="section-title">Latest Movies</h2>
                    <a href="{{ url_for('movies_only') }}" class="see-all-link">See All</a>
                </div>
                <div class="content-grid">
                    {% for movie in latest_movies %}
                    <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="movie-card">
                        <img src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}" class="card-poster">
                        <div class="card-overlay">
                            <h3 class="card-title">{{ movie.title }}</h3>
                            <div class="card-meta">
                                {% if movie.vote_average %}<span class="rating"><i class="fas fa-star"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
                                {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Latest Series Section -->
            {% if latest_series %}
            <div class="content-section">
                <div class="section-header">
                    <h2 class="section-title">Latest Series</h2>
                    <a href="{{ url_for('webseries') }}" class="see-all-link">See All</a>
                </div>
                <div class="content-grid">
                    {% for movie in latest_series %}
                    <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="movie-card">
                        <img src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}" class="card-poster">
                        <div class="card-overlay">
                            <h3 class="card-title">{{ movie.title }}</h3>
                             <div class="card-meta">
                                {% if movie.vote_average %}<span class="rating"><i class="fas fa-star"></i> {{ "%.1f"|format(movie.vote_average) }}</span>{% endif %}
                                {% if movie.release_date %}<span>{{ movie.release_date.split('-')[0] }}</span>{% endif %}
                            </div>
                        </div>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>
    {% endif %}
</main>

<script src="https://cdn.jsdelivr.net/npm/swiper@8/swiper-bundle.min.js"></script>
<script>
    const header = document.querySelector('.main-header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });

    const swiper = new Swiper('.hero-slider', {
        loop: true,
        autoplay: {
            delay: 5000,
            disableOnInteraction: false,
        },
        pagination: {
            el: '.swiper-pagination',
            clickable: true,
        },
    });
</script>

</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# --- START OF detail_html TEMPLATE (NEW DESIGN) ---
# detail_html, watch_html, admin_html, edit_html এবং macros_html আগের মতোই থাকবে।
# আমি কোড সংক্ষিপ্ত রাখার জন্য এগুলো আবার পেস্ট করছি না। আপনি আগের উত্তর থেকে এগুলো নিতে পারেন।
# The detail_html, watch_html, admin_html, edit_html, and macros_html templates remain the same.
# I'm not re-pasting them to keep the code concise. You can use them from the previous response.

detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieZone</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
  :root {
      --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010;
      --text-light: #f5f5f5; --text-grey: #a0a0a0; --card-bg: #181818;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Poppins', sans-serif; background: var(--body-bg); color: var(--text-light); }
  .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
  main { padding-top: 100px; }
  
  /* Detail Hero */
  .detail-hero { display: flex; gap: 40px; }
  .detail-poster { width: 300px; height: 450px; flex-shrink: 0; border-radius: 12px; object-fit: cover; }
  .detail-info { flex-grow: 1; }
  .detail-title { font-size: 3rem; font-weight: 700; line-height: 1.2; margin-bottom: 15px; }
  .detail-meta { display: flex; flex-wrap: wrap; gap: 20px; align-items: center; margin-bottom: 20px; color: var(--text-grey); }
  .meta-item { display: flex; align-items: center; gap: 8px; }
  .meta-item .fa-star { color: #ffc107; }
  .genres span { background: #333; padding: 5px 10px; border-radius: 15px; font-size: 0.9rem; }
  .detail-overview { font-size: 1rem; line-height: 1.7; margin-bottom: 30px; }
  .watch-btn { background-color: var(--primary-color); padding: 15px 30px; border-radius: 8px; font-weight: 600; transition: transform 0.2s; display: inline-flex; align-items: center; gap: 10px; font-size: 1.1rem; }
  .watch-btn:hover { transform: scale(1.05); }

  /* Content Section */
  .content-section { margin-top: 50px; }
  .section-title { font-size: 1.8rem; font-weight: 600; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid var(--primary-color); display: inline-block; }
  
  /* Episodes/Downloads */
  .season-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
  .season-tab { background: var(--card-bg); padding: 10px 20px; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
  .season-tab.active { background: var(--primary-color); font-weight: 600; }
  .episode-list { display: none; }
  .episode-list.active { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
  .episode-item { background: var(--card-bg); padding: 15px; border-radius: 8px; border-left: 3px solid #444; transition: border-color 0.2s; }
  .episode-item:hover { border-color: var(--primary-color); }
  .episode-title { font-size: 1rem; font-weight: 500; }
  .episode-actions { margin-top: 10px; }
  .ep-btn { background: #444; padding: 8px 15px; border-radius: 5px; font-size: 0.9rem; transition: background-color 0.2s; display: inline-block; margin: 5px 5px 5px 0; }
  .ep-btn.watch { background: var(--primary-color); }

  .download-links a { margin: 5px; }

  @media (max-width: 768px) {
    .detail-hero { flex-direction: column; text-align: center; }
    .detail-poster { width: 60%; max-width: 250px; height: auto; margin-bottom: 20px; }
    .detail-meta { justify-content: center; }
    .episode-list { grid-template-columns: 1fr; }
  }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css">
</head>
<body>

<header class="main-header" style="background-color: #101010;">
    <div class="container" style="display:flex; justify-content: space-between; align-items:center;">
        <a href="{{ url_for('home') }}" class="logo">MovieDokan</a>
        <a href="{{ url_for('home') }}" style="font-weight: 500;"><i class="fas fa-arrow-left"></i> Back to Home</a>
    </div>
</header>

<main>
<div class="container">
    {% if movie %}
    <div class="detail-hero">
        <img src="{{ movie.poster or 'https://via.placeholder.com/400x600.png?text=No+Image' }}" alt="{{ movie.title }}" class="detail-poster">
        <div class="detail-info">
            <h1 class="detail-title">{{ movie.title }}</h1>
            <div class="detail-meta">
                {% if movie.vote_average %}<div class="meta-item"><i class="fas fa-star"></i> {{ "%.1f"|format(movie.vote_average) }}</div>{% endif %}
                {% if movie.release_date %}<div class="meta-item"><i class="fas fa-calendar"></i> {{ movie.release_date.split('-')[0] }}</div>{% endif %}
            </div>
            {% if movie.genres %}
            <div class="detail-meta genres">
                {% for genre in movie.genres %}<span>{{ genre }}</span>{% endfor %}
            </div>
            {% endif %}
            <p class="detail-overview">{{ movie.overview }}</p>
            
            {% if not movie.is_coming_soon %}
                {% if movie.type == 'movie' and movie.watch_link %}
                <a href="{{ url_for('watch_movie', movie_id=movie._id) }}" class="watch-btn"><i class="fas fa-play"></i> Watch Movie</a>
                {% elif movie.type == 'series' and seasons and seasons[seasons.keys()|sort|first] and seasons[seasons.keys()|sort|first][0].watch_link %}
                <a href="{{ url_for('watch_movie', movie_id=movie._id, s=seasons.keys()|sort|first, ep=seasons[seasons.keys()|sort|first]|sort(attribute='episode_number')|first.episode_number) }}" class="watch-btn"><i class="fas fa-play"></i> Start Watching</a>
                {% endif %}
            {% endif %}
        </div>
    </div>

    <div class="content-section">
    {% if movie.is_coming_soon %}
        <h2 class="section-title">Coming Soon</h2>
        <p>This content is not yet available.</p>
    {% elif movie.type == 'movie' %}
        <h2 class="section-title">Downloads & Trailer</h2>
        <div class="download-links">
        {% for link in movie.links %}
            <a href="{{ link.url }}" class="ep-btn" target="_blank"><i class="fas fa-download"></i> {{ link.quality }}</a>
        {% endfor %}
        </div>
    {% elif movie.type == 'series' and seasons %}
        <h2 class="section-title">Seasons & Episodes</h2>
        <div class="season-tabs">
            {% for season_num in seasons.keys()|sort %}
            <div class="season-tab {% if loop.first %}active{% endif %}" data-season="{{ season_num }}">Season {{ season_num }}</div>
            {% endfor %}
        </div>
        {% for season_num, episodes in seasons.items()|sort %}
        <div class="episode-list {% if loop.first %}active{% endif %}" id="season-{{ season_num }}">
            {% for episode in episodes|sort(attribute='episode_number') %}
            <div class="episode-item">
                <h3 class="episode-title">E{{ episode.episode_number }}: {{ episode.title }}</h3>
                <div class="episode-actions">
                    {% if episode.watch_link %}<a href="{{ url_for('watch_movie', movie_id=movie._id, s=episode.season_number, ep=episode.episode_number) }}" class="ep-btn watch"><i class="fas fa-play"></i> Watch</a>{% endif %}
                    {% for link in episode.links %}<a href="{{ link.url }}" class="ep-btn" target="_blank"><i class="fas fa-download"></i> {{ link.quality }}</a>{% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    {% endif %}
    </div>
    {% else %}
    <p>Content not found.</p>
    {% endif %}
</div>
</main>
<script>
document.querySelectorAll('.season-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelector('.season-tab.active').classList.remove('active');
        document.querySelector('.episode-list.active').classList.remove('active');
        tab.classList.add('active');
        document.getElementById(`season-${tab.dataset.season}`).classList.add('active');
    });
});
</script>
</body>
</html>
"""
watch_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Watching: {{ title }}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
    :root { --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010; --card-bg: #181818; }
    body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; background-color: #000; font-family: 'Poppins', sans-serif; color: #fff; }
    .watch-wrapper { display: flex; height: 100vh; }
    .player-container { flex-grow: 1; height: 100%; position: relative; background-color: #000; }
    .player-container iframe { width: 100%; height: 100%; border: 0; }
    .sidebar { width: 350px; background-color: var(--body-bg); height: 100%; overflow-y: auto; flex-shrink: 0; border-left: 1px solid #222; }
    .sidebar-header { padding: 15px; background-color: var(--card-bg); }
    .series-title { font-size: 1.2rem; font-weight: 600; margin: 0 0 10px 0; }
    .season-selector { width: 100%; background-color: #333; color: #fff; border: 1px solid #444; padding: 10px; border-radius: 4px; font-size: 1rem; }
    .episode-list-ul { list-style: none; padding: 0; margin: 0; }
    .episode-list-item a { display: block; padding: 15px; text-decoration: none; color: #ccc; border-bottom: 1px solid #222; transition: all 0.2s; }
    .episode-list-item a:hover { background-color: #222; color: #fff; }
    .episode-list-item.active a { background-color: var(--primary-color); color: #fff; font-weight: 600; }
    .ep-num { font-weight: 700; margin-right: 8px; color: #888; }
    .episode-list-item.active .ep-num { color: #fff; }
    
    @media (max-width: 768px) {
        .watch-wrapper { flex-direction: column; }
        .sidebar { width: 100%; height: 40vh; }
        .player-container { height: 60vh; }
    }
</style>
</head>
<body>
    <div class="watch-wrapper">
        <div class="player-container">
            <iframe id="videoPlayer" src="{{ current_episode.watch_link }}" allowfullscreen allowtransparency allow="autoplay" scrolling="no" frameborder="0"></iframe>
        </div>
        {% if movie.type == 'series' %}
        <div class="sidebar">
            <div class="sidebar-header">
                <h3 class="series-title">{{ movie.title }}</h3>
                <select id="seasonSelector" class="season-selector">
                    {% for season_num in seasons.keys()|sort %}
                    <option value="{{ season_num }}" {% if season_num == current_episode.season_number %}selected{% endif %}>Season {{ season_num }}</option>
                    {% endfor %}
                </select>
            </div>
            {% for season_num, episodes in seasons.items()|sort %}
            <ul class="episode-list-ul" id="season-{{ season_num }}-list" style="display: {% if season_num == current_episode.season_number %}block{% else %}none{% endif %};">
                {% for ep in episodes|sort(attribute='episode_number') %}
                <li class="episode-list-item {% if ep.season_number == current_episode.season_number and ep.episode_number == current_episode.episode_number %}active{% endif %}">
                    <a href="#" data-watch-link="{{ ep.watch_link }}" data-title="{{ movie.title }} - S{{ep.season_number}} E{{ep.episode_number}}">
                        <span class="ep-num">E{{ ep.episode_number }}</span>{{ ep.title }}
                    </a>
                </li>
                {% endfor %}
            </ul>
            {% endfor %}
        </div>
        {% endif %}
    </div>

<script>
    const player = document.getElementById('videoPlayer');
    const seasonSelector = document.getElementById('seasonSelector');
    const episodeLinks = document.querySelectorAll('.episode-list-item a');
    
    function switchEpisode(link, title, clickedElement) {
        if (player && link) {
            player.src = link;
            document.title = "Watching: " + title;
            document.querySelectorAll('.episode-list-item').forEach(el => el.classList.remove('active'));
            clickedElement.parentElement.classList.add('active');
        }
    }
    
    if (seasonSelector) {
        seasonSelector.addEventListener('change', function() {
            document.querySelectorAll('.episode-list-ul').forEach(list => list.style.display = 'none');
            document.getElementById(`season-${this.value}-list`).style.display = 'block';
        });
    }
    
    episodeLinks.forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            switchEpisode(this.dataset.watchLink, this.dataset.title, this);
        });
    });
</script>
</body>
</html>
"""
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieDokan</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010; --card-bg: #181818; }
    body { font-family: 'Poppins', sans-serif; background-color: var(--body-bg); color: #f5f5f5; padding: 20px; }
    h2, h3 { color: var(--primary-color); font-weight: 600; }
    form { max-width: 800px; margin: 20px auto; background: var(--card-bg); padding: 25px; border-radius: 8px; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 8px; font-weight: 500; }
    input, textarea, select { width: 100%; padding: 10px; border-radius: 4px; border: 1px solid #333; background: #222; color: #f5f5f5; box-sizing: border-box; }
    input[type="checkbox"] { width: auto; margin-right: 10px; }
    button, .btn { background: var(--primary-color); color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: 600; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
    .episode-item { border: 1px solid #333; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
  </style>
</head>
<body>
  <h2>Add New Content</h2>
  <form method="post">
    <div class="form-group"><label for="title">Title:</label><input type="text" name="title" required /></div>
    <div class="form-group"><label for="content_type">Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie">Movie</option><option value="series">Series</option></select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Watch Link (Embed):</label><input type="url" name="watch_link" /></div>
        <hr><p>OR Download Links</p>
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" /></div>
        <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
      <h3>Episodes</h3><div id="episodes_container"></div>
      <button type="button" onclick="addEpisodeField()" class="btn">Add Episode</button>
    </div>
    <hr>
    <h3>Manual Details (Optional)</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview"></textarea></div>
    <div class="form-group"><label>Release Date (YYYY-MM-DD):</label><input type="text" name="release_date" /></div>
    <div class="form-group"><label>Genres (Comma-separated):</label><input type="text" name="genres" /></div>
    <hr>
    <div class="form-group"><input type="checkbox" name="is_featured" value="true"><label style="display:inline;">Add to Homepage Slider?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true"><label style="display:inline;">Is Coming Soon?</label></div>
    <button type="submit">Add Content</button>
  </form>

  <h2>Manage Content</h2>
  <table><thead><tr><th>Title</th><th>Type</th><th>Actions</th></tr></thead>
  <tbody>
    {% for m in movies %}
    <tr>
      <td>{{ m.title }}</td><td>{{ m.type | title }}</td>
      <td>
        <a href="{{ url_for('edit_movie', movie_id=m._id) }}" class="btn" style="background:#007bff;">Edit</a>
        <form action="{{ url_for('delete_movie', movie_id=m._id) }}" method="POST" style="display:inline;" onsubmit="return confirm('Sure?');"><button type="submit" class="btn" style="background:#dc3545;">Delete</button></form>
      </td>
    </tr>
    {% endfor %}
  </tbody></table>

  <script>
    function toggleEpisodeFields() {
        var isSeries = document.getElementById('content_type').value === 'series';
        document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none';
        document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block';
    }
    let epCounter = 0;
    function addEpisodeField() {
        epCounter++;
        const container = document.getElementById('episodes_container');
        const div = document.createElement('div');
        div.className = 'episode-item';
        div.innerHTML = rf'''
            <input type="hidden" name="episode_indices" value="${epCounter}">
            <div style="display:flex;gap:10px;">
              <div class="form-group" style="flex:1;"><label>Season:</label><input type="number" name="season_number_${epCounter}" value="1" required /></div>
              <div class="form-group" style="flex:1;"><label>Episode:</label><input type="number" name="episode_number_${epCounter}" required /></div>
            </div>
            <div class="form-group"><label>Title:</label><input type="text" name="episode_title_${epCounter}" required /></div>
            <div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link_${epCounter}" /></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p_${epCounter}" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p_${epCounter}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="btn" style="background:#6c757d;">Remove</button>
        ''';
        container.appendChild(div);
    }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieDokan</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010; --card-bg: #181818; }
    body { font-family: 'Poppins', sans-serif; background-color: var(--body-bg); color: #f5f5f5; padding: 20px; }
    h2, h3 { color: var(--primary-color); font-weight: 600; }
    form { max-width: 800px; margin: 20px auto; background: var(--card-bg); padding: 25px; border-radius: 8px; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 8px; font-weight: 500; }
    input, textarea, select { width: 100%; padding: 10px; border-radius: 4px; border: 1px solid #333; background: #222; color: #f5f5f5; box-sizing: border-box; }
    input[type="checkbox"] { width: auto; margin-right: 10px; }
    button, .btn { background: var(--primary-color); color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: 600; }
    .episode-item { border: 1px solid #333; padding: 15px; margin-bottom: 15px; border-radius: 5px; }
  </style>
</head>
<body>
  <a href="{{ url_for('admin') }}">← Back to Admin</a>
  <h2>Edit: {{ movie.title }}</h2>
  <form method="post">
    <div class="form-group"><label>Title:</label><input type="text" name="title" value="{{ movie.title }}" required /></div>
    <div class="form-group"><label>Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()">
        <option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option>
        <option value="series" {% if movie.type == 'series' %}selected{% endif %}>Series</option>
    </select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Watch Link:</label><input type="url" name="watch_link" value="{{ movie.watch_link or '' }}" /></div>
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" value="{% for l in movie.links %}{% if l.quality == '480p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
        <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" value="{% for l in movie.links %}{% if l.quality == '720p' %}{{ l.url }}{% endif %}{% endfor %}" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
        <h3>Episodes</h3><div id="episodes_container">
        {% if movie.type == 'series' and movie.episodes %}{% for ep in movie.episodes|sort(attribute='episode_number')|sort(attribute='season_number') %}
        <div class="episode-item">
            <input type="hidden" name="episode_indices" value="{{ loop.index }}">
            <div style="display:flex;gap:10px;">
              <div class="form-group" style="flex:1;"><label>Season:</label><input type="number" name="season_number_{{ loop.index }}" value="{{ ep.season_number }}" required /></div>
              <div class="form-group" style="flex:1;"><label>Episode:</label><input type="number" name="episode_number_{{ loop.index }}" value="{{ ep.episode_number }}" required /></div>
            </div>
            <div class="form-group"><label>Title:</label><input type="text" name="episode_title_{{ loop.index }}" value="{{ ep.title }}" required /></div>
            <div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link_{{ loop.index }}" value="{{ ep.watch_link or '' }}" /></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p_{{ loop.index }}" value="{% for l in ep.links %}{% if l.quality=='480p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p_{{ loop.index }}" value="{% for l in ep.links %}{% if l.quality=='720p'%}{{l.url}}{%endif%}{%endfor%}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="btn" style="background:#6c757d;">Remove</button>
        </div>
        {% endfor %}{% endif %}
        </div>
        <button type="button" onclick="addEpisodeField()" class="btn">Add Episode</button>
    </div>
    <hr>
    <h3>Manual Details</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster or '' }}" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview">{{ movie.overview or '' }}</textarea></div>
    <div class="form-group"><label>Release Date:</label><input type="text" name="release_date" value="{{ movie.release_date or '' }}" /></div>
    <div class="form-group"><label>Genres:</label><input type="text" name="genres" value="{{ movie.genres|join(', ') if movie.genres else '' }}" /></div>
    <hr>
    <div class="form-group"><input type="checkbox" name="is_featured" value="true" {% if movie.is_featured %}checked{% endif %}><label style="display:inline;">Add to Homepage Slider?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}><label style="display:inline;">Is Coming Soon?</label></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() {
        var isSeries = document.getElementById('content_type').value === 'series';
        document.getElementById('episode_fields').style.display = isSeries ? 'block' : 'none';
        document.getElementById('movie_fields').style.display = isSeries ? 'none' : 'block';
    }
    let epCounter = {{ (movie.episodes|length) if movie.episodes else 0 }};
    function addEpisodeField() {
        epCounter++;
        const container = document.getElementById('episodes_container');
        const div = document.createElement('div');
        div.className = 'episode-item';
        div.innerHTML = rf'''
            <input type="hidden" name="episode_indices" value="${epCounter}">
            <div style="display:flex;gap:10px;">
              <div class="form-group" style="flex:1;"><label>Season:</label><input type="number" name="season_number_${epCounter}" value="1" required /></div>
              <div class="form-group" style="flex:1;"><label>Episode:</label><input type="number" name="episode_number_${epCounter}" required /></div>
            </div>
            <div class="form-group"><label>Title:</label><input type="text" name="episode_title_${epCounter}" required /></div>
            <div class="form-group"><label>Watch Link:</label><input type="url" name="episode_watch_link_${epCounter}" /></div>
            <div class="form-group"><label>480p Link:</label><input type="url" name="episode_link_480p_${epCounter}" /></div>
            <div class="form-group"><label>720p Link:</label><input type="url" name="episode_link_720p_${epCounter}" /></div>
            <button type="button" onclick="this.parentElement.remove()" class="btn" style="background:#6c757d;">Remove</button>
        ''';
        container.appendChild(div);
    }
    document.addEventListener('DOMContentLoaded', toggleEpisodeFields);
  </script>
</body></html>
"""


# ----------------- Flask Routes (UPDATED for New Design) -----------------

# Helper function to fetch TMDb data (same as before)
def fetch_tmdb_data(movie):
    if not TMDB_API_KEY:
        return movie, None
    tmdb_type = "tv" if movie.get("type") == "series" else "movie"
    tmdb_id = movie.get("tmdb_id")
    if not tmdb_id:
        try:
            search_url = f"https://api.themoviedb.org/3/search/{tmdb_type}?api_key={TMDB_API_KEY}&query={requests.utils.quote(movie['title'])}"
            search_res = requests.get(search_url, timeout=5).json()
            if search_res.get("results"): tmdb_id = search_res["results"][0].get("id")
        except requests.RequestException: pass
    if not tmdb_id: return movie, None
    try:
        detail_url = f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
        res = requests.get(detail_url, timeout=5).json()
        update_fields = {"tmdb_id": tmdb_id}
        if not movie.get("poster") and res.get("poster_path"): update_fields["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
        if not movie.get("overview") and res.get("overview"): update_fields["overview"] = res["overview"]
        if not movie.get("release_date"):
            release_date = res.get("release_date") or res.get("first_air_date")
            if release_date: update_fields["release_date"] = release_date
        if not movie.get("genres") and res.get("genres"): update_fields["genres"] = [g['name'] for g in res.get("genres", [])]
        if res.get("vote_average"): update_fields["vote_average"] = res.get("vote_average")
        if len(update_fields) > 1:
            movies.update_one({"_id": movie["_id"]}, {"$set": update_fields})
            movie.update(update_fields)
        return movie, None # Trailer logic can be added here if needed
    except requests.RequestException:
        return movie, None


@app.route('/')
def home():
    query = request.args.get('q')
    try:
        if query:
            movies_list = list(movies.find({"title": {"$regex": query, "$options": "i"}}).sort('_id', -1))
            for m in movies_list: m['_id'] = str(m['_id'])
            return render_template_string(index_html, movies=movies_list, query=f'Search Results for "{query}"', is_full_page_list=True)
        else:
            context = {
                "featured_movies": list(movies.find({"is_featured": True, "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(5)),
                "latest_movies": list(movies.find({"type": "movie", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(12)),
                "latest_series": list(movies.find({"type": "series", "is_coming_soon": {"$ne": True}}).sort('_id', -1).limit(12)),
                "is_full_page_list": False, "query": ""
            }
            for key, value in context.items():
                if isinstance(value, list):
                    for item in value:
                        if '_id' in item: item['_id'] = str(item['_id'])
                        # Fetch missing data for display
                        if not item.get('poster') or not item.get('overview'):
                           fetch_tmdb_data(item)
            return render_template_string(index_html, **context)
    except Exception as e:
        print(f"Error in home route: {e}")
        return "An error occurred.", 500

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie_obj: return "Content not found", 404

        movie_obj, _ = fetch_tmdb_data(movie_obj)
        movie = dict(movie_obj); movie['_id'] = str(movie['_id'])
        
        seasons = None
        if movie.get('type') == 'series' and movie.get('episodes'):
            seasons = defaultdict(list)
            for ep in movie['episodes']: seasons[ep['season_number']].append(ep)
        
        return render_template_string(detail_html, movie=movie, seasons=seasons)
    except Exception as e:
        print(f"Error in detail page: {e}")
        return "Error fetching details.", 500

@app.route('/watch/<movie_id>')
def watch_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie: return "Content not found.", 404

        title = movie.get("title")
        if movie.get('type') == 'movie':
            current_episode = {'watch_link': movie.get('watch_link')}
            return render_template_string(watch_html, movie=movie, title=title, current_episode=current_episode, seasons=None)
        
        elif movie.get('type') == 'series':
            seasons = defaultdict(list)
            if not movie.get('episodes'): return "No episodes found.", 404
            for ep in movie['episodes']: seasons[ep['season_number']].append(ep)
            
            req_s = request.args.get('s', type=int)
            req_ep = request.args.get('ep', type=int)
            
            current_episode = None
            if req_s and req_ep:
                for ep in movie['episodes']:
                    if ep.get('season_number') == req_s and ep.get('episode_number') == req_ep:
                        current_episode = ep
                        break
            
            if not current_episode:
                first_s = sorted(seasons.keys())[0]
                current_episode = sorted(seasons[first_s], key=lambda x: x['episode_number'])[0]

            if not current_episode.get('watch_link'): return "Watch link not available.", 404
            title = f"{title} - S{current_episode['season_number']} E{current_episode['episode_number']}"
            return render_template_string(watch_html, movie=movie, title=title, current_episode=current_episode, seasons=seasons)
    except Exception as e:
        print(f"Error on watch page: {e}")
        return "An error occurred.", 500

def process_form_data(form):
    content_type = form.get("content_type", "movie")
    data = {
        "title": form.get("title"), "type": content_type,
        "is_featured": form.get("is_featured") == "true",
        "is_coming_soon": form.get("is_coming_soon") == "true",
        "tmdb_id": None, "poster": form.get("poster_url", "").strip(), "overview": form.get("overview", "").strip(),
        "release_date": form.get("release_date", "").strip(),
        "genres": [g.strip() for g in form.get("genres", "").split(',') if g.strip()]
    }
    if content_type == "movie":
        links = []
        if form.get("link_480p"): links.append({"quality": "480p", "url": form.get("link_480p")})
        if form.get("link_720p"): links.append({"quality": "720p", "url": form.get("link_720p")})
        data["watch_link"] = form.get("watch_link", ""); data["links"] = links
    else:
        episodes = []
        for i in form.getlist('episode_indices'):
            ep_links = []
            if form.get(f'episode_link_480p_{i}'): ep_links.append({"quality": "480p", "url": form.get(f'episode_link_480p_{i}')})
            if form.get(f'episode_link_720p_{i}'): ep_links.append({"quality": "720p", "url": form.get(f'episode_link_720p_{i}')})
            episodes.append({
                "season_number": int(form.get(f'season_number_{i}')), "episode_number": int(form.get(f'episode_number_{i}')),
                "title": form.get(f'episode_title_{i}'), "watch_link": form.get(f'episode_watch_link_{i}'), "links": ep_links
            })
        data["episodes"] = episodes
    return data

@app.route('/admin', methods=["GET", "POST"])
@requires_auth
def admin():
    if request.method == "POST":
        movie_data = process_form_data(request.form)
        movies.insert_one(movie_data)
        return redirect(url_for('admin'))
    all_content = list(movies.find().sort('_id', -1))
    for m in all_content: m['_id'] = str(m['_id'])
    return render_template_string(admin_html, movies=all_content)

@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
    if not movie_obj: return "Movie not found", 404
    if request.method == "POST":
        update_data = process_form_data(request.form)
        if update_data["type"] == "movie":
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"episodes": ""}})
        else:
            movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": "", "watch_link": ""}})
        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": update_data})
        return redirect(url_for('admin'))
    movie_obj['_id'] = str(movie_obj['_id'])
    return render_template_string(edit_html, movie=movie_obj)

@app.route('/delete_movie/<movie_id>', methods=["POST"])
@requires_auth
def delete_movie(movie_id):
    try:
        movies.delete_one({"_id": ObjectId(movie_id)})
    except Exception as e:
        print(f"Error deleting movie: {e}")
    return redirect(url_for('admin'))

def render_full_list(query_filter, title):
    content_list = list(movies.find(query_filter).sort('_id', -1))
    for m in content_list: m['_id'] = str(m['_id'])
    return render_template_string(index_html, movies=content_list, query=title, is_full_page_list=True)

@app.route('/movies')
def movies_only():
    return render_full_list({"type": "movie", "is_coming_soon": {"$ne": True}}, "All Movies")
@app.route('/series')
def webseries():
    return render_full_list({"type": "series", "is_coming_soon": {"$ne": True}}, "All Web Series")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
