from flask import Flask, request, jsonify
import logging
import json
import threading
from waitress import serve
from flask_cors import CORS
from pathlib import Path
import os
import platform
import socket

# Import der erforderlichen Module/Klassen für den Agenten
from ...AgentInterface.Python.agent import PrivateGPTAgent, GroupValidationError
from ...AgentInterface.Python.config import Config, ConfigError
from ...AgentInterface.Python.language import languages

app = Flask(__name__)

# CORS-Konfiguration (anpassen, falls erforderlich)
#CORS(app, resources={r"/*": {"origins": "http://<YOUR IP>:5500"}}, supports_credentials=False)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# Konfiguration laden – hier sind die Felder "server_ip" und "server_port" nicht mehr erforderlich
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "config.json")
    config = Config(
        config_file=config_file,
        required_fields=["email", "password", "mcp_server", "api_ip", "api_port", "api_key"]
    )
    logging.info(config)
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
api_key = config.get("api_key", "default_api_key")

# Konfiguration des Loggings für Flask (Werkzeug)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)
werkzeug_handler = logging.FileHandler('flask.log')
werkzeug_handler.setLevel(logging.ERROR)
werkzeug_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
werkzeug_handler.setFormatter(werkzeug_formatter)
werkzeug_logger.addHandler(werkzeug_handler)

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

def connect_to_mcp_server():
    """
    Versucht, eine Verbindung zum MCP-Server herzustellen.
    Liest die Serverinformationen ausschließlich aus dem "mcp_server"-Eintrag in der Konfiguration.
    Wird keine Verbindung hergestellt, wird eine Exception geworfen.
    """
    # Lese den mcp_server-Eintrag aus der Konfiguration
    logging.info("DEBUG: MCP Server Config lesen!")
    mcp_config = config.get("mcp_server")
    logging.info("DEBUG: MCP Server Config: %s", mcp_config)
    
    if not mcp_config:
        raise Exception("MCP server configuration is missing in the config file.")
    
    if not isinstance(mcp_config, dict):
        raise Exception("MCP server configuration is not a dictionary: {}".format(mcp_config))
    
    # Lese host und port
    mcp_host = mcp_config.get("host")
    mcp_port = mcp_config.get("port")
    
    logging.info("DEBUG: Loaded MCP host: %s", mcp_host)
    logging.info("DEBUG: Loaded MCP port: %s", mcp_port)
    
    if mcp_host is None or mcp_port is None:
        raise Exception("MCP server host or port is missing in the configuration. Found host: {}, port: {}".format(mcp_host, mcp_port))
    
    # Versuche, den Port in einen Integer umzuwandeln
    try:
        mcp_port = int(mcp_port)
    except Exception as e:
        raise Exception("MCP server port is not a valid integer: " + str(e))
    
    try:
        with socket.create_connection((mcp_host, mcp_port), timeout=5) as sock:
            logging.info("Successfully connected to MCP server at %s:%s", mcp_host, mcp_port)
            return True
    except Exception as e:
        raise Exception("Could not connect to MCP server: " + str(e))



@app.before_request
def authenticate():
    # OPTIONS-Anfragen werden ohne Authentifizierung erlaubt
    if request.method == 'OPTIONS':
        return
    if request.endpoint != 'status':
        provided_key = request.headers.get('X-API-KEY')
        if not provided_key or provided_key != api_key:
            return jsonify({"error": "Unauthorized"}), 401

@app.route('/ask', methods=['POST'])
def ask():
    """
    Endpoint zum Stellen einer Frage an den Chatbot-Agenten.
    Akzeptiert entweder eine FIPA-ACL-Nachricht oder das Legacy-JSON-Format.
    """
    data = request.get_json()

    # Prüfen, ob es sich um eine FIPA-ACL-Nachricht handelt
    if data and "performative" in data and "content" in data:
        performative = data.get("performative", "unknown")
        sender = data.get("sender", "unknown")
        receiver = data.get("receiver", "unknown")
        ontology = data.get("ontology", "none")
        content = data["content"]
        if not content or 'question' not in content:
            return jsonify({"error": "Invalid FIPA-ACL request. 'content.question' is required."}), 400

        question = content['question']
        use_public = content.get('usePublic', False)
        groups = content.get('groups', None)
        language = content.get('language', 'en')

        logging.info(f"Received FIPA-ACL message: performative={performative}, sender={sender}, "
                     f"receiver={receiver}, ontology={ontology}")
    else:
        # Fallback: Legacy-Format
        if not data or 'question' not in data:
            return jsonify({"error": "Invalid request. 'question' field is required."}), 400
        question = data['question']
        use_public = data.get('usePublic', False)
        groups = data.get('groups', None)
        language = data.get('language', 'en')
        logging.info("Received legacy JSON request (no FIPA ACL fields).")

    # Sprache validieren
    if language not in languages:
        language = 'en'
        logging.warning("Unsupported language provided. Fallback to English.")

    # Gruppen validieren
    try:
        invalid_groups = agent.validate_groups(groups)
        if invalid_groups:
            return jsonify({"error": f"Invalid groups: {invalid_groups}"}), 400
    except Exception as e:
        logging.error(f"Error during group validation: {e}")
        return jsonify({"error": "Group validation failed."}), 500

    # Versuch, eine Verbindung zum MCP-Server herzustellen
    try:
        connect_to_mcp_server()
    except Exception as e:
        failure_message = {
            "performative": "failure",
            "sender": "Chatbot_Agent",
            "receiver": "IoT_MQTT_Agent",
            "language": "fipa-sl",
            "ontology": "mcp-connection-ontology",
            "content": {
                "reason": f"Could not connect to MCP server: {str(e)}"
            }
        }
        logging.error(f"MCP-Verbindungsfehler: {e}. Sende FIPA ACL failure an den IoT-Agenten.")
        return jsonify(failure_message), 200

    # Falls die Verbindung erfolgreich war, wird die Frage an den Agenten weitergereicht.
    response = agent.query_private_gpt(
        prompt=question,
        use_public=use_public,
        language=language,
        groups=groups
    )

    # Die Antwort wird als JSON zurückgegeben.
    return jsonify(json.loads(response)), 200

@app.route('/logs', methods=['GET'])
def view_logs():
    try:
        with open('flask.log', 'r') as log_file:
            log_content = log_file.read()
        return f"<pre>{log_content}</pre>", 200
    except FileNotFoundError:
        return "Log file not found.", 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "PrivateGPT Agent is running."}), 200

def run_api_server():
    server_ip = config.get("api_ip", "0.0.0.0")
    server_port = config.get("api_port", 5001)
    serve(app, host=server_ip, port=int(server_port))

if __name__ == '__main__':
    api_thread = threading.Thread(target=run_api_server)
    api_thread.daemon = True
    api_thread.start()
    display_startup_header()
    agent.run()

