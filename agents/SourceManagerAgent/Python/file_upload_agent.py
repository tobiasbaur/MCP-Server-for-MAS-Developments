# Python/api_server.py
from pathlib import Path

from flask import Flask, request, jsonify
import logging
import json
import threading

from waitress import serve
from flask_cors import CORS  # Import von Flask-CORS

from agents.AgentInterface.Python.color import Color
from agents.SourceManagerAgent.Python.file_tools.loader_factory import LoadersFactory
from agents.SourceManagerAgent.Python.local_db import create_sql_table, list_db, add_to_sql_table, delete_from_sql_table, \
    get_from_sql_table
from ...AgentInterface.Python.agent import PrivateGPTAgent
from ...AgentInterface.Python.config import Config, ConfigError
import os
import platform
import socket
#os.environ.setdefault("USER_AGENT", "PGPT")
app = Flask(__name__)

# Konfiguration von CORS
# Erlaubt spezifische Origins, z.B., 'http://localhost:5500'
# Ändern Sie die Origins entsprechend Ihrer tatsächlichen Frontend-URL
#CORS(app, resources={r"/*": {"origins": "http://192.168.100.185:5500"}}, supports_credentials=False)
# Konfiguration laden


class FileUploadAgent(PrivateGPTAgent):

    # Konfigurieren von Logging für Flask (Werkzeug)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)  # Nur Fehler, keine Warnungen
    werkzeug_handler = logging.FileHandler('flask.log')  # Logs in separate Datei
    werkzeug_handler.setLevel(logging.ERROR)
    werkzeug_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    werkzeug_handler.setFormatter(werkzeug_formatter)
    werkzeug_logger.addHandler(werkzeug_handler)


    def display_startup_header(self):
        server_ip = config.get("api_ip", "0.0.0.0")
        server_port = config.get("api_port", 8000)
        api_key_status = "✔️ Set" if self.api_key != "default_api_key" else "❌ Not Set"

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
    def authenticate(self):
        # Erlaube OPTIONS-Anfragen ohne Authentifizierung
        if request.method == 'OPTIONS':
            return
        if request.endpoint != 'status':  # Optional: Status-Endpoint ohne Auth
            provided_key = request.headers.get('X-API-KEY')
            if not provided_key or provided_key != self.api_key:
                return jsonify({"error": "Unauthorized"}), 401



    @app.route('/logs', methods=['GET'])
    def view_logs(self):
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
    def status(self):
        """
        Endpoint zur Überprüfung des Serverstatus.
        """
        return jsonify({"status": "PrivateGPT Agent is running."}), 200

    def run_api_server(self):
        # Flask-Server konfigurieren
        server_ip = config.get("api_ip", "0.0.0.0")
        server_port = config.get("api_port", 5001)

        serve(app, host=server_ip, port=int(server_port))

    def run(self):
        if not self.token:
            logging.error(self.get_lang_message("authentication_failed"))
            print(self.get_lang_message("authentication_failed"), flush=True)
            return

        db = Path.absolute(Path(__file__).parent.parent / "database/documents.sql")

        create_sql_table(db)
        list_db(db)


        welcome_msg = f"{Color.OKGREEN}{self.get_lang_message('welcome')}{Color.ENDC}"
        print(welcome_msg, flush=True)
        logging.info(self.get_lang_message("user_interface_started"))

        groups = self.chosen_groups

        print("Documents in " + groups[0] + ":" )
        available_documents = self.send_list_sources_request(groups[0])
        sources = json.loads(available_documents)["sources"]
        print(sources)


        while True:
            try:
                user_input = input(f"{Color.OKBLUE}{self.get_lang_message('user_question')}{Color.ENDC}")


                if user_input.strip().lower().startswith("delete "):
                    sourceid = user_input.strip().lower()[7:]
                    print(sourceid)

                    #if success delete from db...
                    response = self.delete_source(sourceid)
                    print(response)
                    delete_from_sql_table(db, sourceid)
                elif user_input.strip().lower() == "wipe unknown":

                    for sourceid in sources:
                        db_entry = get_from_sql_table(db, sourceid)
                        if db_entry is None:
                            print("deleting: " + sourceid)
                            # todo delete from
                        else:
                            print("keeping: " + sourceid + " " + db_entry.file + " " + db_entry.content)



                elif user_input.strip().lower() == "exit":
                    goodbye_msg = f"{Color.OKGREEN}{self.get_lang_message('goodbye')}{Color.ENDC}"
                    print(goodbye_msg, flush=True)
                    logging.info(self.get_lang_message("session_ended"))
                    break

                if user_input.strip().lower().startswith("upload file: "):

                    file_path = user_input.strip()[13:].replace("\\", "\\\\").replace("\"", "")


                    # Get the file extension
                    file_extension = os.path.splitext(file_path)[1]
                    print(f"File Extension: {file_extension}")

                    content = ""
                    if file_extension == ".pdf":
                        content =  LoadersFactory().pdf(file_path)
                    elif file_extension == ".csv":
                        content =  LoadersFactory().csv(file_path)
                    elif file_extension == ".xlsx":
                        content = LoadersFactory().xlsx(file_path)
                    #todo add more sources


                    markdown = LoadersFactory().convert_documents_to_markdown(content)
                    print(markdown)

                    result = self.send_create_source_request("test", markdown, groups)
                    parsed_result = json.loads(result)

                    if "documentId" in parsed_result:
                        answer = parsed_result["documentId"]
                        head, tail = os.path.split(file_path)
                        file = tail
                        print(file)
                        add_to_sql_table(db, parsed_result["documentId"], markdown, str(groups), file, self.email)
                        print(f"{Color.OKGREEN}{self.get_lang_message('agent_answer', answer=answer)}{Color.ENDC}",
                              flush=True)
                    else:
                        error = parsed_result["error"]
                        print(f"{Color.FAIL}{self.get_lang_message('agent_error', error=error)}{Color.ENDC}",
                              flush=True)




                elif not user_input.strip():
                    result = self.send_create_source_request("test", user_input, groups)
                    parsed_result = json.loads(result)

                    if "documentId" in parsed_result:
                        answer = parsed_result["documentId"]
                        file = "User Input"
                        add_to_sql_table(db, parsed_result["documentId"], user_input, str(groups), file, self.email)
                        print(f"{Color.OKGREEN}{self.get_lang_message('agent_answer', answer=answer)}{Color.ENDC}", flush=True)
                    else:
                        error = parsed_result["error"]
                        print(f"{Color.FAIL}{self.get_lang_message('agent_error', error=error)}{Color.ENDC}", flush=True)
            except (KeyboardInterrupt, EOFError):
                goodbye_msg = f"{Color.OKGREEN}{self.get_lang_message('goodbye')}{Color.ENDC}"
                print(goodbye_msg, flush=True)
                logging.info(self.get_lang_message("session_interrupted"))
                break

if __name__ == '__main__':
    # Starten des API-Servers in einem separaten Daemon-Thread
    try:
        config_file = Path.absolute(Path(__file__).parent.parent / "config.json")
        config = Config(config_file=config_file, required_fields=["server_ip", "server_port", "email", "password"])
    except ConfigError as e:
        logging.error(f"Configuration Error: {e}")
        exit(1)

    agent = FileUploadAgent(config=config)
    api_thread = threading.Thread(target=agent.run_api_server)
    api_thread.daemon = True  # Daemon-Thread
    api_thread.start()

    # Call this function right before the server starts
    agent.display_startup_header()

    # Starten des manuellen Chat-Interfaces
    agent.run()


