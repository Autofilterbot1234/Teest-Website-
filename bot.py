import os
import requests
from flask import Flask, request, redirect, url_for, render_template_string, session
from functools import wraps
from pymongo import MongoClient
from bson.objectid import ObjectId
import hashlib

app = Flask(__name__)
app.secret_key = os.urandom(24) # A strong secret key for session management

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/") # Use environment variable or default
DB_NAME = "moviezone_db"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
movies = db.movies # Collection for movie/series data
users = db.users   # Collection for admin users

# TMDb API Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY") # Get your TMDb API key from environment variables

# TMDb Genre Map (Common genres, extend as needed)
TMDb_Genre_Map = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
    27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western",
    10759: "Action & Adventure", 10762: "Kids", 10763: "News", 10764: "Reality",
    10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk", 10768: "War & Politics"
}

# --- Utility Functions ---

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password_hash, provided_password):
    return stored_password_hash == hash_password(provided_password)

# --- Admin Authentication ---

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.find_one({"username": username})
        if user and verify_password(user['password_hash'], password):
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template_string(login_html, message="Invalid Credentials")
    return render_template_string(login_html, message=None)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

# --- Routes ---

@app.route('/')
def home():
    search_query = request.args.get('q')
    content_type_filter = request.args.get('type', 'all')
    genre_filter = request.args.get('genre', 'all')
    language_filter = request.args.get('lang', 'all')
    sort_by = request.args.get('sort', 'latest') # New sort parameter

    filter_criteria = {}

    if search_query:
        filter_criteria["title"] = {"$regex": search_query, "$options": "i"}
    
    if content_type_filter != 'all':
        filter_criteria["type"] = content_type_filter

    if genre_filter != 'all':
        filter_criteria["genres"] = genre_filter
        
    if language_filter != 'all':
        filter_criteria["original_language"] = language_filter.lower()

    if sort_by == 'popular':
        sort_order = [("vote_average", -1)] # Sort by vote_average descending
    else: # Default to 'latest'
        sort_order = [('_id', -1)] # Sort by latest (MongoDB's default _id is time-based)


    all_content = list(movies.find(filter_criteria).sort(sort_order))
    
    for content in all_content:
        content['_id'] = str(content['_id'])

    # Get unique genres and languages for filters
    unique_genres = sorted(movies.distinct("genres"))
    unique_languages = sorted([lang.upper() for lang in movies.distinct("original_language") if lang])

    return render_template_string(index_html, movies=all_content, 
                                  search_query=search_query, 
                                  content_type_filter=content_type_filter,
                                  genre_filter=genre_filter,
                                  language_filter=language_filter,
                                  unique_genres=unique_genres,
                                  unique_languages=unique_languages,
                                  sort_by=sort_by)

@app.route('/movie/<movie_id>')
def movie_detail(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if movie:
            movie['_id'] = str(movie['_id'])
            
            # Determine TMDb type for detail and video fetch
            tmdb_content_type = "movie" if movie.get("type") == "movie" else "tv"

            # Check if additional TMDb details (overview, poster, etc.) need fetching
            # Fetch if any essential detail is missing or generic, OR if tmdb_id is not set
            should_fetch_details = TMDB_API_KEY and (
                not movie.get("tmdb_id") or 
                movie.get("overview") == "No overview available." or 
                not movie.get("poster") or 
                movie.get("year") == "N/A" or 
                movie.get("original_language") == "N/A" or 
                not movie.get("genres") or movie.get("genres") == [] # Check if genres are missing or empty
            )
            
            # Check if trailer key needs fetching (only if TMDb ID is available or can be found)
            should_fetch_trailer = TMDB_API_KEY and not movie.get("trailer_key")

            # --- Fetching details (overview, poster, etc.) ---
            if should_fetch_details:
                tmdb_id = movie.get("tmdb_id") 
                
                # If tmdb_id is not stored, try to search for it first
                if not tmdb_id:
                    search_url = f"https://api.themoviedb.org/3/search/{tmdb_content_type}?api_key={TMDB_API_KEY}&query={movie['title']}"
                    try:
                        search_res = requests.get(search_url, timeout=5).json()
                        if search_res and "results" in search_res and search_res["results"]:
                            tmdb_id = search_res["results"][0].get("id")
                            # Update tmdb_id in the database immediately
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"tmdb_id": tmdb_id}})
                            movie["tmdb_id"] = tmdb_id # Update current movie object
                            print(f"TMDb ID found for '{movie['title']}' and updated.")
                        else:
                            print(f"No search results found on TMDb for title: {movie['title']} ({tmdb_content_type})")
                            tmdb_id = None
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for search '{movie['title']}': {e}")
                        tmdb_id = None
                    except Exception as e:
                        print(f"An unexpected error occurred during TMDb search for '{movie['title']}': {e}")
                        tmdb_id = None

                if tmdb_id:
                    tmdb_detail_url = f"https://api.themoviedb.org/3/{tmdb_content_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
                    try:
                        res = requests.get(tmdb_detail_url, timeout=5).json()
                        updated_fields = {}

                        if movie.get("overview") == "No overview available." and res.get("overview"):
                            movie["overview"] = res.get("overview")
                            updated_fields["overview"] = movie["overview"]
                        if not movie.get("poster") and res.get("poster_path"):
                            movie["poster"] = f"https://image.tmdb.org/t/p/w500{res['poster_path']}"
                            updated_fields["poster"] = movie["poster"]
                        
                        release_date_key = "release_date" if tmdb_content_type == "movie" else "first_air_date"
                        release_date = res.get(release_date_key)
                        if movie.get("year") == "N/A" and release_date:
                            movie["year"] = release_date[:4]
                            movie["release_date"] = release_date
                            updated_fields["year"] = movie["year"]
                            updated_fields["release_date"] = movie["release_date"]
                        
                        if movie.get("vote_average") is None and res.get("vote_average"):
                            movie["vote_average"] = res.get("vote_average")
                            updated_fields["vote_average"] = movie["vote_average"]
                        if movie.get("original_language") == "N/A" and res.get("original_language"):
                            movie["original_language"] = res.get("original_language")
                            updated_fields["original_language"] = movie["original_language"]
                        
                        genres_names = []
                        for genre_obj in res.get("genres", []):
                            if isinstance(genre_obj, dict) and genre_obj.get("id") in TMDb_Genre_Map:
                                genres_names.append(TMDb_Genre_Map[genre_obj["id"]])
                        if (not movie.get("genres") or movie["genres"] == []) and genres_names:
                            movie["genres"] = genres_names
                            updated_fields["genres"] = movie["genres"]

                        # Persist TMDb fetched data to DB
                        if updated_fields:
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_fields})
                            print(f"TMDb details updated for '{movie['title']}'.")
                    except requests.exceptions.RequestException as e:
                        print(f"Error connecting to TMDb API for detail '{movie_id}': {e}")
                    except Exception as e:
                        print(f"An unexpected error occurred while fetching TMDb detail data: {e}")
                else:
                    print(f"TMDb ID not found for content '{movie.get('title', movie_id)}'. Skipping TMDb detail fetch.")
            else:
                print("Skipping TMDb API call for general details (no key, or data already present).")

            # --- Fetching Trailer Key ---
            if should_fetch_trailer and movie.get("tmdb_id"): # Only fetch trailer if tmdb_id is known
                trailer_url = f"https://api.themoviedb.org/3/{tmdb_content_type}/{movie['tmdb_id']}/videos?api_key={TMDB_API_KEY}"
                try:
                    trailer_res = requests.get(trailer_url, timeout=5).json()
                    if trailer_res and "results" in trailer_res and trailer_res["results"]:
                        trailer_key = None
                        for video in trailer_res["results"]:
                            # Prioritize 'Trailer' type, then 'Teaser'
                            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                                trailer_key = video.get("key")
                                break
                        if not trailer_key: # If no "Trailer" found, look for "Teaser"
                             for video in trailer_res["results"]:
                                if video.get("site") == "YouTube" and video.get("type") == "Teaser":
                                    trailer_key = video.get("key")
                                    break
                        
                        if trailer_key:
                            movie["trailer_key"] = trailer_key
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"trailer_key": trailer_key}})
                            print(f"Trailer key found and updated for '{movie['title']}'.")
                        else:
                            print(f"No suitable trailer (Trailer/Teaser) found on TMDb for '{movie['title']}'.")
                            movie["trailer_key"] = None 
                            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"trailer_key": None}}) # Persist None to avoid re-fetching
                    else:
                        print(f"No video results found on TMDb for '{movie['title']}' ({tmdb_content_type}).")
                        movie["trailer_key"] = None
                        movies.update_one({"_id": ObjectId(movie_id)}, {"$set": {"trailer_key": None}}) # Persist None
                except requests.exceptions.RequestException as e:
                    print(f"Error connecting to TMDb API for trailer '{movie['title']}': {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while fetching TMDb trailer data: {e}")
            else:
                print("Skipping TMDb API call for trailer (no key, or trailer already present, or no TMDb ID).")


        return render_template_string(detail_html, movie=movie)
    except Exception as e:
        print(f"Error fetching movie detail for ID {movie_id}: {e}")
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
            "title": title,
            "quality": quality_tag,
            "type": content_type,
            "overview": manual_overview if manual_overview else "No overview available.",
            "poster": manual_poster_url if manual_poster_url else "",
            "year": manual_year if manual_year else "N/A",
            "release_date": manual_year if manual_year else "N/A", # Will be updated by TMDb if available
            "vote_average": None,
            "original_language": manual_original_language if manual_original_language else "N/A",
            "genres": manual_genres_list,
            "tmdb_id": None, # Will be set by TMDb API call
            "trailer_key": None, # Will be set by TMDb API call in detail page
            "top_label": manual_top_label if manual_top_label else "",
            "is_coming_soon": is_coming_soon
        }

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
                if episode_link_480ps and episode_link_480ps[i]:
                    episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                if episode_link_720ps and episode_link_720ps[i]:
                    episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                if episode_link_1080ps and episode_link_1080ps[i]:
                    episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                
                episodes_list.append({
                    "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                    "title": episode_titles[i] if episode_titles[i] else f"Episode {episode_numbers[i]}", # Fallback for episode title
                    "overview": episode_overviews[i] if episode_overviews[i] else "No overview available for this episode.",
                    "links": episode_links
                })
            movie_data["episodes"] = episodes_list

        # TMDb API call for both movies and series for initial metadata
        if TMDB_API_KEY and (not manual_poster_url or not manual_overview or movie_data["overview"] == "No overview available." or not movie_data["poster"]):
            tmdb_search_type = "movie" if content_type == "movie" else "tv" # Determine search type
            tmdb_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={title}"
            try:
                res = requests.get(tmdb_url, timeout=5).json()
                if res and "results" in res and res["results"]:
                    data = res["results"][0]
                    
                    if not manual_overview and data.get("overview"):
                        movie_data["overview"] = data.get("overview")
                    if not manual_poster_url and data.get("poster_path"):
                        movie_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                    
                    release_date_key = "release_date" if content_type == "movie" else "first_air_date"
                    release_date = data.get(release_date_key)
                    if not manual_year and release_date:
                        movie_data["year"] = release_date[:4]
                        movie_data["release_date"] = release_date
                    
                    movie_data["vote_average"] = data.get("vote_average", movie_data["vote_average"])
                    if not manual_original_language and data.get("original_language"):
                        movie_data["original_language"] = data.get("original_language")
                    
                    genres_names = []
                    for genre_id in data.get("genre_ids", []):
                        if genre_id in TMDb_Genre_Map:
                            genres_names.append(TMDb_Genre_Map[genre_id])
                    if not manual_genres_list and genres_names:
                        movie_data["genres"] = genres_names
                    
                    movie_data["tmdb_id"] = data.get("id")
                    print(f"TMDb data filled for '{title}': ID={movie_data['tmdb_id']}, Overview={movie_data['overview'][:50]}...")
                else:
                    print(f"No results found on TMDb for title: {title} ({tmdb_search_type})")
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to TMDb API for '{title}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred while fetching TMDb data: {e}")
        else:
            print("Skipping TMDb API call (no key, or manual poster/overview provided).")

        try:
            movies.insert_one(movie_data)
            print(f"Content '{movie_data['title']}' added successfully to MovieZone!")
            return redirect(url_for('admin'))
        except Exception as e:
            print(f"Error inserting content into MongoDB: {e}")
            return redirect(url_for('admin'))

    admin_query = request.args.get('q')

    if admin_query:
        all_content = list(movies.find({"title": {"$regex": admin_query, "$options": "i"}}).sort('_id', -1))
    else:
        all_content = list(movies.find().sort('_id', -1))
    
    for content in all_content:
        content['_id'] = str(content['_id']) 

    return render_template_string(admin_html, movies=all_content, admin_query=admin_query)


