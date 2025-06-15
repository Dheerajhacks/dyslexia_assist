from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
import os
import pyttsx3
import base64
import tempfile
import random
import google.generativeai as genai
from pymongo import MongoClient
import re
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'your_secret_key'



client = MongoClient('mongodb://localhost:27017/')
db = client.dyslexia_assistance
progress_collection = db.progress
user_profile = db.user_profile
users_collection = db['users']
logs_collection = db['logs']


load_dotenv()
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

engine = pyttsx3.init()


def save_progress(user_id, module_id, reference_text, incorrect_words, text_done, audio_done):
    progress_data = {
        "user_id": user_id,
        "module_id": module_id,
        "text_done": text_done,
        "audio_done": audio_done,
        "reference_text": reference_text,
        "incorrect_words": incorrect_words,
    }
    progress_collection.insert_one(progress_data)

def get_all_progress(user_id):
    return list(progress_collection.find({"user_id": user_id}).sort("module_id", 1))


def get_latest_progress(user_id):
    return progress_collection.find_one({"user_id": user_id}, sort=[('_id', -1)])


def update_user_capability(user_id, reference_text, incorrect_words):
    total_words = len(reference_text.split())
    incorrect_count = len(incorrect_words)

    profile = user_profile.find_one({"user_id": user_id}) or {
        "user_id": user_id,
        "capability_score": 1.0,
        "history": {
            "total_attempts": 0,
            "total_words": 0,
            "total_errors": 0
        }
    }

    profile["history"]["total_attempts"] += 1
    profile["history"]["total_words"] += total_words
    profile["history"]["total_errors"] += incorrect_count

    total_words = profile["history"]["total_words"]
    total_errors = profile["history"]["total_errors"]
    profile["capability_score"] = max(0.1, round(1 - (total_errors / total_words), 2))

    user_profile.update_one({"user_id": user_id}, {"$set": profile}, upsert=True)


def generate_custom_paragraph(capability_score):
    if capability_score < 0.92:
        prompt = "Generate an intermediate English paragraph with slightly challenging vocabulary. Keep it around 3-4 sentences"
    elif capability_score < 0.89:
        prompt = "Generate a simple English paragraph using basic vocabulary and short sentences."
    else:
        prompt = "Write a very simple English paragraph using short, easy words."

    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content([prompt])
        return response.text.strip()
    except Exception as e:
        print("Gemini API error:", e)
        return "The sun rises in the east and sets in the west."

@app.route('/homepage')
def homepage():
    return render_template('homepage.html')

@app.route('/module')
def module():
    user_id = session.get('user_id', 'guest')
    print(user_id)
    user = user_profile.find_one({'user_id': user_id}) or {"capability_score": 1.0}
    capability_score = user.get('capability_score', 1.0)
    paragraph = generate_custom_paragraph(capability_score)

    save_progress(user_id, module_id=0, reference_text=paragraph, incorrect_words=[], text_done=False, audio_done=False)

    progress_history = get_all_progress(user_id)
    previous_texts = [item['reference_text'] for item in progress_history]

    previous_texts = [
    ref if len(ref) <= 40 else ref[:37] + "..."
    for ref in previous_texts   
    ]

    return render_template('module.html', reference_text=paragraph, module_id=0, previous_texts=previous_texts)


@app.route('/')
def mycourse():
    return render_template('index.html')

@app.route('/history')
def history():
    user_id = session.get('user_id', 'guest')

    user_progress = list(progress_collection.find({"user_id": user_id}))

    # Convert ObjectId to string to make JSON serializable
    for entry in user_progress:
        entry['_id'] = str(entry['_id'])

    user_profile_data = user_profile.find_one({"user_id": user_id})
    capability_score = user_profile_data.get("capability_score", 0) if user_profile_data else 0

    docs = list(progress_collection.find({"user_id": user_id}))  # Convert cursor to list


# Temporary list to store all correct words (in order of appearance)
    correct_words_ordered = []

    for doc in docs:
        incorrect_words = doc.get("incorrect_words", [])
        for word in incorrect_words:
            correct = word.get("correct")
            if correct:
                correct_words_ordered.append(correct.lower().strip())  # Normalize

    # Reverse the list so newest entries come first
    correct_words_ordered.reverse()

    # Now pick unique words in this reversed order
    seen = set()
    unique_correct_words = []
    for word in correct_words_ordered:
        if word not in seen:
            unique_correct_words.append(word)
            seen.add(word)

    # Get the top 10 most recent unique correct words
    top_10_unique_correct = unique_correct_words[:10]

    # Display
    print("Top 10 Unique Corrected Words (Newest First)")
    print("=" * 45)
    for word in top_10_unique_correct:
        print(f"{word:>20}")
    return render_template("history.html",
                           history_list=user_progress,
                           capability_score=capability_score,
                           top_corrected_words=top_10_unique_correct)


