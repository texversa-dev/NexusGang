import os
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION: LOAD FROM .env ---
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY not found. Check your .env file.")

# GEMINI API CLIENT SETUP
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please check your .env file.")
client = genai.Client(api_key=API_KEY)

# Login Credentials
VALID_USERNAME = os.getenv("LOGIN_USERNAME")
VALID_PASSWORD = os.getenv("LOGIN_PASSWORD")


# --- RATE LIMITING CONFIGURATION ---
# IMPORTANT: Adjust these values based on your API usage needs
MAX_DAILY_CALLS = 10  # Set a low limit for testing, increase later (e.g., 500)
CALL_WINDOW_SECONDS = 86400 # 24 hours (60 * 60 * 24)

# Global variables to track usage across the *entire* application instance
global_usage_count = 0
global_reset_time = time.time() + CALL_WINDOW_SECONDS


# --- ROUTES ---

@app.route('/')
def index():
    # ... (login check remains the same) ...
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (login logic remains the same) ...
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid Credentials. Please try again.'
            return render_template('login.html', error=error)
            
    return render_template('login.html')

@app.route('/solve', methods=['POST'])
def solve_query():
    global global_usage_count
    global global_reset_time

    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"answer": "Access Denied. Please log in first."}), 401
        
    data = request.get_json()
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({"answer": "Please enter a question."})

    # --- RATE LIMIT CHECK ---
    current_time = time.time()

    # 1. Reset the counter if the time window has passed
    if current_time >= global_reset_time:
        global_usage_count = 0
        global_reset_time = current_time + CALL_WINDOW_SECONDS
        print("API usage counter reset.")

    # 2. Check if the current limit has been reached
    if global_usage_count >= MAX_DAILY_CALLS:
        # Calculate time remaining until reset
        time_remaining = int(global_reset_time - current_time)
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        
        limit_message = (
            f"API usage limit reached (Max: {MAX_DAILY_CALLS}). "
            f"Please wait {hours} hours and {minutes} minutes."
        )
        return jsonify({"answer": limit_message})
    
    # If limit is not reached, increment the counter
    global_usage_count += 1
    print(f"API Call #{global_usage_count} made.")
    # -------------------------


    # --- API CALL EXECUTION ---
    content = [user_query]
    
    system_instruction = (
        "You are a concise, final answer solver. "
        "When presented with a question, especially a math problem, "
        "respond only with the final answer as a raw mathematical expression. "
        "Do not include step-by-step reasoning, introductory phrases, or concluding sentences. "
        "Crucially, use proper mathematical symbols (e.g., +, -, \\times, \\div, ^ or exponents) for all operations. "
        "Do NOT use the \\boxed command. Use standard parentheses () instead of curly braces {} for grouping."
    )

    config = {
        "system_instruction": system_instruction
    }

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=content,
            config=config
        )
        ai_answer = response.text.strip()
        return jsonify({"answer": ai_answer})

    except APIError as e:
        print(f"Gemini API Error: {e}")
        # NOTE: If a real API error occurs, we don't decrement the counter, 
        # as the call was attempted.
        return jsonify({"answer": "An API error occurred. Unable to process the request."})
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"answer": "A server error occurred. Unable to process the request."})

@app.route('/logout')
def logout():
    # ... (logout logic remains the same) ...
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    # NOTE: Set threaded=False for local testing if using global vars
    app.run(debug=True, threaded=False)