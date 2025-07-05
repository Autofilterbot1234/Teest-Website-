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

if not MONGO_URI:
    print("Error: MONGO_URI environment variable must be set. Exiting.")
    exit(1)
if not TMDB_API_KEY:
    print("Warning: TMDB_API_KEY is not set. Metadata fetching will be disabled.")

try:
    client = MongoClient(MONGO_URI)
    db = client["movie_db"]
    movies = db["movies"]
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}. Exiting.")
    exit(1)


# --- START OF index_html TEMPLATE (FINAL DESIGN) ---
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
            --primary-color: #e50914; --dark-color: #141414; --body-bg: #0d0d0d;
            --text-light: #f5f5f5; --text-grey: #a0a0a0; --card-bg: #1a1a1a;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Poppins', sans-serif; background-color: var(--body-bg); color: var(--text-light); }
        a { text-decoration: none; color: inherit; }
        .container { max-width: 1400px; margin: 0 auto; padding: 0 40px; }
        
        /* Header */
        .main-header { position: fixed; top: 0; left: 0; width: 100%; z-index: 1000; padding: 20px 0; background: linear-gradient(to bottom, rgba(0,0,0,0.6), transparent); transition: background-color 0.3s ease-in-out; }
        .main-header.scrolled { background-color: rgba(13, 13, 13, 0.9); backdrop-filter: blur(5px); }
        .header-content { display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 2.2rem; font-weight: 700; color: var(--primary-color); text-transform: uppercase; letter-spacing: 1px; }
        .search-box { position: relative; }
        .search-input { background: rgba(255,255,255,0.1); border: 1px solid #333; color: white; padding: 10px 20px; border-radius: 50px; width: 280px; transition: all 0.3s; }
        .search-input:focus { background: white; color: black; border-color: var(--primary-color); }

        /* Hero Slider */
        .hero-section { padding-top: 80px; } /* Added padding to push content down */
        .hero-slider { height: 80vh; width: 100%; position: relative; border-radius: 12px; overflow: hidden; }
        .swiper-slide { position: relative; color: white; }
        .hero-slide-bg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
        .hero-slide-bg::after { content:''; position: absolute; inset: 0; background: linear-gradient(to top, var(--body-bg) 1%, transparent 50%), linear-gradient(to right, rgba(13, 13, 13, 0.7) 10%, transparent 60%); }
        .slide-content { position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; justify-content: center; max-width: 50%; padding-left: 60px; }
        .slide-title { font-size: 4rem; font-weight: 700; line-height: 1.1; margin-bottom: 1rem; text-shadow: 2px 2px 10px rgba(0,0,0,0.5); }
        .slide-meta { display: flex; gap: 20px; align-items: center; margin-bottom: 1rem; font-weight: 500;}
        .slide-meta .rating { color: #ffc107; }
        .slide-overview { font-size: 1rem; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 1.5rem; max-width: 500px; }
        .slide-btn { background-color: var(--primary-color); padding: 12px 30px; border-radius: 8px; font-weight: 600; transition: transform 0.2s; display: inline-block; }
        .slide-btn:hover { transform: scale(1.05); }
        .swiper-button-next, .swiper-button-prev { color: white; }
        .swiper-pagination-bullet-active { background-color: var(--primary-color); }
        
        /* Content Section */
        .content-section { padding: 50px 0; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
        .section-title { font-size: 1.8rem; font-weight: 600; }
        .see-all-link { color: var(--text-grey); font-weight: 500; }
        .see-all-link:hover { color: var(--primary-color); }

        .content-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 25px; }
        
        /* RGB Border Card */
        @keyframes rgb-border { 0% { border-color: #ff0000; box-shadow: 0 0 10px #ff0000; } 25% { border-color: #00ff00; box-shadow: 0 0 10px #00ff00; } 50% { border-color: #0000ff; box-shadow: 0 0 10px #0000ff; } 75% { border-color: #ffff00; box-shadow: 0 0 10px #ffff00; } 100% { border-color: #ff0000; box-shadow: 0 0 10px #ff0000; } }
        .movie-card { position: relative; border-radius: 10px; overflow: hidden; transition: transform 0.3s ease-out; background-color: var(--card-bg); border: 2px solid transparent; }
        .movie-card:hover { transform: translateY(-10px); animation: rgb-border 4s linear infinite; }
        .card-poster { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.95) 20%, transparent 70%); display: flex; flex-direction: column; justify-content: flex-end; padding: 15px; opacity: 0; transition: opacity 0.3s; }
        .movie-card:hover .card-overlay { opacity: 1; }
        .card-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 5px; }
        .card-meta { font-size: 0.8rem; color: var(--text-grey); display: flex; gap: 10px; }
        .card-meta .rating { color: #ffc107; font-weight: 600; }
        
        /* Full Page Grid */
        .full-page-container { padding-top: 120px; }

        @media (max-width: 768px) {
            .container { padding: 0 20px; }
            .slide-title { font-size: 2.5rem; }
            .slide-content { max-width: 90%; padding-left: 20px; }
            .search-input { width: 180px; }
            .content-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; }
            .swiper-button-next, .swiper-button-prev { display: none; }
        }
    </style>
</head>
<body>
<header class="main-header">
    <div class="container header-content">
        <a href="{{ url_for('home') }}" class="logo">MovieDokan</a>
        <div class="search-box">
            <form method="GET" action="/">
                <input type="search" name="q" class="search-input" placeholder="Search..." value="{{ query|default('') }}">
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
                {% else %}<p>No content found.</p>{% endif %}
            </div>
        </div>
    {% else %}
        <div class="hero-section">
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
                <div class="swiper-button-next"></div>
                <div class="swiper-button-prev"></div>
                <div class="swiper-pagination"></div>
            </div>
        </div>
        <div class="container">
            {% macro render_section(title, movies_list, endpoint) %}
            {% if movies_list %}
            <div class="content-section">
                <div class="section-header">
                    <h2 class="section-title">{{ title }}</h2>
                    <a href="{{ url_for(endpoint) }}" class="see-all-link">See All</a>
                </div>
                <div class="content-grid">
                    {% for movie in movies_list %}
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
            {% endmacro %}
            {{ render_section('Latest Movies', latest_movies, 'movies_only') }}
            {{ render_section('Popular Series', latest_series, 'webseries') }}
        </div>
    {% endif %}
</main>
<script src="https://cdn.jsdelivr.net/npm/swiper@8/swiper-bundle.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function () {
        const header = document.querySelector('.main-header');
        window.addEventListener('scroll', () => {
            header.classList.toggle('scrolled', window.scrollY > 50);
        });
        const swiper = new Swiper('.hero-slider', {
            loop: true, effect: 'fade',
            autoplay: { delay: 5000, disableOnInteraction: false, },
            pagination: { el: '.swiper-pagination', clickable: true, },
            navigation: { nextEl: '.swiper-button-next', prevEl: '.swiper-button-prev', },
        });
    });
