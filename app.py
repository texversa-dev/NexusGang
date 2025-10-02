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

# --- ROUTES ---

@app.route('/')
def index():
    """Renders the main solver page if logged in, otherwise redirects to login."""
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles the user login form."""
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
    """Handles the user's query by sending it to the Gemini API."""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"answer": "Access Denied. Please log in first."}), 401
        
    data = request.get_json()
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({"answer": "Please enter a question."})

    # --- 1. Prepare Content for Gemini (Text-Only) ---
    content = [user_query]
    
    # --- 2. Define System Instruction & Config (ULTIMATE CONCISENESS) ---
    system_instruction = (
        "You are a concise, final answer solver. "
        "When presented with a question, especially a math problem, "
        "respond only with the final answer as a raw mathematical expression. "
        "Do not include step-by-step reasoning, introductory phrases, or concluding sentences. "
        "Crucially, use proper mathematical symbols (e.g., +, -, \\times, \\div, \^ or exponents) for all operations. "
        "Do NOT use the \\boxed{} command. Use standard parentheses () instead of curly braces {} for grouping."
    )

    # Use the 'config' dictionary to pass system instructions
    config = {
        "system_instruction": system_instruction
    }

    try:
        # Call the Gemini API using the 'config' parameter
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=content,
            config=config
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
    """Removes the logged_in flag from the session."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)