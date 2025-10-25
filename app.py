import os
import json
import base64
import time
from urllib.parse import urlencode

from flask import Flask, redirect, request, session, jsonify, send_file
import requests
from flask_session import Session
from dotenv import load_dotenv

from analysis import analyze_moods, generate_template_summary
from utils import token_headers

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "devsecret"
app.config["SESSION_TYPE"] = os.environ.get("SESSION_TYPE", "filesystem")
Session(app)

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REDIRECT_URI = os.environ["SPOTIFY_REDIRECT_URI"]

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Scopes we need for top tracks, user profile, recently played
SCOPES = "user-top-read user-read-private user-read-email"


def _make_auth_header():
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64 = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {b64}", "Content-Type": "application/x-www-form-urlencoded"}


@app.route("/")
def index():
    return "<h3>Spotify Wrapped Backend — /login to start</h3>"


@app.route("/login")
def login():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "show_dialog": "true",
    }
    url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post(SPOTIFY_TOKEN_URL, headers=_make_auth_header(), data=data)
    token_data = resp.json()
    # save tokens in session
    session["token"] = token_data
    session["token"]["created_at"] = int(time.time())
    return redirect(f"{os.environ.get('FRONTEND_URL')}/dashboard")


def refresh_token_if_needed():
    token = session.get("token")
    if not token:
        return False
    expires_in = token.get("expires_in", 3600)
    created = token.get("created_at", 0)
    if int(time.time()) > created + expires_in - 60:
        # refresh
        data = {"grant_type": "refresh_token", "refresh_token": token.get("refresh_token")}
        r = requests.post(SPOTIFY_TOKEN_URL, headers=_make_auth_header(), data=data)
        new = r.json()
        # merge fields
        token.update(new)
        token["created_at"] = int(time.time())
        session["token"] = token
    return True


@app.route("/me")
def me():
    if "token" not in session:
        return redirect("/login")
    refresh_token_if_needed()
    headers = token_headers(session["token"]["access_token"])
    r = requests.get(f"{SPOTIFY_API_BASE}/me", headers=headers)
    return jsonify(r.json())


# Example endpoint: get user's top artists
@app.route("/top/artists")
def top_artists():
    if "token" not in session:
        return redirect("/login")
    refresh_token_if_needed()
    headers = token_headers(session["token"]["access_token"])
    params = {"limit": 20, "time_range": request.args.get("time_range", "medium_term")}
    r = requests.get(f"{SPOTIFY_API_BASE}/me/top/artists", headers=headers, params=params)
    return jsonify(r.json())


# Example: get user's top tracks and audio features and run mood analysis
@app.route("/analyze")
def analyze():
    """
    Returns:
    {
      top_tracks: [...],
      audio_features: {...},
      mood_labels: {...},
      template_summary: "..."
    }
    """
    if "token" not in session:
        return redirect("/login")
    refresh_token_if_needed()
    headers = token_headers(session["token"]["access_token"])

    # 1) fetch top tracks
    params = {"limit": 20, "time_range": request.args.get("time_range", "medium_term")}
    r = requests.get(f"{SPOTIFY_API_BASE}/me/top/tracks", headers=headers, params=params)
    top_tracks = r.json().get("items", [])

    if not top_tracks:
        return jsonify({"error": "no top tracks found"}), 400

    # 2) fetch audio features for these tracks
    ids = ",".join([t["id"] for t in top_tracks])
    rf = requests.get(f"{SPOTIFY_API_BASE}/audio-features", headers=headers, params={"ids": ids})
    audio_features = rf.json().get("audio_features", [])

    # 3) run mood analysis
    mood_labels = analyze_moods(top_tracks, audio_features)

    # 4) template-based summary
    summary = generate_template_summary(top_tracks, mood_labels)

    return jsonify({
        "top_tracks": top_tracks,
        "audio_features": audio_features,
        "mood_labels": mood_labels,
        "template_summary": summary,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
