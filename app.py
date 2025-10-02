import os
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai.errors import APIError
from dotenv import load_dotenv # <-- New Import!

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- SECURELY CONFIGURE YOUR GEMINI API KEY ---
# The os.getenv() function retrieves the key from the environment
# which was loaded by load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please check your .env file.")

client = genai.Client(api_key=API_KEY)

# ... rest of your code remains the same ...

@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

# ... the /solve route and main block (if __name__ == '__main__':) remain the same ...