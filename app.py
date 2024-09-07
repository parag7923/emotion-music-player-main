from flask import Flask, request, jsonify
from flask_cors import CORS
from transformers import pipeline
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
import os
import random
import json
from dotenv import load_dotenv
import uuid
import datetime
import requests
import threading

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()

# Initialize Hugging Face emotion detection model
emotion_detector = pipeline('sentiment-analysis', model='bhadresh-savani/distilbert-base-uncased-finetuned-emotion')

# Spotify API credentials
spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

# Spotify authentication
auth_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
sp = spotipy.Spotify(auth_manager=auth_manager)

# Webhook URL (if applicable)
webhook_url = "http://localhost:8000/callback"  # Replace with your webhook URL if needed

# Function to detect emotion using Hugging Face model
def detect_emotion(text):
    try:
        response = emotion_detector(text)
        emotion = response[0]['label'].lower()
        return emotion
    except Exception as e:
        print(f"Error detecting emotion: {e}")
        return "unknown"

# Function to search for Spotify playlists based on a keyword
def find_playlists_for_keyword(keyword, limit=10):
    try:
        random_queries = [f"{keyword} playlist", f"best {keyword} playlists", f"{keyword} hits"]
        query = random.choice(random_queries)
        results = sp.search(q=query, type='playlist', limit=limit)
        playlists = results['playlists']['items']
        return [{
            'name': playlist['name'],
            'description': playlist['description'],
            'link': playlist['external_urls']['spotify']
        } for playlist in playlists]
    except Exception as e:
        print(f"Error finding playlists: {e}")
        return []

# Function to find playlists based on emotion
def find_playlists_for_emotion(emotion, limit=10):
    emotion_to_query = {
        "joy": "happy",
        "anger": "angry",
        "fear": "fearful",
        "sadness": "sad",
        "surprise": "surprised",
        "disgust": "disgusted",
        "trust": "trusting",
        "anticipation": "anticipating",
        "boredom": "bored",
        "frustration": "frustrated",
        "confusion": "confused",
        "excitement": "excited",
        "contentment": "content",
        "relief": "relieved",
        "nostalgia": "nostalgic",
        "pride": "proud",
        "guilt": "guilty",
        "shame": "ashamed",
        "embarrassment": "embarrassed",
        "hope": "hopeful",
        "unknown": "mood",
        "mixed": "mixed emotions",
        "indifference": "indifferent"
    }

    query = emotion_to_query.get(emotion, "mood")
    
    try:
        random_queries = [f"{query} playlist", f"best {query} playlists", f"{query} hits"]
        query = random.choice(random_queries)
        results = sp.search(q=query, type='playlist', limit=limit)
        playlists = results['playlists']['items']
        return [{
            'name': playlist['name'],
            'description': playlist['description'],
            'link': playlist['external_urls']['spotify']
        } for playlist in playlists]
    except Exception as e:
        print(f"Error finding playlists: {e}")
        return []

# Check if all information is in the request
def check_input_request(request):
    reason = ""
    status = ""
    user_id = request.headers.get('X-User-ID', None)
    if user_id is None or not user_id.strip():
        status = "INVALID_REQUEST"
        reason = "userToken is invalid"
    
    request_id = request.headers.get('x-request-id', None)
    request_data = request.get_json()
    print(request_data)
    
    if request_id is None or not request_id.strip():
        status = "INVALID_REQUEST"
        reason = "requestId is invalid"
    if status != "":
        trace_id = uuid.uuid4().hex
        error_code = {
            "status": status,
            "reason": reason
        }
        response_data = {
            "requestId": request_id,
            "traceId": trace_id,
            "processDuration": -1,
            "isResponseImmediate": True,
            "response": {},
            "errorCode": error_code
        }
        return response_data
    return None

@app.route('/get_playlist', methods=['POST'])
def get_playlist():
    ret = check_input_request(request)
    if ret is not None:
        return jsonify(ret), 400

    data = request.json
    user_text = data.get('text', '')

    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    # Detect emotion from the text
    emotion = detect_emotion(user_text)
    
    # Find playlists based on emotion and keyword
    emotion_playlists = find_playlists_for_emotion(emotion)
    keyword_playlists = find_playlists_for_keyword(user_text)

    # Combine and randomize the playlists
    all_playlists = emotion_playlists + keyword_playlists
    random.shuffle(all_playlists)
    
    # Select up to 4 playlists
    selected_playlists = all_playlists[:4]

    response = {
        "playlists": selected_playlists
    }

    # Send callback if needed
    def send_callback(response):
        callback_message = {
            "apiVersion": "1.0",
            "service": "EmotionMusicPlayer",
            "datetime": datetime.datetime.now().isoformat(),
            "processDuration": 0,
            "taskId": str(uuid.uuid4()),
            "isResponseImmediate": True,
            "response": response,
            "errorCode": {
                "status": "SUCCESS",
                "reason": "Success"
            }
        }
        headers = {
            "Content-Type": "application/json",
            "x-request-id": str(uuid.uuid4()),
            "x-user-id": data.get('user_id', 'anonymous')
        }
        requests.post(webhook_url, json=callback_message, headers=headers)
    
    threading.Thread(target=send_callback, args=(response,)).start()

    return jsonify(response)

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run(debug=True)