@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    data = request.get_json()
    rate = int(data.get('rate', 150))

    user_id = session.get('user_id', 'guest')
    progress = get_latest_progress(user_id)
    text = progress["reference_text"] if progress else "No text available"

    engine.setProperty('rate', rate)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_path = temp_file.name
    engine.save_to_file(text, temp_path)
    engine.runAndWait()

    with open(temp_path, 'rb') as f:
        audio_base64 = base64.b64encode(f.read()).decode('utf-8')
    os.remove(temp_path)
    return jsonify({'audio': f'data:audio/wav;base64,{audio_base64}'})

# def clean_word(word):
#     # Remove punctuation like -, ., ,
#     return re.sub(r'[.,]', '', word.lower())

import difflib

def clean_word(word):
    return ''.join(char.lower() for char in word if char.isalnum())

def compare_texts(user_text, reference_text):
    reference_words = reference_text.split()
    user_words = user_text.split()

    matcher = difflib.SequenceMatcher(None, reference_words, user_words)
    incorrect_words = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            for ref_word, user_word in zip(reference_words[i1:i2], user_words[j1:j2]):
                incorrect_words.append({'user': user_word, 'correct': ref_word})
            
            # Handle length mismatches between segments
            if (i2 - i1) > (j2 - j1):  # Missing user words
                for ref_word in reference_words[i1 + (j2 - j1):i2]:
                    incorrect_words.append({'user': '', 'correct': ref_word})
            elif (j2 - j1) > (i2 - i1):  # Extra user words
                for user_word in user_words[j1 + (i2 - i1):j2]:
                    incorrect_words.append({'user': user_word, 'correct': ''})


    pronunciations = []
    for word in incorrect_words:
        if word['correct']:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_path = temp_file.name
            engine.save_to_file(f" {word['correct']}", temp_path)
            engine.runAndWait()
            with open(temp_path, 'rb') as f:
                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
            os.remove(temp_path)
            pronunciations.append({
                'word': word['correct'],
                'audio': f'data:audio/wav;base64,{audio_base64}'
            })

    return incorrect_words, pronunciations


@app.route('/check_text', methods=['POST'])
def check_text():
    user_id = session.get('user_id', 'guest')
    user_text = request.json.get('text', '')

    progress = get_latest_progress(user_id)
    if not progress:
        return jsonify({'error': 'No reference text found'}), 400

    reference_text = progress["reference_text"]
    incorrect_words, pronunciations = compare_texts(user_text, reference_text)
    print(pronunciations)
    completed = len(incorrect_words) == 0

    save_progress(user_id, 0, reference_text, incorrect_words, text_done=completed, audio_done=progress['audio_done'])
    update_user_capability(user_id, reference_text, incorrect_words)

    return jsonify({
        'incorrect': incorrect_words,
        'pronunciations': pronunciations,
        'completed': completed,
        'points': 10 if completed else 0
    })


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if users_collection.find_one({"email": email}):
            return "User already exists."
        users_collection.insert_one({"email": email, "password": password})
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email, "password": password})
        if user:
            session['user_id'] = user['email']
            return redirect(url_for('homepage'))
        return render_template('login.html', error="Invalid email or password.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    print('logout....')
    return redirect(url_for('login'))


@app.before_request
def load_user():
    session['user_id'] = 'guest'  # Mock user for demonstration

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/sort')
def sort():
    return render_template('sort.html')

@app.route('/match')
def match():
    return render_template('match.html')

@app.route('/context')
def context():
    return render_template('context_exercise.html')


@app.route('/exercise/<exercise_type>')
def exercise(exercise_type):
    sample_words = [
        {"user": "recieve", "correct": "receive"},
        {"user": "definately", "correct": "definitely"},
        {"user": "seperate", "correct": "separate"},
        {"user": "occurence", "correct": "occurrence"},
        {"user": "goverment", "correct": "government"}
    ]

    if exercise_type == "spelling":
        return render_template("spelling_exercise.html", words=sample_words)
    elif exercise_type == "fillblank":
        sentences = [
            {"text": f"The ___ of the event was unexpected.", "answer": word['correct']} for word in sample_words
        ]
        return render_template("fill_blank_exercise.html", sentences=sentences)
    elif exercise_type == "multiplechoice":
        options = [
            {
                "question": word['user'],
                "choices": random.sample([word['correct'], word['user'], word['correct'][::-1], 'random'], k=4),
                "answer": word['correct']
            }
            for word in sample_words
        ]
        return render_template("multiple_choice.html", options=options)
    else:
        return redirect(url_for('home'))

@app.route('/submit/<exercise_type>', methods=['POST'])
def submit(exercise_type):
    user_id = session['user_id']
    answers = request.form.to_dict()
    result = {
        "user_id": user_id,
        "exercise_type": exercise_type,
        "answers": answers
    }
    db.exercise_logs.insert_one(result)
    return redirect(url_for('home'))



if __name__ == '__main__':
    app.run(debug=True)