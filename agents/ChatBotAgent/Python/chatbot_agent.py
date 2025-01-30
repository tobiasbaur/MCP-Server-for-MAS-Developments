# Python/api_server.py
from pathlib import Path

from flask import Flask, request, jsonify
import logging
import json
import threading
from waitress import serve
from flask_cors import CORS  # Import von Flask-CORS
from ...AgentInterface.Python.agent import PrivateGPTAgent, GroupValidationError
from ...AgentInterface.Python.config import Config, ConfigError
from ...AgentInterface.Python.language import languages
import os
import platform
import socket

app = Flask(__name__)

# Konfiguration von CORS
# Erlaubt spezifische Origins, z.B., 'http://localhost:5500'
# Ändern Sie die Origins entsprechend Ihrer tatsächlichen Frontend-URL
CORS(app, resources={r"/*": {"origins": "http://192.168.100.185:5500"}}, supports_credentials=False)



# Konfiguration laden
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "config.json")
    config = Config(config_file=config_file, required_fields=["server_ip", "server_port", "email", "password"])
except ConfigError as e:
    logging.error(f"Configuration Error: {e}")
    exit(1)

# Initialisierung des PrivateGPTAgent
try:
    agent = PrivateGPTAgent(config)
except GroupValidationError as e:
    logging.error(f"Group Validation Error: {e}")
    exit(1)
except Exception as e:
    logging.error(f"Unexpected Error during Agent Initialization: {e}")
    exit(1)

# Laden des API-Schlüssels
api_key = config.get("api_key", "default_api_key")  # Stellen Sie sicher, dass ein API-Key gesetzt ist

# Konfigurieren von Logging für Flask (Werkzeug)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)  # Nur Fehler, keine Warnungen
werkzeug_handler = logging.FileHandler('flask.log')  # Logs in separate Datei
werkzeug_handler.setLevel(logging.ERROR)
werkzeug_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
werkzeug_handler.setFormatter(werkzeug_formatter)
werkzeug_logger.addHandler(werkzeug_handler)

# Allgemeine Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)

def display_startup_header():
    server_ip = config.get("api_ip", "0.0.0.0")
    server_port = config.get("api_port", 8000)
    api_key_status = "✔️ Set" if api_key != "default_api_key" else "❌ Not Set"

    header = f"""
    ────────────────────────────────────────────────
    Fujitsu PrivateGPT ChatBot Agent - Startup
    ────────────────────────────────────────────────
    System Information:
    - Hostname      : {socket.gethostname()}
    - Operating Sys : {platform.system()} {platform.release()}
    - Python Version: {platform.python_version()}

    Server Configuration:
    - API Endpoint  : http://{server_ip}:{server_port}
    - API Key Status: {api_key_status}

    Logs:
    - Flask Log     : flask.log
    - Agent Log     : agent.log
    ────────────────────────────────────────────────
    🚀 Ready to serve requests!
    """
    print(header)
    print(f"Current working directory: {os.getcwd()}")


@app.before_request
def authenticate():
    # Erlaube OPTIONS-Anfragen ohne Authentifizierung
    if request.method == 'OPTIONS':
        return
    if request.endpoint != 'status':  # Optional: Status-Endpoint ohne Auth
        provided_key = request.headers.get('X-API-KEY')
        if not provided_key or provided_key != api_key:
            return jsonify({"error": "Unauthorized"}), 401

@app.route('/ask', methods=['POST'])

def ask():
    """
    Endpoint zum Stellen einer Frage an den Chatbot-Agenten.
    Erwartet ein JSON-Objekt mit dem Schlüssel 'question'.
    Optional können 'usePublic', 'groups' und 'language' angegeben werden.
    """
    data = request.get_json()

    if not data or 'question' not in data:
        return jsonify({"error": "Invalid request. 'question' field is required."}), 400

    question = data['question']
    use_public = data.get('usePublic', False)
    groups = data.get('groups')  # Kann None oder eine Liste sein
    language = data.get('language', 'en')

    # Setzen der Agent-Sprache, falls erforderlich
    if language not in languages:
        language = 'en'
        logging.warning(f"Unsupported language '{language}'. Falling back to English.")

    lang = languages[language]

    # Validierung der Gruppen
    try:
        invalid_groups = agent.validate_groups(groups)
        if invalid_groups:
            return jsonify({"error": f"Invalid groups: {invalid_groups}"}), 400
    except Exception as e:
        logging.error(f"Error during group validation: {e}")
        return jsonify({"error": "Group validation failed."}), 500

    # Abfrage des Agents
    response = agent.query_private_gpt(
        prompt=question,
        use_public=use_public,
        language=language,
        groups=groups  # Kann None oder eine Liste sein
    )

    # Rückgabe der Antwort
    return jsonify(json.loads(response)), 200

@app.route('/logs', methods=['GET'])
def view_logs():
    """
    Endpoint, um das Flask-Log per Browser anzuzeigen.
    """
    try:
        with open('flask.log', 'r') as log_file:
            log_content = log_file.read()
        # Rückgabe des Logs als Text
        return f"<pre>{log_content}</pre>", 200  # <pre> für eine schönere Darstellung
    except FileNotFoundError:
        return "Log file not found.", 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500
        
@app.route('/status', methods=['GET'])
def status():
    """
    Endpoint zur Überprüfung des Serverstatus.
    """
    return jsonify({"status": "PrivateGPT Agent is running."}), 200

def run_api_server():
    # Flask-Server konfigurieren
    server_ip = config.get("api_ip", "0.0.0.0")
    server_port = config.get("api_port", 5001)

    serve(app, host=server_ip, port=int(server_port))

if __name__ == '__main__':
    # Starten des API-Servers in einem separaten Daemon-Thread
    api_thread = threading.Thread(target=run_api_server)
    api_thread.daemon = True  # Daemon-Thread
    api_thread.start()

    # Call this function right before the server starts
    display_startup_header()

    # Starten des manuellen Chat-Interfaces
    agent.run()


