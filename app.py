import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION: LOAD FROM .env ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Check for essential keys
if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY not found. Check your .env file.")

# 1. GEMINI API CLIENT SETUP
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please check your .env file.")
client = genai.Client(api_key=API_KEY)

# 2. LOGIN CREDENTIALS
VALID_USERNAME = os.getenv("LOGIN_USERNAME")
VALID_PASSWORD = os.getenv("LOGIN_PASSWORD")

# --- ROUTES ---

@app.route('/')
def index():
    """Renders the main page, but first checks if the user is logged in."""
    if 'logged_in' not in session or not session['logged_in']:
        # If not logged in, redirect them to the login page
        return redirect(url_for('login'))
    
    # If logged in, show the AI solver template
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles the login form."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check credentials loaded from .env
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid Credentials. Please try again.'
            return render_template('login.html', error=error)
            
    # For GET requests, show the login form
    return render_template('login.html')

@app.route('/solve', methods=['POST'])
def solve_query():
    """Handles the user's request, but only if they are logged in."""
    # Security check for session
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"answer": "Access Denied. Please log in first."}), 401
        
    data = request.get_json()
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({"answer": "Please enter a question or equation."})

    try:
        # Call the Gemini API
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[user_query]
        )
        ai_answer = response.text.strip()
        return jsonify({"answer": ai_answer})

    except APIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify({"answer": "An API error occurred. Check the server console."})
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"answer": "A server error occurred. Unable to process the request."})

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)