@app.route('/edit_movie/<movie_id>', methods=["GET", "POST"])
@requires_auth
def edit_movie(movie_id):
    try:
        movie = movies.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            return "Movie not found!", 404

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
            
            updated_data = {
                "title": title,
                "quality": quality_tag,
                "type": content_type,
                "overview": manual_overview if manual_overview else "No overview available.",
                "poster": manual_poster_url if manual_poster_url else "",
                "year": manual_year if manual_year else "N/A",
                "release_date": manual_year if manual_year else "N/A",
                "original_language": manual_original_language if manual_original_language else "N/A",
                "genres": manual_genres_list,
                "top_label": manual_top_label if manual_top_label else "",
                "is_coming_soon": is_coming_soon,
                # Retain existing tmdb_id and trailer_key, they will be updated by detail page fetch or if TMDb auto-fill overrides
                "tmdb_id": movie.get("tmdb_id"), 
                "trailer_key": movie.get("trailer_key")
            }

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
                # If changing from series to movie, remove episodes field
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
                    if episode_link_480ps and episode_link_480ps[i]:
                        episode_links.append({"quality": "480p", "size": "590MB", "url": episode_link_480ps[i]})
                    if episode_link_720ps and episode_link_720ps[i]:
                        episode_links.append({"quality": "720p", "size": "1.4GB", "url": episode_link_720ps[i]})
                    if episode_link_1080ps and episode_link_1080ps[i]:
                        episode_links.append({"quality": "1080p", "size": "2.9GB", "url": episode_link_1080ps[i]})
                    
                    episodes_list.append({
                        "episode_number": int(episode_numbers[i]) if episode_numbers[i] else 0,
                        "title": episode_titles[i] if episode_titles[i] else f"Episode {episode_numbers[i]}",
                        "overview": episode_overviews[i] if episode_overviews[i] else "No overview available for this episode.",
                        "links": episode_links
                    })
                updated_data["episodes"] = episodes_list
                # If changing from movie to series, remove links field
                if "links" in movie:
                    movies.update_one({"_id": ObjectId(movie_id)}, {"$unset": {"links": ""}})

            # TMDb API call for both movies and series in edit_movie
            # Only fetch if specific manual fields are empty, allowing manual override
            if TMDB_API_KEY and (not manual_poster_url or not manual_overview or updated_data["overview"] == "No overview available." or not updated_data["poster"]):
                tmdb_search_type = "movie" if content_type == "movie" else "tv"
                tmdb_url = f"https://api.themoviedb.org/3/search/{tmdb_search_type}?api_key={TMDB_API_KEY}&query={title}"
                try:
                    res = requests.get(tmdb_url, timeout=5).json()
                    if res and "results" in res and res["results"]:
                        data = res["results"][0]
                        
                        if not manual_overview and data.get("overview"):
                            updated_data["overview"] = data.get("overview")
                        if not manual_poster_url and data.get("poster_path"):
                            updated_data["poster"] = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
                        
                        release_date_key = "release_date" if content_type == "movie" else "first_air_date"
                        release_date = data.get(release_date_key)
                        if not manual_year and release_date:
                            updated_data["year"] = release_date[:4]
                            updated_data["release_date"] = release_date
                        
                        updated_data["vote_average"] = data.get("vote_average", movie.get("vote_average"))
                        if not manual_original_language and data.get("original_language"):
                            updated_data["original_language"] = data.get("original_language")
                        
                        genres_names = []
                        for genre_id in data.get("genre_ids", []):
                            if genre_id in TMDb_Genre_Map:
                                genres_names.append(TMDb_Genre_Map[genre_id])
                        if not manual_genres_list and genres_names:
                            updated_data["genres"] = genres_names
                        
                        updated_data["tmdb_id"] = data.get("id") # Update tmdb_id during edit if a new search is performed
                        print(f"TMDb data re-filled for '{title}' during edit.")
                    else:
                        print(f"No results found on TMDb for title: {title} ({tmdb_search_type}) during edit.")
                except requests.exceptions.RequestException as e:
                    print(f"Error connecting to TMDb API for '{title}' during edit: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while fetching TMDb data during edit: {e}")
            else:
                print("Skipping TMDb API call (no key, or manual poster/overview provided).")
            
            movies.update_one({"_id": ObjectId(movie_id)}, {"$set": updated_data})
            print(f"Content '{title}' updated successfully!")
            return redirect(url_for('admin'))

        else:
            movie['_id'] = str(movie['_id']) 
            return render_template_string(edit_html, movie=movie)

    except Exception as e:
        print(f"Error processing edit for movie ID {movie_id}: {e}")
        return "An error occurred during editing.", 500

