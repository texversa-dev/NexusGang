import os
import requests
from flask import Flask, redirect, request, session, url_for, render_template_string, jsonify
from flask_sqlalchemy import SQLAlchemy

# --- CONFIGURATION (FINAL) ---
CLIENT_ID = "1416882044696395926" 
CLIENT_SECRET = "7vgeQMvrlYzBLLaBeDma8QBU6Qa7LW0a" 
# This MUST match the URI registered in the Discord Developer Portal.
REDIRECT_URI = "https://nexuserlc.xyz/" 

OAUTH_SCOPES = "identify guilds" 
API_BASE_URL = 'https://discord.com/api/v10'

ADMINISTRATOR = 0x8       
MANAGE_GUILD = 0x20       

app = Flask(__name__)
# WARNING: Change this key for production security!
app.secret_key = os.urandom(24) 

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexus_settings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODEL ---
class GuildSettings(db.Model):
    guild_id = db.Column(db.String(30), primary_key=True) 
    welcome_channel_id = db.Column(db.String(30), default='')
    welcome_message = db.Column(db.Text, default='')
    welcome_role = db.Column(db.String(100), default='')
    mod_log_channel_id = db.Column(db.String(30), default='')
    automod_enabled = db.Column(db.Boolean, default=False)
    mute_role = db.Column(db.String(100), default='')
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# --- HELPER FUNCTIONS ---

def get_oauth_url():
    """Generates the Discord OAuth2 authorization URL."""
    return (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={OAUTH_SCOPES.replace(' ', '%20')}"
    )

def fetch_manageable_guilds(access_token):
    """Fetches and filters guilds the user can manage."""
    headers = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(f'{API_BASE_URL}/users/@me/guilds', headers=headers)
    r.raise_for_status()
    guilds = r.json()

    manageable_guilds = []
    for guild in guilds:
        permissions = int(guild.get('permissions', 0))
        if guild['owner'] or (permissions & ADMINISTRATOR) or (permissions & MANAGE_GUILD):
             manageable_guilds.append(guild)
    return manageable_guilds

# --- FLASK ROUTES ---

@app.route("/")
def index_and_callback():
    """
    Handles the index page AND the OAuth2 callback.
    This route is configured to avoid any unnecessary /login redirects.
    """
    code = request.args.get("code")

    if code:
        # 1. OAuth2 Callback logic
        data = {
            'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code',
            'code': code, 'redirect_uri': REDIRECT_URI, 'scope': OAUTH_SCOPES
        }
        
        try:
            r = requests.post(f'{API_BASE_URL}/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            r.raise_for_status()
            token_data = r.json()
            
            session['access_token'] = token_data['access_token']
            # Success: Redirect to dashboard
            return redirect(url_for('dashboard'))
        except requests.exceptions.HTTPError as e:
            return f"Discord OAuth Error: {e.response.text}", 500

    # 2. Index page logic
    if 'access_token' in session:
        return redirect(url_for('dashboard'))
    
    # Show login prompt, linking DIRECTLY to Discord's OAuth URL
    return f"""
        <header style="background-color: #2C2F33; color: white; padding: 20px; text-align: center;">
            <h1>Nexus Dashboard</h1>
        </header>
        <div style="text-align: center; padding: 50px; background-color: #202225; color: #DCDDDE;">
            <h2>Welcome to Nexus!</h2>
            <p>Please log in with Discord to manage your servers.</p>
            <a href="{get_oauth_url()}" style="padding: 12px 25px; background-color: #7289DA; color: white; text-decoration: none; border-radius: 5px; display: inline-block;">
                Login with Discord
            </a>
        </div>
    """


@app.route("/dashboard")
def dashboard():
    """Serves the dashboard content after the user is authenticated."""
    if 'access_token' not in session:
        return redirect(url_for('index_and_callback'))

    try:
        manageable_guilds = fetch_manageable_guilds(session["access_token"])
        
        guild_buttons_html = ""
        first_guild_id = None
        
        for guild in manageable_guilds:
            if not first_guild_id:
                first_guild_id = guild['id']
            
            icon_text = "".join([w[0].upper() for w in guild['name'].split()][:2])
            
            guild_buttons_html += f"""
                <button class="guild-button" onclick="selectServer('{guild['id']}', '{guild['name']}', this)">
                    <span class="guild-icon">{icon_text}</span>
                    {guild['name']}
                </button>
            """
        
        try:
            with open("dashboard.html", "r") as f:
                html_template = f.read()
        except FileNotFoundError:
            return "Error: dashboard.html not found.", 500

        # Inject content and modify display styles
        html_content = html_template.replace('<div id="guild-list"></div>', f'<div id="guild-list">{guild_buttons_html}</div>')
        
        if manageable_guilds:
            html_content = html_content.replace('id="login-prompt"', 'id="login-prompt" style="display: none;"')
            html_content = html_content.replace('id="dashboard-sidebar" style="display: none;"', 'id="dashboard-sidebar"')
            html_content = html_content.replace('id="dashboard-content" style="display: none;"', 'id="dashboard-content"')
            
            # Inject the ID of the first server for initial load
            html_content = html_content.replace(
                '// INITIAL SETUP START',
                f"let initialGuildId = '{first_guild_id}';"
            )

        return render_template_string(html_content)

    except requests.exceptions.HTTPError:
        session.pop('access_token', None)
        return redirect(url_for('index_and_callback'))

@app.route("/logout")
def logout():
    """Clears the session and logs the user out."""
    session.pop('access_token', None)
    return redirect(url_for('index_and_callback'))

# --- API ENDPOINTS ---

@app.route("/api/settings/<guild_id>", methods=["GET"])
def get_settings(guild_id):
    if 'access_token' not in session: return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    try:
        manageable_guilds = fetch_manageable_guilds(session["access_token"])
        if not any(g['id'] == guild_id for g in manageable_guilds):
            return jsonify({"success": False, "error": "Permission denied for this server."}), 403
    except Exception: return jsonify({"success": False, "error": "Token expired or invalid."}), 401

    settings_entry = GuildSettings.query.get(guild_id)
    if not settings_entry:
        return jsonify({"success": True, "settings": GuildSettings().to_dict()})
    
    return jsonify({"success": True, "settings": settings_entry.to_dict()})


@app.route("/api/save_settings", methods=["POST"])
def save_settings_api():
    if 'access_token' not in session: return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    try:
        data = request.json
        guild_id = data.get('guild_id')
        feature = data.get('feature')
        settings = data.get('settings', {})

        if not guild_id: return jsonify({"success": False, "error": "Missing Guild ID"}), 400

        manageable_guilds = fetch_manageable_guilds(session["access_token"])
        if not any(g['id'] == guild_id for g in manageable_guilds):
            return jsonify({"success": False, "error": "Permission denied for this server."}), 403

        settings_entry = GuildSettings.query.get(guild_id)
        if not settings_entry: settings_entry = GuildSettings(guild_id=guild_id)

        if feature == 'welcome':
            settings_entry.welcome_channel_id = settings.get('welcome-channel')
            settings_entry.welcome_message = settings.get('welcome-message')
            settings_entry.welcome_role = settings.get('welcome-role', '')
            
        elif feature == 'moderation':
            settings_entry.mod_log_channel_id = settings.get('mod-log-channel')
            settings_entry.automod_enabled = settings.get('filter-status')
            settings_entry.mute_role = settings.get('mute-role', '')

        db.session.add(settings_entry)
        db.session.commit()
        
        return jsonify({"success": True, "message": f"{feature} settings saved for {guild_id}"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)