</script>
</body>
</html>
"""
# --- END OF index_html TEMPLATE ---


# detail_html, watch_html, admin_html, edit_html টেমপ্লেটগুলো আগের মতোই থাকবে।
# শুধুমাত্র admin এবং edit পেজে `is_featured` চেকবক্স যোগ করা হয়েছে। আমি এখানে শুধু সেই দুটি টেমপ্লেট দিচ্ছি।

# --- START OF admin_html TEMPLATE (UPDATED) ---
admin_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Admin Panel - MovieDokan</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010; --card-bg: #1a1a1a; }
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
    <div class="form-group"><label>Title:</label><input type="text" name="title" required /></div>
    <div class="form-group"><label>Type:</label><select name="content_type" id="content_type" onchange="toggleEpisodeFields()"><option value="movie">Movie</option><option value="series">Series</option></select></div>
    <div id="movie_fields">
        <div class="form-group"><label>Watch Link:</label><input type="url" name="watch_link" /></div>
        <div class="form-group"><label>480p Link:</label><input type="url" name="link_480p" /></div>
        <div class="form-group"><label>720p Link:</label><input type="url" name="link_720p" /></div>
    </div>
    <div id="episode_fields" style="display: none;">
      <h3>Episodes</h3><div id="episodes_container"></div>
      <button type="button" onclick="addEpisodeField()" class="btn">Add Episode</button>
    </div>
    <hr style="border-color: #333; margin: 20px 0;">
    <h3>Details (Optional)</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview"></textarea></div>
    <div class="form-group"><label>Release Date (YYYY-MM-DD):</label><input type="text" name="release_date" /></div>
    <div class="form-group"><label>Genres (Comma-separated):</label><input type="text" name="genres" /></div>
    <hr style="border-color: #333; margin: 20px 0;">
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
        document.getElementById('episode_fields').style.display = document.getElementById('content_type').value === 'series' ? 'block' : 'none';
        document.getElementById('movie_fields').style.display = document.getElementById('content_type').value === 'series' ? 'none' : 'block';
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

# --- START OF edit_html TEMPLATE (UPDATED) ---
edit_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Edit Content - MovieDokan</title>
  <!-- Styles from admin_html can be reused -->
  <style>:root { --primary-color: #e50914; --dark-color: #141414; --body-bg: #101010; --card-bg: #1a1a1a; } body { font-family: 'Poppins', sans-serif; background-color: var(--body-bg); color: #f5f5f5; padding: 20px; } h2, h3 { color: var(--primary-color); font-weight: 600; } form { max-width: 800px; margin: 20px auto; background: var(--card-bg); padding: 25px; border-radius: 8px; } .form-group { margin-bottom: 15px; } label { display: block; margin-bottom: 8px; font-weight: 500; } input, textarea, select { width: 100%; padding: 10px; border-radius: 4px; border: 1px solid #333; background: #222; color: #f5f5f5; box-sizing: border-box; } input[type="checkbox"] { width: auto; margin-right: 10px; } button, .btn { background: var(--primary-color); color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: 600; } .episode-item { border: 1px solid #333; padding: 15px; margin-bottom: 15px; border-radius: 5px; }</style>
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
    <hr style="border-color: #333; margin: 20px 0;">
    <h3>Details</h3>
    <div class="form-group"><label>Poster URL:</label><input type="url" name="poster_url" value="{{ movie.poster or '' }}" /></div>
    <div class="form-group"><label>Overview:</label><textarea name="overview">{{ movie.overview or '' }}</textarea></div>
    <div class="form-group"><label>Release Date:</label><input type="text" name="release_date" value="{{ movie.release_date or '' }}" /></div>
    <div class="form-group"><label>Genres:</label><input type="text" name="genres" value="{{ movie.genres|join(', ') if movie.genres else '' }}" /></div>
    <hr style="border-color: #333; margin: 20px 0;">
    <div class="form-group"><input type="checkbox" name="is_featured" value="true" {% if movie.is_featured %}checked{% endif %}><label style="display:inline;">Add to Homepage Slider?</label></div>
    <div class="form-group"><input type="checkbox" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}><label style="display:inline;">Is Coming Soon?</label></div>
    <button type="submit">Update Content</button>
  </form>
  <script>
    function toggleEpisodeFields() {
        document.getElementById('episode_fields').style.display = document.getElementById('content_type').value === 'series' ? 'block' : 'none';
        document.getElementById('movie_fields').style.display = document.getElementById('content_type').value === 'series' ? 'none' : 'block';
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

# আপনার detail_html এবং watch_html টেমপ্লেট অপরিবর্তিত থাকবে
# The detail_html and watch_html templates will remain unchanged.

# ----------------- Flask Routes (UPDATED) -----------------
# The Python/Flask part of the code remains the same as the previous correct version.
# I'm re-pasting it here for completeness.

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
            return render_template_string(index_html, **context)
    except Exception as e:
        print(f"Error in home route: {e}")
        return "An error occurred.", 500

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie_obj = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie_obj: return "Content not found", 404
        movie = dict(movie_obj); movie['_id'] = str(movie['_id'])
        seasons = None
        if movie.get('type') == 'series' and movie.get('episodes'):
            seasons = defaultdict(list)
            for ep in movie['episodes']: seasons[ep['season_number']].append(ep)
        # Using the same detail_html as before, as it's functional
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

# process_form_data, admin, edit_movie, delete_movie and other routes remain the same
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
    return render_full_list({"type": "series", "is_coming_soon": {"$ne": True}}, "Popular Series")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
