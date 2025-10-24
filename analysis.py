from collections import Counter
from typing import List, Dict, Any
import random

def analyze_moods(tracks: List[Dict[str, Any]], features: List[Dict[str, Any]]):
    """
    Simple rule-based mood labeling:
    - uses energy, danceability, tempo, valence
    Returns dictionary of aggregated stats and a top mood label
    """
    labels = []
    mapped = []
    for t, f in zip(tracks, features):
        if f is None:
            continue
        energy = f.get("energy", 0)
        dance = f.get("danceability", 0)
        tempo = f.get("tempo", 0)
        valence = f.get("valence", 0)  # happiness

        # rules (tunable)
        if energy > 0.7 and dance > 0.6:
            label = "Energetic"
        elif valence > 0.7 and dance > 0.5:
            label = "Happy"
        elif energy < 0.4 and valence < 0.4:
            label = "Melancholic"
        elif tempo < 70 and valence > 0.5:
            label = "Chill"
        elif dance > 0.7:
            label = "Party"
        else:
            label = "Indie/Alternative"

        mapped.append({"track": t["name"], "artist": t["artists"][0]["name"], "label": label})
        labels.append(label)

    # aggregated
    counter = Counter(labels)
    top_label, _ = counter.most_common(1)[0] if counter else ("Unknown", 0)
    return {"per_track": mapped, "summary_counts": dict(counter), "top_mood": top_label}


# Template-based summary
TEMPLATES = [
    "You were vibing to {top_mood} tracks — {top_artist} dominated your playlists!",
    "It was a {top_mood} year. {top_artist} kept showing up in your top songs.",
    "Major {top_mood} energy: {top_artist} & friends filled your playlists.",
    "Your top vibe was {top_mood}. Biggest artist? {top_artist}.",
]

def generate_template_summary(tracks, mood_info):
    # get most-played artist by frequency in top tracks
    artists = [t["artists"][0]["name"] for t in tracks]
    top_artist = max(set(artists), key=artists.count)
    top_mood = mood_info.get("top_mood", "eclectic")

    template = random.choice(TEMPLATES)
    return template.format(top_mood=top_mood, top_artist=top_artist)