@app.route('/delete_movie/<movie_id>', methods=["POST"])
@requires_auth
def delete_movie(movie_id):
    try:
        movies.delete_one({"_id": ObjectId(movie_id)})
        print(f"Content ID {movie_id} deleted successfully.")
        return redirect(url_for('admin'))
    except Exception as e:
        print(f"Error deleting content ID {movie_id}: {e}")
        return "An error occurred during deletion.", 500

# --- HTML Templates (as Python strings) ---

# Admin Login HTML
login_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a1a; color: #f0f0f0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background-color: #2a2a2a; padding: 40px; border-radius: 10px; box-shadow: 0 0 20px rgba(0, 0, 0, 0.5); width: 350px; text-align: center; }
        h1 { color: #007bff; margin-bottom: 30px; font-size: 28px; }
        .form-group { margin-bottom: 20px; text-align: left; }
        label { display: block; margin-bottom: 8px; color: #ccc; font-weight: bold; }
        input[type="text"], input[type="password"] { width: calc(100% - 20px); padding: 12px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 16px; }
        input[type="text"]:focus, input[type="password"]:focus { outline: none; border-color: #007bff; box-shadow: 0 0 5px rgba(0, 123, 255, 0.5); }
        button { width: 100%; padding: 12px; background-color: #007bff; color: white; border: none; border-radius: 5px; font-size: 18px; cursor: pointer; transition: background-color 0.3s ease; margin-top: 20px; }
        button:hover { background-color: #0056b3; }
        .message { color: #ff6347; margin-top: 15px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Admin Login</h1>
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        {% if message %}
        <p class="message">{{ message }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

# Admin HTML
admin_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Admin - MovieZone</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #1a1a1a; color: #f0f0f0; }
  header { background-color: #2a2a2a; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); }
  header h1 { color: #007bff; margin: 0; font-size: 28px; }
  .logout-button { background-color: #dc3545; color: white; padding: 10px 18px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s ease; text-decoration: none; }
  .logout-button:hover { background-color: #c82333; }
  main { padding: 30px; max-width: 1200px; margin: 20px auto; background-color: #2a2a2a; border-radius: 10px; box-shadow: 0 0 15px rgba(0, 0, 0, 0.5); }
  h2 { color: #007bff; text-align: center; margin-bottom: 30px; font-size: 26px; }
  .form-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 40px; }
  .form-group { margin-bottom: 15px; }
  label { display: block; margin-bottom: 8px; color: #ccc; font-weight: bold; }
  input[type="text"], input[type="number"], textarea, select { width: calc(100% - 20px); padding: 12px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 16px; }
  input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus { outline: none; border-color: #007bff; box-shadow: 0 0 5px rgba(0, 123, 255, 0.5); }
  textarea { resize: vertical; min-height: 80px; }
  .checkbox-group { display: flex; align-items: center; margin-bottom: 15px; }
  .checkbox-group input { margin-right: 10px; width: auto; }
  .btn-submit { background-color: #28a745; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 18px; transition: background-color 0.3s ease; grid-column: 1 / -1; }
  .btn-submit:hover { background-color: #218838; }
  .movie-list { margin-top: 40px; }
  .movie-item { background-color: #333; padding: 15px; margin-bottom: 15px; border-radius: 8px; display: flex; align-items: center; box-shadow: 0 0 10px rgba(0,0,0,0.3); }
  .movie-item img { width: 80px; height: 120px; object-fit: cover; border-radius: 5px; margin-right: 15px; }
  .movie-info { flex-grow: 1; }
  .movie-info h3 { margin: 0 0 5px 0; color: #007bff; font-size: 20px; }
  .movie-info p { margin: 0; color: #ccc; font-size: 14px; }
  .movie-actions { display: flex; gap: 10px; }
  .movie-actions .edit-btn, .movie-actions .delete-btn { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; transition: background-color 0.3s ease; text-decoration: none; }
  .movie-actions .edit-btn { background-color: #ffc107; color: #333; }
  .movie-actions .edit-btn:hover { background-color: #e0a800; }
  .movie-actions .delete-btn { background-color: #dc3545; color: white; }
  .movie-actions .delete-btn:hover { background-color: #c82333; }
  .search-bar { margin-bottom: 25px; text-align: center; }
  .search-bar input[type="text"] { width: 60%; max-width: 500px; padding: 12px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 16px; }
  .search-bar button { padding: 12px 20px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-left: 10px; transition: background-color 0.3s ease; }
  .search-bar button:hover { background-color: #0056b3; }
  
  /* Episode fields styling */
  .episode-fields { border: 1px solid #444; padding: 15px; margin-top: 20px; border-radius: 8px; background-color: #3a3a3a; }
  .episode-fields h4 { color: #007bff; margin-top: 0; margin-bottom: 15px; font-size: 18px; }
  .episode-item { background-color: #444; padding: 10px; margin-bottom: 10px; border-radius: 5px; position: relative; }
  .episode-item .form-group { margin-bottom: 10px; }
  .episode-item input, .episode-item textarea { width: calc(100% - 20px); }
  .remove-episode { position: absolute; top: 10px; right: 10px; background-color: #dc3545; color: white; border: none; border-radius: 50%; width: 25px; height: 25px; display: flex; justify-content: center; align-items: center; cursor: pointer; font-size: 14px; }
  .add-episode-btn { background-color: #17a2b8; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px; }
  .add-episode-btn:hover { background-color: #138496; }

  /* Responsive Adjustments */
  @media (max-width: 768px) {
    .form-container { grid-template-columns: 1fr; }
    header { flex-direction: column; text-align: center; }
    header h1 { margin-bottom: 10px; }
    .search-bar input[type="text"] { width: 80%; }
  }
  @media (max-width: 480px) {
    main { padding: 15px; }
    .movie-item { flex-direction: column; align-items: flex-start; }
    .movie-item img { margin-right: 0; margin-bottom: 10px; }
    .movie-actions { width: 100%; justify-content: flex-end; margin-top: 10px; }
  }
</style>
<script>
  function showHideFields() {
    var contentType = document.getElementById('content_type').value;
    var movieFields = document.getElementById('movie_fields');
    var episodeFields = document.getElementById('episode_fields');

    if (contentType === 'movie') {
      movieFields.style.display = 'block';
      episodeFields.style.display = 'none';
    } else {
      movieFields.style.display = 'none';
      episodeFields.style.display = 'block';
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    showHideFields(); // Call on page load to set initial state

    // Event listener for content type change
    document.getElementById('content_type').addEventListener('change', showHideFields);

    // Add episode dynamically
    document.getElementById('add_episode').addEventListener('click', function() {
      var episodeContainer = document.getElementById('episodes_container');
      var episodeCount = episodeContainer.children.length + 1; // Simple incrementing counter

      var newEpisodeHtml = `
        <div class="episode-item">
          <button type="button" class="remove-episode" onclick="this.closest('.episode-item').remove()">X</button>
          <div class="form-group">
            <label for="episode_number_${episodeCount}">Episode Number:</label>
            <input type="number" id="episode_number_${episodeCount}" name="episode_number[]" value="${episodeCount}" required>
          </div>
          <div class="form-group">
            <label for="episode_title_${episodeCount}">Episode Title:</label>
            <input type="text" id="episode_title_${episodeCount}" name="episode_title[]" placeholder="e.g., The Pilot">
          </div>
          <div class="form-group">
            <label for="episode_overview_${episodeCount}">Episode Overview:</label>
            <textarea id="episode_overview_${episodeCount}" name="episode_overview[]" placeholder="Brief summary of the episode"></textarea>
          </div>
          <div class="form-group">
            <label for="episode_link_480p_${episodeCount}">480p Download Link:</label>
            <input type="text" id="episode_link_480p_${episodeCount}" name="episode_link_480p[]" placeholder="https://example.com/episode_480p">
          </div>
          <div class="form-group">
            <label for="episode_link_720p_${episodeCount}">720p Download Link:</label>
            <input type="text" id="episode_link_720p_${episodeCount}" name="episode_link_720p[]" placeholder="https://example.com/episode_720p">
          </div>
          <div class="form-group">
            <label for="episode_link_1080p_${episodeCount}">1080p Download Link:</label>
            <input type="text" id="episode_link_1080p_${episodeCount}" name="episode_link_1080p[]" placeholder="https://example.com/episode_1080p">
          </div>
        </div>
      `;
      episodeContainer.insertAdjacentHTML('beforeend', newEpisodeHtml);
    });

    // Handle existing episodes for edit page (if applicable)
    // This part is crucial for the edit_html. We need to ensure that the
    // episode fields are correctly populated when editing a series.
    // This admin_html snippet is for the 'add' page primarily,
    // but the JS here prepares for both.
    // For 'edit_movie' page, you'd iterate through movie.episodes
    // and create these episode-item blocks with pre-filled values.
  });
</script>
</head>
<body>
<header>
  <h1>Admin Panel</h1>
  <a href="{{ url_for('logout') }}" class="logout-button">Logout</a>
</header>
<main>
  <h2>Add New Content</h2>
  <form method="POST">
    <div class="form-container">
      <div class="form-group">
        <label for="title">Title:</label>
        <input type="text" id="title" name="title" required placeholder="e.g., Inception or The Office">
      </div>
      <div class="form-group">
        <label for="content_type">Content Type:</label>
        <select id="content_type" name="content_type" onchange="showHideFields()">
          <option value="movie">Movie</option>
          <option value="series">Series</option>
        </select>
      </div>
      <div class="form-group">
        <label for="quality">Quality Tag (e.g., HD, WEB-DL, BluRay):</label>
        <input type="text" id="quality" name="quality" placeholder="e.g., HD">
      </div>
      <div class="form-group">
        <label for="top_label">Top Label (Optional, e.g., Featured):</label>
        <input type="text" id="top_label" name="top_label" placeholder="e.g., Featured">
      </div>
      <div class="form-group">
        <label for="overview">Overview (from TMDb or manual):</label>
        <textarea id="overview" name="overview" placeholder="A brief description of the movie/series. Automatically fetched from TMDb if left empty."></textarea>
      </div>
      <div class="form-group">
        <label for="poster_url">Poster URL (from TMDb or manual):</label>
        <input type="text" id="poster_url" name="poster_url" placeholder="Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="year">Release Year (from TMDb or manual):</label>
        <input type="text" id="year" name="year" placeholder="e.g., 2023. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="original_language">Original Language (from TMDb or manual):</label>
        <input type="text" id="original_language" name="original_language" placeholder="e.g., en, es. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="genres">Genres (comma-separated, from TMDb or manual):</label>
        <input type="text" id="genres" name="genres" placeholder="e.g., Action, Sci-Fi. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="checkbox-group">
          <input type="checkbox" id="is_trending" name="is_trending" value="true">
          <label for="is_trending">Mark as Trending (overrides Quality tag to TRENDING)</label>
      </div>
      <div class="checkbox-group">
          <input type="checkbox" id="is_coming_soon" name="is_coming_soon" value="true">
          <label for="is_coming_soon">Mark as Coming Soon</label>
      </div>
    </div>

    <div id="movie_fields">
      <h3>Movie Download Links</h3>
      <div class="form-group">
        <label for="link_480p">480p Download Link:</label>
        <input type="text" id="link_480p" name="link_480p" placeholder="https://example.com/movie_480p.mp4">
      </div>
      <div class="form-group">
        <label for="link_720p">720p Download Link:</label>
        <input type="text" id="link_720p" name="link_720p" placeholder="https://example.com/movie_720p.mp4">
      </div>
      <div class="form-group">
        <label for="link_1080p">1080p Download Link:</label>
        <input type="text" id="link_1080p" name="link_1080p" placeholder="https://example.com/movie_1080p.mp4">
      </div>
    </div>

    <div id="episode_fields" style="display: none;">
      <div class="episode-fields">
        <h4>Series Episodes</h4>
        <div id="episodes_container">
          <div class="episode-item">
            <button type="button" class="remove-episode" onclick="this.closest('.episode-item').remove()">X</button>
            <div class="form-group">
              <label for="episode_number_1">Episode Number:</label>
              <input type="number" id="episode_number_1" name="episode_number[]" value="1" required>
            </div>
            <div class="form-group">
              <label for="episode_title_1">Episode Title:</label>
              <input type="text" id="episode_title_1" name="episode_title[]" placeholder="e.g., The Pilot">
            </div>
            <div class="form-group">
              <label for="episode_overview_1">Episode Overview:</label>
              <textarea id="episode_overview_1" name="episode_overview[]" placeholder="Brief summary of the episode"></textarea>
            </div>
            <div class="form-group">
              <label for="episode_link_480p_1">480p Download Link:</label>
              <input type="text" id="episode_link_480p_1" name="episode_link_480p[]" placeholder="https://example.com/episode_480p">
            </div>
            <div class="form-group">
              <label for="episode_link_720p_1">720p Download Link:</label>
              <input type="text" id="episode_link_720p_1" name="episode_link_720p[]" placeholder="https://example.com/episode_720p">
            </div>
            <div class="form-group">
              <label for="episode_link_1080p_1">1080p Download Link:</label>
              <input type="text" id="episode_link_1080p_1" name="episode_link_1080p[]" placeholder="https://example.com/episode_1080p">
            </div>
          </div>
        </div>
        <button type="button" id="add_episode" class="add-episode-btn">Add Another Episode</button>
      </div>
    </div>

    <button type="submit" class="btn-submit">Add Content</button>
  </form>

  <hr style="border-color:#444; margin: 40px 0;">

  <h2>Existing Content</h2>
  <div class="search-bar">
      <form method="GET" action="{{ url_for('admin') }}">
          <input type="text" name="q" placeholder="Search content..." value="{{ admin_query if admin_query }}">
          <button type="submit">Search</button>
      </form>
  </div>
  <div class="movie-list">
    {% if movies %}
      {% for movie in movies %}
        <div class="movie-item">
          {% if movie.poster %}
            <img src="{{ movie.poster }}" alt="{{ movie.title }}">
          {% else %}
            <div style="width: 80px; height: 120px; background:#444; display:flex;align-items:center;justify-content:center;color:#777; font-size:12px; text-align:center; border-radius: 5px;">No Image</div>
          {% endif %}
          <div class="movie-info">
            <h3>{{ movie.title }} ({{ movie.get('year', 'N/A') }})</h3>
            <p>Type: {{ movie.type | title }}</p>
            <p>Quality: {{ movie.quality }}</p>
            <p>Genres: {{ movie.genres | join(', ') if movie.genres else 'N/A' }}</p>
            <p>Language: {{ movie.original_language | upper if movie.original_language else 'N/A'}}</p>
            {% if movie.is_coming_soon %}
                <p style="color:#ffc107;">COMING SOON</p>
            {% endif %}
          </div>
          <div class="movie-actions">
            <a href="{{ url_for('edit_movie', movie_id=movie._id) }}" class="edit-btn">Edit</a>
            <form action="{{ url_for('delete_movie', movie_id=movie._id) }}" method="POST" onsubmit="return confirm('Are you sure you want to delete this content?');">
              <button type="submit" class="delete-btn">Delete</button>
            </form>
          </div>
        </div>
      {% endfor %}
    {% else %}
      <p style="text-align:center; color:#999;">No content found.</p>
    {% endif %}
  </div>
</main>
</body>
</html>
"""

# Edit HTML (Updated to handle series episodes and TMDb auto-fill)
edit_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Edit Content - MovieZone</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #1a1a1a; color: #f0f0f0; }
  header { background-color: #2a2a2a; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); }
  header h1 { color: #007bff; margin: 0; font-size: 28px; }
  .back-button { background-color: #555; color: white; padding: 10px 18px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s ease; text-decoration: none; }
  .back-button:hover { background-color: #666; }
  main { padding: 30px; max-width: 1200px; margin: 20px auto; background-color: #2a2a2a; border-radius: 10px; box-shadow: 0 0 15px rgba(0, 0, 0, 0.5); }
  h2 { color: #007bff; text-align: center; margin-bottom: 30px; font-size: 26px; }
  .form-container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 40px; }
  .form-group { margin-bottom: 15px; }
  label { display: block; margin-bottom: 8px; color: #ccc; font-weight: bold; }
  input[type="text"], input[type="number"], textarea, select { width: calc(100% - 20px); padding: 12px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 16px; }
  input[type="text"]:focus, input[type="number"]:focus, textarea:focus, select:focus { outline: none; border-color: #007bff; box-shadow: 0 0 5px rgba(0, 123, 255, 0.5); }
  textarea { resize: vertical; min-height: 80px; }
  .checkbox-group { display: flex; align-items: center; margin-bottom: 15px; }
  .checkbox-group input { margin-right: 10px; width: auto; }
  .btn-submit { background-color: #007bff; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 18px; transition: background-color 0.3s ease; grid-column: 1 / -1; }
  .btn-submit:hover { background-color: #0056b3; }

  /* Episode fields styling */
  .episode-fields { border: 1px solid #444; padding: 15px; margin-top: 20px; border-radius: 8px; background-color: #3a3a3a; }
  .episode-fields h4 { color: #007bff; margin-top: 0; margin-bottom: 15px; font-size: 18px; }
  .episode-item { background-color: #444; padding: 10px; margin-bottom: 10px; border-radius: 5px; position: relative; }
  .episode-item .form-group { margin-bottom: 10px; }
  .episode-item input, .episode-item textarea { width: calc(100% - 20px); }
  .remove-episode { position: absolute; top: 10px; right: 10px; background-color: #dc3545; color: white; border: none; border-radius: 50%; width: 25px; height: 25px; display: flex; justify-content: center; align-items: center; cursor: pointer; font-size: 14px; }
  .add-episode-btn { background-color: #17a2b8; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px; }
  .add-episode-btn:hover { background-color: #138496; }

  /* Responsive Adjustments */
  @media (max-width: 768px) {
    .form-container { grid-template-columns: 1fr; }
  }
  @media (max-width: 480px) {
    main { padding: 15px; }
  }
</style>
<script>
  function showHideFields() {
    var contentType = document.getElementById('content_type').value;
    var movieFields = document.getElementById('movie_fields');
    var episodeFields = document.getElementById('episode_fields');

    if (contentType === 'movie') {
      movieFields.style.display = 'block';
      episodeFields.style.display = 'none';
    } else {
      movieFields.style.display = 'none';
      episodeFields.style.display = 'block';
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    showHideFields(); // Call on page load to set initial state

    // Event listener for content type change
    document.getElementById('content_type').addEventListener('change', showHideFields);

    // Add episode dynamically
    document.getElementById('add_episode').addEventListener('click', function() {
      var episodeContainer = document.getElementById('episodes_container');
      var episodeCount = episodeContainer.children.length + 1; 

      var newEpisodeHtml = `
        <div class="episode-item">
          <button type="button" class="remove-episode" onclick="this.closest('.episode-item').remove()">X</button>
          <div class="form-group">
            <label for="episode_number_${episodeCount}">Episode Number:</label>
            <input type="number" id="episode_number_${episodeCount}" name="episode_number[]" value="${episodeCount}" required>
          </div>
          <div class="form-group">
            <label for="episode_title_${episodeCount}">Episode Title:</label>
            <input type="text" id="episode_title_${episodeCount}" name="episode_title[]" placeholder="e.g., The Pilot">
          </div>
          <div class="form-group">
            <label for="episode_overview_${episodeCount}">Episode Overview:</label>
            <textarea id="episode_overview_${episodeCount}" name="episode_overview[]" placeholder="Brief summary of the episode"></textarea>
          </div>
          <div class="form-group">
            <label for="episode_link_480p_${episodeCount}">480p Download Link:</label>
            <input type="text" id="episode_link_480p_${episodeCount}" name="episode_link_480p[]" placeholder="https://example.com/episode_480p">
          </div>
          <div class="form-group">
            <label for="episode_link_720p_${episodeCount}">720p Download Link:</label>
            <input type="text" id="episode_link_720p_${episodeCount}" name="episode_link_720p[]" placeholder="https://example.com/episode_720p">
          </div>
          <div class="form-group">
            <label for="episode_link_1080p_${episodeCount}">1080p Download Link:</label>
            <input type="text" id="episode_link_1080p_${episodeCount}" name="episode_link_1080p[]" placeholder="https://example.com/episode_1080p">
          </div>
        </div>
      `;
      episodeContainer.insertAdjacentHTML('beforeend', newEpisodeHtml);
    });
  });
</script>
</head>
<body>
<header>
  <a href="{{ url_for('admin') }}" class="back-button">Back to Admin</a>
  <h1>Edit Content</h1>
</header>
<main>
  <h2>Edit "{{ movie.title }}"</h2>
  <form method="POST">
    <div class="form-container">
      <div class="form-group">
        <label for="title">Title:</label>
        <input type="text" id="title" name="title" value="{{ movie.title }}" required>
      </div>
      <div class="form-group">
        <label for="content_type">Content Type:</label>
        <select id="content_type" name="content_type" onchange="showHideFields()">
          <option value="movie" {% if movie.type == 'movie' %}selected{% endif %}>Movie</option>
          <option value="series" {% if movie.type == 'series' %}selected{% endif %}>Series</option>
        </select>
      </div>
      <div class="form-group">
        <label for="quality">Quality Tag (e.g., HD, WEB-DL, BluRay):</label>
        <input type="text" id="quality" name="quality" value="{{ movie.quality | default('') }}" placeholder="e.g., HD">
      </div>
      <div class="form-group">
        <label for="top_label">Top Label (Optional, e.g., Featured):</label>
        <input type="text" id="top_label" name="top_label" value="{{ movie.top_label | default('') }}" placeholder="e.g., Featured">
      </div>
      <div class="form-group">
        <label for="overview">Overview (from TMDb or manual):</label>
        <textarea id="overview" name="overview" placeholder="A brief description of the movie/series. Automatically fetched from TMDb if left empty.">{{ movie.overview | default('No overview available.') }}</textarea>
      </div>
      <div class="form-group">
        <label for="poster_url">Poster URL (from TMDb or manual):</label>
        <input type="text" id="poster_url" name="poster_url" value="{{ movie.poster | default('') }}" placeholder="Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="year">Release Year (from TMDb or manual):</label>
        <input type="text" id="year" name="year" value="{{ movie.year | default('N/A') }}" placeholder="e.g., 2023. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="original_language">Original Language (from TMDb or manual):</label>
        <input type="text" id="original_language" name="original_language" value="{{ movie.original_language | default('N/A') }}" placeholder="e.g., en, es. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="form-group">
        <label for="genres">Genres (comma-separated, from TMDb or manual):</label>
        <input type="text" id="genres" name="genres" value="{{ movie.genres | join(', ') if movie.genres else '' }}" placeholder="e.g., Action, Sci-Fi. Automatically fetched from TMDb if left empty.">
      </div>
      <div class="checkbox-group">
          <input type="checkbox" id="is_trending" name="is_trending" value="true" {% if movie.is_trending %}checked{% endif %}>
          <label for="is_trending">Mark as Trending (overrides Quality tag to TRENDING)</label>
      </div>
      <div class="checkbox-group">
          <input type="checkbox" id="is_coming_soon" name="is_coming_soon" value="true" {% if movie.is_coming_soon %}checked{% endif %}>
          <label for="is_coming_soon">Mark as Coming Soon</label>
      </div>
    </div>

    <div id="movie_fields">
      <h3>Movie Download Links</h3>
      <div class="form-group">
        <label for="link_480p">480p Download Link:</label>
        <input type="text" id="link_480p" name="link_480p" value="{% for link in movie.links if link.quality == '480p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/movie_480p.mp4">
      </div>
      <div class="form-group">
        <label for="link_720p">720p Download Link:</label>
        <input type="text" id="link_720p" name="link_720p" value="{% for link in movie.links if link.quality == '720p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/movie_720p.mp4">
      </div>
      <div class="form-group">
        <label for="link_1080p">1080p Download Link:</label>
        <input type="text" id="link_1080p" name="link_1080p" value="{% for link in movie.links if link.quality == '1080p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/movie_1080p.mp4">
      </div>
    </div>

    <div id="episode_fields" style="display: none;">
      <div class="episode-fields">
        <h4>Series Episodes</h4>
        <div id="episodes_container">
          {% if movie.type == 'series' and movie.episodes %}
            {% for episode in movie.episodes %}
              <div class="episode-item">
                <button type="button" class="remove-episode" onclick="this.closest('.episode-item').remove()">X</button>
                <div class="form-group">
                  <label for="episode_number_{{ loop.index }}">Episode Number:</label>
                  <input type="number" id="episode_number_{{ loop.index }}" name="episode_number[]" value="{{ episode.episode_number | default(loop.index) }}" required>
                </div>
                <div class="form-group">
                  <label for="episode_title_{{ loop.index }}">Episode Title:</label>
                  <input type="text" id="episode_title_{{ loop.index }}" name="episode_title[]" value="{{ episode.title | default('') }}" placeholder="e.g., The Pilot">
                </div>
                <div class="form-group">
                  <label for="episode_overview_{{ loop.index }}">Episode Overview:</label>
                  <textarea id="episode_overview_{{ loop.index }}" name="episode_overview[]" placeholder="Brief summary of the episode">{{ episode.overview | default('') }}</textarea>
                </div>
                <div class="form-group">
                  <label for="episode_link_480p_{{ loop.index }}">480p Download Link:</label>
                  <input type="text" id="episode_link_480p_{{ loop.index }}" name="episode_link_480p[]" value="{% for link in episode.links if link.quality == '480p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/episode_480p">
                </div>
                <div class="form-group">
                  <label for="episode_link_720p_{{ loop.index }}">720p Download Link:</label>
                  <input type="text" id="episode_link_720p_{{ loop.index }}" name="episode_link_720p[]" value="{% for link in episode.links if link.quality == '720p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/episode_720p">
                </div>
                <div class="form-group">
                  <label for="episode_link_1080p_{{ loop.index }}">1080p Download Link:</label>
                  <input type="text" id="episode_link_1080p_{{ loop.index }}" name="episode_link_1080p[]" value="{% for link in episode.links if link.quality == '1080p' %}{{ link.url }}{% endfor %}" placeholder="https://example.com/episode_1080p">
                </div>
              </div>
            {% endfor %}
          {% else %}
             <div class="episode-item">
                <button type="button" class="remove-episode" onclick="this.closest('.episode-item').remove()">X</button>
                <div class="form-group">
                  <label for="episode_number_1">Episode Number:</label>
                  <input type="number" id="episode_number_1" name="episode_number[]" value="1" required>
                </div>
                <div class="form-group">
                  <label for="episode_title_1">Episode Title:</label>
                  <input type="text" id="episode_title_1" name="episode_title[]" placeholder="e.g., The Pilot">
                </div>
                <div class="form-group">
                  <label for="episode_overview_1">Episode Overview:</label>
                  <textarea id="episode_overview_1" name="episode_overview[]" placeholder="Brief summary of the episode"></textarea>
                </div>
                <div class="form-group">
                  <label for="episode_link_480p_1">480p Download Link:</label>
                  <input type="text" id="episode_link_480p_1" name="episode_link_480p[]" placeholder="https://example.com/episode_480p">
                </div>
                <div class="form-group">
                  <label for="episode_link_720p_1">720p Download Link:</label>
                  <input type="text" id="episode_link_720p_1" name="episode_link_720p[]" placeholder="https://example.com/episode_720p">
                </div>
                <div class="form-group">
                  <label for="episode_link_1080p_1">1080p Download Link:</label>
                  <input type="text" id="episode_link_1080p_1" name="episode_link_1080p[]" placeholder="https://example.com/episode_1080p">
                </div>
              </div>
          {% endif %}
        </div>
        <button type="button" id="add_episode" class="add-episode-btn">Add Another Episode</button>
      </div>
    </div>

    <button type="submit" class="btn-submit">Update Content</button>
  </form>
</main>
</body>
</html>
"""

# Index HTML (Home Page)
index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MovieZone</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #1a1a1a; color: #f0f0f0; }
  header { background-color: #2a2a2a; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); }
  header h1 { color: #007bff; margin: 0; font-size: 32px; }
  .search-container { display: flex; gap: 10px; }
  .search-container input { padding: 10px 15px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 16px; width: 250px; }
  .search-container button { padding: 10px 15px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s ease; }
  .search-container button:hover { background-color: #0056b3; }
  main { padding: 20px; max-width: 1200px; margin: 20px auto; }
  .filters { background-color: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 25px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; justify-content: center; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
  .filters label { margin-right: 10px; color: #ccc; font-weight: bold; }
  .filters select { padding: 8px 12px; border: 1px solid #444; border-radius: 5px; background-color: #333; color: #f0f0f0; font-size: 15px; cursor: pointer; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20256%20256%22%3E%3Cpath%20fill%3D%22%23cccccc%22%20d%3D%22M208%2080l-80%2080-80-80z%22%2F%3E%3C%2Fsvg%3E'); background-repeat: no-repeat; background-position: right 10px center; background-size: 12px; }
  .filters select:focus { outline: none; border-color: #007bff; box-shadow: 0 0 5px rgba(0, 123, 255, 0.5); }
  .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 25px; }
  .movie-card { background-color: #2a2a2a; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4); text-decoration: none; color: #f0f0f0; transition: transform 0.2s ease, box-shadow 0.2s ease; position: relative; }
  .movie-card:hover { transform: translateY(-5px); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6); }
  .movie-card img { width: 100%; height: 270px; object-fit: cover; display: block; border-bottom: 1px solid #333; }
  .movie-card .info { padding: 15px; }
  .movie-card .info h3 { font-size: 18px; margin: 0 0 8px 0; color: #007bff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .movie-card .info p { font-size: 14px; margin: 0; color: #ccc; }
  .badge { position: absolute; top: 10px; right: 10px; background-color: #007bff; color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; }
  .badge.trending { background-color: #ffc107; color: #333; }
  .coming-soon-badge { position: absolute; top: 10px; right: 10px; background-color: #ff6347; color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; }
  
  /* Placeholder for missing poster */
  .no-image-placeholder {
    width: 100%;
    height: 270px;
    background-color: #333;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #777;
    font-size: 16px;
    text-align: center;
    border-bottom: 1px solid #444;
  }

  /* Bottom Navigation */
  .bottom-nav { background-color: #2a2a2a; padding: 15px 30px; text-align: center; box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.4); margin-top: 30px; }
  .bottom-nav a { color: #007bff; text-decoration: none; margin: 0 15px; font-size: 18px; transition: color 0.3s ease; }
  .bottom-nav a:hover { color: #0056b3; }

  /* Responsive Adjustments */
  @media (max-width: 768px) {
    header { flex-direction: column; text-align: center; }
    header h1 { margin-bottom: 15px; }
    .search-container { flex-direction: column; align-items: center; width: 100%; }
    .search-container input { width: calc(100% - 30px); margin-bottom: 10px; }
    .search-container button { width: 100%; }
    .movie-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
    .movie-card img, .no-image-placeholder { height: 220px; }
    .filters { flex-direction: column; align-items: stretch; }
    .filters select { width: 100%; margin-bottom: 10px; }
  }
  @media (max-width: 480px) {
    main { padding: 15px; }
    .movie-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 15px; }
    .movie-card img, .no-image-placeholder { height: 180px; }
    .movie-card .info h3 { font-size: 16px; }
    .movie-card .info p { font-size: 12px; }
  }
</style>
</head>
<body>
<header>
  <h1>MovieZone</h1>
  <div class="search-container">
    <form method="GET" action="{{ url_for('home') }}" style="display: flex; gap: 10px; width: 100%;">
      <input type="text" name="q" placeholder="Search movies or series..." value="{{ search_query if search_query }}" style="flex-grow: 1;">
      <button type="submit"><i class="fas fa-search"></i></button>
    </form>
  </div>
</header>
<main>
  <div class="filters">
    <form method="GET" action="{{ url_for('home') }}" id="filter-form">
        <label for="type_filter">Type:</label>
        <select name="type" id="type_filter" onchange="document.getElementById('filter-form').submit()">
            <option value="all" {% if content_type_filter == 'all' %}selected{% endif %}>All</option>
            <option value="movie" {% if content_type_filter == 'movie' %}selected{% endif %}>Movies</option>
            <option value="series" {% if content_type_filter == 'series' %}selected{% endif %}>Series</option>
        </select>

        <label for="genre_filter">Genre:</label>
        <select name="genre" id="genre_filter" onchange="document.getElementById('filter-form').submit()">
            <option value="all" {% if genre_filter == 'all' %}selected{% endif %}>All Genres</option>
            {% for genre in unique_genres %}
                <option value="{{ genre }}" {% if genre_filter == genre %}selected{% endif %}>{{ genre }}</option>
            {% endfor %}
        </select>

        <label for="lang_filter">Language:</label>
        <select name="lang" id="lang_filter" onchange="document.getElementById('filter-form').submit()">
            <option value="all" {% if language_filter == 'all' %}selected{% endif %}>All Languages</option>
            {% for lang in unique_languages %}
                <option value="{{ lang.lower() }}" {% if language_filter == lang.lower() %}selected{% endif %}>{{ lang }}</option>
            {% endfor %}
        </select>

        <label for="sort_by">Sort By:</label>
        <select name="sort" id="sort_by" onchange="document.getElementById('filter-form').submit()">
            <option value="latest" {% if sort_by == 'latest' %}selected{% endif %}>Latest</option>
            <option value="popular" {% if sort_by == 'popular' %}selected{% endif %}>Popular</option>
        </select>
        {% if search_query %}<input type="hidden" name="q" value="{{ search_query }}">{% endif %}
    </form>
  </div>
  <div class="movie-grid">
    {% if movies %}
      {% for movie in movies %}
        <a href="{{ url_for('movie_detail', movie_id=movie._id) }}" class="movie-card">
          {% if movie.poster %}
            <img src="{{ movie.poster }}" alt="{{ movie.title }}">
          {% else %}
            <div class="no-image-placeholder">No Poster</div>
          {% endif %}
          {% if movie.is_coming_soon %}
              <div class="coming-soon-badge">COMING SOON</div>
          {% elif movie.quality %}
            <div class="badge {% if movie.quality == 'TRENDING' %}trending{% endif %}">{{ movie.quality }}</div>
          {% endif %}
          <div class="info">
            <h3>{{ movie.title }}</h3>
            <p>{{ movie.get('year', 'N/A') }} - {{ movie.type | title }}</p>
            {% if movie.vote_average %}
                <p>Rating: {{ "%.1f"|format(movie.vote_average) }}/10 <i class="fas fa-star" style="color:#FFD700;"></i></p>
            {% endif %}
          </div>
        </a>
      {% endfor %}
    {% else %}
      <p style="text-align:center; grid-column: 1 / -1; color:#999;">No content found matching your criteria.</p>
    {% endif %}
  </div>
</main>
<nav class="bottom-nav">
  <a href="{{ url_for('home') }}">Home</a>
  <a href="{{ url_for('admin') }}">Admin</a>
</nav>
</body>
</html>
"""

# Detail HTML (Updated for Trailer)
detail_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{ movie.title if movie else "Content Not Found" }} - MovieZone Details</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #1a1a1a; color: #f0f0f0; }
  header { background-color: #2a2a2a; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4); }
  header h1 { color: #007bff; margin: 0; font-size: 28px; }
  .back-button { background-color: #555; color: white; padding: 10px 18px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s ease; text-decoration: none; display: flex; align-items: center; gap: 5px; }
  .back-button:hover { background-color: #666; }
  main { padding: 20px; max-width: 1000px; margin: 20px auto; background-color: #2a2a2a; border-radius: 10px; box-shadow: 0 0 15px rgba(0, 0, 0, 0.5); }

  .movie-detail-container { display: flex; flex-direction: column; gap: 25px; }
  .main-info { display: flex; gap: 25px; flex-wrap: wrap; }
  .detail-poster-wrapper { flex-shrink: 0; position: relative; width: 250px; height: 375px; background-color: #333; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
  .detail-poster { width: 100%; height: 100%; object-fit: cover; display: block; }
  .detail-info { flex-grow: 1; min-width: 280px; }
  .detail-title { color: #007bff; font-size: 36px; margin: 0 0 15px 0; font-weight: 700; }
  .detail-meta { margin-bottom: 20px; color: #ccc; font-size: 16px; display: flex; flex-wrap: wrap; gap: 15px; }
  .detail-meta span { background-color: #333; padding: 8px 12px; border-radius: 5px; display: flex; align-items: center; gap: 5px;}
  .detail-overview { line-height: 1.6; color: #ddd; font-size: 17px; }

  .download-section { margin-top: 30px; background: #1f1f1f; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
  .download-section h3 { font-size: 24px; font-weight: 700; color: #007bff; margin-bottom: 20px; }
  .download-links { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
  .download-button { background-color: #28a745; color: white; padding: 12px 18px; border-radius: 5px; text-decoration: none; text-align: center; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 17px; font-weight: bold; transition: background-color 0.3s ease, transform 0.2s ease; }
  .download-button:hover { background-color: #218838; transform: translateY(-2px); }
  .no-links { color: #999; text-align: center; padding: 10px; }

  /* Episode list for series */
  .episode-list { margin-top: 30px; background: #1f1f1f; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
  .episode-list h3 { font-size: 24px; font-weight: 700; color: #007bff; margin-bottom: 20px; }
  .episode-item-detail { background-color: #333; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
  .episode-item-detail h4 { color: #ffc107; margin-top: 0; margin-bottom: 10px; font-size: 20px; }
  .episode-item-detail p { margin-bottom: 10px; color: #ddd; line-height: 1.5; }
  .episode-item-detail .download-links { margin-top: 10px; }

  .badge { position: absolute; top: 10px; right: 10px; background-color: #007bff; color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; z-index: 10; }
  .badge.trending { background-color: #ffc107; color: #333; }
  .coming-soon-badge { position: absolute; top: 10px; right: 10px; background-color: #ff6347; color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; font-weight: bold; z-index: 10; }
  .detail-poster-wrapper .no-image-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: #777; font-size: 20px; background-color: #333; border-radius: 8px;}

  /* Trailer Section Styles */
  .trailer-section {
    width: 100%;
    margin-top: 30px;
    background: #1f1f1f;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    text-align: center;
  }
  .trailer-section h3 {
    font-size: 24px;
    font-weight: 700;
    color: #007bff; /* Blue color for heading */
    margin-bottom: 20px;
  }
  .trailer-container {
    position: relative;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
    height: 0;
    overflow: hidden;
    margin-bottom: 20px;
    border-radius: 8px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
  }
  .trailer-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: none;
  }
  .no-trailer-message {
      color: #999;
      font-size: 16px;
      text-align: center;
      padding: 10px;
  }

  /* Bottom Navigation */
  .bottom-nav { background-color: #2a2a2a; padding: 15px 30px; text-align: center; box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.4); margin-top: 30px; }
  .bottom-nav a { color: #007bff; text-decoration: none; margin: 0 15px; font-size: 18px; transition: color 0.3s ease; }
  .bottom-nav a:hover { color: #0056b3; }

  /* Responsive Adjustments for Detail Page */
  @media (max-width: 768px) {
    .main-info { flex-direction: column; align-items: center; }
    .detail-poster-wrapper { width: 80%; max-width: 300px; height: 450px; }
    .detail-title { font-size: 30px; text-align: center; }
    .detail-meta { justify-content: center; text-align: center; }
    .detail-overview { text-align: center; }
    .trailer-section h3, .download-section h3, .episode-list h3 { font-size: 20px; }
    .download-links { grid-template-columns: 1fr; }
  }
  @media (max-width: 480px) {
      main { padding: 15px; }
      .detail-poster-wrapper { width: 95%; height: 400px; }
      .detail-title { font-size: 24px; }
      .detail-meta span { font-size: 14px; padding: 6px 10px; }
      .detail-overview { font-size: 15px; }
      .trailer-section h3, .download-section h3, .episode-list h3 { font-size: 18px; }
      .download-button { font-size: 15px; padding: 10px 15px; }
      header { flex-direction: column; align-items: flex-start; }
      header h1 { margin-top: 10px; font-size: 24px; }
      .back-button { margin-bottom: 10px; }
  }
</style>
</head>
<body>
<header>
  <a href="{{ url_for('home') }}" class="back-button"><i class="fas fa-arrow-left"></i> Back</a>
  <h1>MovieZone</h1>
</header>
<main>
  {% if movie %}
  <div class="movie-detail-container">
    <div class="main-info">
        <div class="detail-poster-wrapper">
            {% if movie.poster %}
              <img class="detail-poster" src="{{ movie.poster }}" alt="{{ movie.title }}">
            {% else %}
              <div class="no-image-placeholder">No Poster</div>
            {% endif %}
            {% if movie.is_coming_soon %}
                <div class="coming-soon-badge">COMING SOON</div>
            {% elif movie.quality %}
              <div class="badge {% if movie.quality == 'TRENDING' %}trending{% endif %}">{{ movie.quality }}</div>
            {% endif %}
        </div>
        <div class="detail-info">
          <h2 class="detail-title">{{ movie.title }}</h2>
          <div class="detail-meta">
              {% if movie.release_date %}<span><i class="fas fa-calendar-alt"></i> <strong>Release:</strong> {{ movie.release_date }}</span>{% endif %}
              {% if movie.vote_average %}<span><i class="fas fa-star"></i> <strong>Rating:</strong> {{ "%.1f"|format(movie.vote_average) }}/10</span>{% endif %}
              {% if movie.original_language %}<span><i class="fas fa-language"></i> <strong>Language:</strong> {{ movie.original_language | upper }}</span>{% endif %}
              {% if movie.genres %}<span><i class="fas fa-tags"></i> <strong>Genres:</strong> {{ movie.genres | join(', ') }}</span>{% endif %}
          </div>
          <p class="detail-overview">{{ movie.overview }}</p>
        </div>
    </div>
    
    {# NEW: TRAILER SECTION #}
    <div class="trailer-section">
        <h3>Official Trailer</h3>
        {% if movie.trailer_key %}
            <div class="trailer-container">
                <iframe 
                    src="https://www.youtube.com/embed/{{ movie.trailer_key }}?autoplay=0&controls=1&showinfo=0&rel=0" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen>
                </iframe>
            </div>
        {% else %}
            <p class="no-trailer-message">No trailer available for this content.</p>
        {% endif %}
    </div>

    {% if movie.type == 'movie' %}
      <div class="download-section">
        <h3>Download Links</h3>
        <div class="download-links">
          {% if movie.links %}
            {% for link in movie.links %}
              <a href="{{ link.url }}" class="download-button" target="_blank" rel="noopener noreferrer">
                <i class="fas fa-download"></i> Download {{ link.quality }}
              </a>
            {% endfor %}
          {% else %}
            <p class="no-links">No download links available for this movie yet.</p>
          {% endif %}
        </div>
      </div>
    {% elif movie.type == 'series' %}
      <div class="episode-list">
        <h3>Episodes</h3>
        {% if movie.episodes %}
          {% for episode in movie.episodes %}
            <div class="episode-item-detail">
              <h4>Episode {{ episode.episode_number }}: {{ episode.title }}</h4>
              <p>{{ episode.overview }}</p>
              <div class="download-links">
                {% if episode.links %}
                  {% for link in episode.links %}
                    <a href="{{ link.url }}" class="download-button" target="_blank" rel="noopener noreferrer">
                      <i class="fas fa-download"></i> Download {{ link.quality }}
                    </a>
                  {% endfor %}
                {% else %}
                  <p class="no-links">No download links available for this episode yet.</p>
                {% endif %}
              </div>
            </div>
          {% endfor %}
        {% else %}
          <p class="no-links">No episodes available for this series yet.</p>
        {% endif %}
      </div>
    {% endif %}

  </div>
  {% else %}
    <p style="text-align:center; color:#999; margin-top: 40px;">Content not found.</p>
  {% endif %}
</main>
<nav class="bottom-nav">
  <a href="{{ url_for('home') }}">Home</a>
  <a href="{{ url_for('admin') }}">Admin</a>
</nav>
</body>
</html>
"""

# --- Initial Admin User Setup (Run once if needed) ---
@app.route('/setup_admin')
def setup_admin():
    if users.count_documents({}) == 0:
        default_username = "admin"
        default_password = "admin_password" # Change this to a strong password!
        hashed_pw = hash_password(default_password)
        users.insert_one({"username": default_username, "password_hash": hashed_pw})
        return f"Default admin user '{default_username}' created. Please change the password immediately! Then go to /login"
    return "Admin user already exists."

if __name__ == '__main__':
    # For initial setup: uncomment the line below and run once.
    # After setup, you can comment it out or remove it.
    # print(hash_password("your_new_admin_password")) # Use this to generate a hash for a new password

    # Ensure the admin user exists (simple check for development)
    if users.count_documents({}) == 0:
        print("No admin user found. Creating a default 'admin' user with password 'admin_password'.")
        print("Please change this password immediately after logging in!")
        users.insert_one({"username": "admin", "password_hash": hash_password("admin_password")})

    app.run(debug=True, host='0.0.0.0', port=5000)

