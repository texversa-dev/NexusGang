import os
import io
import base64
from PIL import Image
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
    image_data_b64 = data.get('image_data')

    if not user_query and not image_data_b64:
        return jsonify({"answer": "Please enter a question or upload an image."})

    # --- 1. Prepare Content for Gemini ---
    content = []
    
    if image_data_b64:
        try:
            image_bytes = base64.b64decode(image_data_b64)
            img = Image.open(io.BytesIO(image_bytes))
            
            content.append(img)
        except Exception as e:
            print(f"Image Decoding Error: {e}")
            return jsonify({"answer": "Error processing image. Is it a valid image file?"})

    if user_query:
        content.append(user_query)
    
    # --- 2. Define System Instruction (To enforce concise answers) ---
    system_instruction = (
        "You are a concise, final answer solver. "
        "When presented with a question, especially a math problem, "
        "respond only with the final answer. "
        "Do not include step-by-step reasoning, introductory phrases, or concluding sentences. "
        "If the answer is a mathematical expression, use the correct LaTeX formatting (e.g., \\boxed{\\text{your answer}})."
    )

    try:
        # Call the Gemini API with the new instruction
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=content,
            system_instruction=system_instruction
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