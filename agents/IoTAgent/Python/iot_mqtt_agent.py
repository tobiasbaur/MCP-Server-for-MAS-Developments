# iot_mqtt_agent.py

import paho.mqtt.client as mqtt
import logging
import json
from datetime import datetime
import os
import paramiko
import shutil
import argparse
import posixpath  # Für Remote-Pfade
import requests  # Für die Kommunikation mit dem Chatbot-Agenten
import sys
import time
import warnings
from .language import languages  # Korrekte Importanweisung
from ...AgentInterface.Python.color import Color


import socket  # Für display_startup_header
import platform  # Für display_startup_header

import signal

def handle_sigint(signum, frame):
    # Hier Logging oder andere Aufräumarbeiten
    logging.info("Strg+C erkannt, beende den IoT MQTT Agent jetzt sauber.")
    # Falls der MQTT-Client global verfügbar ist, kann man ihn hier stoppen
    # client.loop_stop()
    # client.disconnect()
    sys.exit(0)

# Dem Betriebssystem mitteilen, dass diese Funktion bei SIGINT (Strg+C) aufzurufen ist
signal.signal(signal.SIGINT, handle_sigint)


# ───────────────────────────────────────────────────────────────
# Konstante Spaltenbreiten für saubere Formatierung
# ───────────────────────────────────────────────────────────────
TIMESTAMP_WIDTH  = 20
COMPONENT_WIDTH  = 16
TAG_WIDTH        = 10
MESSAGE_WIDTH    = 12
LABEL_WIDTH      = 30  # Einheitliche Breite für "Received message on topic" etc.
TOPIC_WIDTH      = 40
PARAMETER_WIDTH  = 35
VALUE_WIDTH      = 15
STATUS_WIDTH     = 8
RESPONSE_WIDTH   = 40

# Funktion zur Formatierung von Text mit fester Breite
def format_text(text: str, width: int, align: str = "<") -> str:
    """Bringt den Text auf eine feste Breite und richtet ihn aus (links '<', rechts '>')."""
    return f"{text:{align}{width}}"[:width]

# ───────────────────────────────────────────────────────────────
# Custom Logging Formatter (Emoji + einheitliche Spaltenbreite)
# ───────────────────────────────────────────────────────────────
class CustomFormatter(logging.Formatter):
    LEVEL_ICONS = {
        'DEBUG': '🐛',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '‼️'
    }

    def format(self, record):
        record.level_icon = self.LEVEL_ICONS.get(record.levelname, record.levelname)
        record.component = format_text(getattr(record, "component", "iot"), COMPONENT_WIDTH)
        record.tag = format_text(getattr(record, "tag", "-"), TAG_WIDTH)
        record.message_type = format_text(getattr(record, "message_type", "-"), MESSAGE_WIDTH)

        log_format = "{asctime} | {level_icon} {component} :{tag} | {message_type} | {message}"
        return log_format.format(
            asctime=self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            level_icon=record.level_icon,
            component=record.component,
            tag=record.tag,
            message_type=record.message_type,
            message=record.getMessage()
        )

def setup_logging(logging_config):
    level_name = logging_config.get("level", "INFO")
    log_level = getattr(logging, level_name.upper(), logging.INFO)

    formatter = CustomFormatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Hier wird basicConfig nur einmal aufgerufen, bevor Logging genutzt wird.
    logging.basicConfig(level=log_level, handlers=[handler])

if __name__ == "__main__":
    setup_logging({"level": "DEBUG"})
    # Jetzt können alle weiteren Logging-Aufrufe den benutzerdefinierten Formatter nutzen.
    # Restlicher Code...
  
# Temporäres Filtern der DeprecationWarning (nur als Übergangslösung)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Globale Variable für die aktuelle Sprache
current_language = "en"

# Klasse zur Handhabung von userdata
class UserData:
    def __init__(self, handlers, config):
        self.handlers = handlers
        self.config = config

# Funktion zum Laden der Konfiguration
def load_config(config_path, current_language):
    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
        message = languages[current_language]["configuration_loaded"].format(config_path=config_path)
        #logging.debug(message)
        return config
    except Exception as e:
        message = languages[current_language]["error_loading_config"].format(e=e)
        logging.error(message)
        sys.exit(1)

# Callback-Funktion für den Verbindungsaufbau (angepasst für MQTT v5)
def on_connect(client, userdata, flags, rc, properties=None):
    global current_language
    if rc == 0:
        # logging.info(message)
        message = languages[current_language]["welcome"]
        logging.info(
            "Connected to MQTT broker",
            extra={"component": "mqtt", "tag": "connect", "message_type": "Status"}
        )
        client.subscribe(userdata.config['mqtt']['topic'])
        subscribed_message = f"Subscribed to {userdata.config['mqtt']['topic']}."
        logging.info(Color.color_text(subscribed_message, Color.OKBLUE))
    else:
        error_message = languages[current_language]["chatbot_error_status"].format(status_code=rc, response="")
        logging.error(
            f"Failed to connect, return code {rc}",
            extra={"component": "mqtt", "tag": "connect", "message_type": "Error"}
        )
        # logging.error(error_message)

# Callback-Funktion für empfangene Nachrichten (angepasst)
def on_message(client, userdata, msg):
    global current_language
    try:
        # Extrahiere Timestamp, Parameter und Payload
        timestamp = datetime.now().isoformat()
        parameter = msg.topic.split('/')[-1]
        payload = msg.payload.decode('utf-8')

        try:
            value = json.loads(payload) if payload.startswith('{') else payload
        except json.JSONDecodeError:
            value = payload

        record = {
            "timestamp": timestamp,
            "vehicle": userdata.config['mqtt']['vehicle_name'],
            "parameter": parameter,
            "value": value
        }

        # Einheitliche Formatierung ohne erzwungene Breiten
        flabel = "Received message on topic"
        ftopic = msg.topic
        fparam = parameter
        fvalue = payload.strip()  # Entferne unnötige Leerzeichen

        # Einheitliche Log-Ausgabe für MQTT-Nachrichten
        logging.info(
            f"{flabel} | {ftopic} | Parameter: {fparam} | Wert: {fvalue}",
            extra={"component": "mqtt", "tag": "message", "message_type": "Incoming"}
        )
        # Speichern der JSON-Daten
        userdata.handlers['json'].append_record(record)

        # Debugging-Statement
        #logging.debug(f"Calling interpret_and_output with record: {record}, handlers: {userdata.handlers}, config: {userdata.config}")

        # Interpretation und Speicherung der generierten Sätze
        interpret_and_output(record, userdata.handlers, userdata.config)
                # Einheitliche API-Logging
         # status_code = format_text(str(response.status_code), STATUS_WIDTH, ">")
         # response_text = format_text(response.text, RESPONSE_WIDTH)

        logging.info(
            f"{ftopic} | Parameter: {fparam} | Value: {fvalue}",
            extra={"component": "chatbot_agent", "tag": "request", "message_type": "Outgoing"}
        )

        # logging.info(
            # f"{format_text('Chatbot API Request', LABEL_WIDTH)} | {ftopic} | Parameter: {fparam} | Wert: {fvalue}",
            # extra={"component": "chatbot_agent", "tag": "request", "message_type": "Outgoing"}
        # )

        mqtt_info = f"MQTT Message received: Topic: {msg.topic} | Payload: {payload}"
        logging.info(mqtt_info, extra={"component": "mqtt", "tag": "message", "message_type": "Incoming"})

    except Exception as e:
        error_message = languages[current_language]["error_in_interpret_and_output"].format(e=e)
        logging.error(error_message)

class LocalFileHandler:
    """
    Diese Klasse verwaltet lokale Dateien mit dynamischen, timestamp-basierten Namen.
    Sie sorgt dafür, dass jede Datei einen eindeutigen Zeitstempel und einen 5-stelligen Zähler im Namen hat.
    """

    def __init__(self, base_name, local_dir, file_type, size_limit, remote_subdir, config, language_code):
        """
        Initialisiert den FileHandler.

        :param base_name: Basisname der Datei (z.B. 'mqtt.json', 'translated_text_de.txt')
        :param local_dir: Lokales Verzeichnis, in dem die Dateien gespeichert werden sollen
        :param file_type: Typ der Datei ('json', 'txt')
        :param size_limit: Größenlimit in Bytes
        :param remote_subdir: Remote-Unterverzeichnis auf dem SFTP-Server
        :param config: Gesamte Konfigurationsdaten
        :param language_code: Sprachcode (z.B. 'de', 'en')
        """
        self.base_name = base_name
        self.local_dir = local_dir
        self.file_type = file_type
        self.size_limit = size_limit
        self.remote_subdir = remote_subdir
        self.config = config
        self.language_code = language_code
        self.current_file_path = self._create_new_file()

    def _create_new_file(self):
        """
        Erstellt eine neue lokale Datei mit einem Zeitstempel und einem Zähler.

        :return: Pfad zur neu erstellten Datei
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  # Format: YYYYMMDDHHMMSS
        if self.file_type == "json":
            suffix = "JSON"
        else:
            suffix = self.language_code.upper()
        prefix = f"{self.config['files']['base_filename']}-{suffix}-"
        full_prefix = f"{prefix}{timestamp}-"
        counter = self._get_next_suffix(full_prefix)
        if counter is None:
            error_message = languages[current_language]["cannot_create_new_file"].format(file_type=self.file_type, language=self.language_code)
            logging.error(error_message)
            return None
        extension = "json" if self.file_type == "json" else "txt"
        filename = f"{full_prefix}{counter}.{extension}"
        file_path = os.path.join(self.local_dir, filename)
        os.makedirs(self.local_dir, exist_ok=True)
        if self.file_type == "json":
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump([], file, ensure_ascii=False, indent=4)
        message = languages[current_language]["new_file_created"].format(file_path=file_path)
        logging.info(message)
        return file_path

    def _get_next_suffix(self, full_prefix):
        """
        Ermittelt den nächsten verfügbaren 5-stelligen Suffix.

        :param full_prefix: Vollständiger Prefix inklusive Zeitstempel
        :return: 5-stelliger Suffix als String oder None, wenn keine verfügbar sind
        """
        try:
            # Verbinde sich mit SFTP, um vorhandene Suffixe zu ermitteln
            transport = paramiko.Transport((self.config['sftp']['host'], self.config['sftp']['port']))
            transport.connect(username=self.config['sftp']['username'], password=self.config['sftp']['password'])
            sftp = paramiko.SFTPClient.from_transport(transport)
            remote_base_dir = posixpath.join(self.config['sftp']['remote_path'], self.remote_subdir)
            try:
                sftp.chdir(remote_base_dir)
                existing_files = sftp.listdir(remote_base_dir)
            except IOError:
                existing_files = []
            sftp.close()
            transport.close()

            suffixes = []
            for file in existing_files:
                if file.startswith(full_prefix):
                    suffix_part = file[len(full_prefix):].split('.')[0]
                    if suffix_part.isdigit() and len(suffix_part) == 5:
                        suffixes.append(int(suffix_part))

            for i in range(100000):
                if i not in suffixes:
                    return f"{i:05}"

            logging.error(languages[current_language]["error_getting_suffixes"].format(e="All suffixes are occupied."))
            return None
        except Exception as e:
            error_message = languages[current_language]["error_getting_suffixes"].format(e=e)
            logging.error(error_message)
            return None

    def append_record(self, record):
        """
        Fügt einen Datensatz zur JSON-Datei hinzu.

        :param record: Der zu speichernde Datensatz (Dictionary)
        """
        if self.file_type != "json":
            error_message = languages[current_language]["invalid_group"].format(groups=self.file_type)
            logging.error(error_message)
            return

        try:
            if not self.current_file_path:
                error_message = languages[current_language]["error_writing_file"].format(file_path=self.current_file_path, e="File path is not set.")
                logging.error(error_message)
                return

            with open(self.current_file_path, 'r+', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []
                    warning_message = languages[current_language]["file_empty_or_corrupted"].format(file_path=self.current_file_path)
                    logging.warning(Color.color_text(warning_message, Color.WARNING))
                data.append(record)
                file.seek(0)
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.truncate()
            record_added_message = languages[current_language]["record_added"].format(file_path=self.current_file_path)
           # logging.info(record_added_message)
            logging.info(
                f"{record_added_message}",
                extra={"component": "iot", "tag": "filesystem", "message_type": "write"}
            )


            self._check_size_and_rotate()
        except Exception as e:
            error_message = languages[current_language]["error_writing_file"].format(file_path=self.current_file_path, e=e)
            logging.error(error_message)

    def append_text(self, text):
        """
        Fügt einen Text zur Textdatei hinzu.

        :param text: Der zu speichernde Text (String)
        """
        if self.file_type != "txt":
            error_message = languages[current_language]["invalid_group"].format(groups=self.file_type)
            logging.error(error_message)
            return

        try:
            if not self.current_file_path:
                error_message = languages[current_language]["error_writing_file"].format(file_path=self.current_file_path, e="File path is not set.")
                logging.error(error_message)
                return

            with open(self.current_file_path, 'a', encoding='utf-8') as file:
                file.write(text + '\n')
            logging.info(
                f"{text}",
                extra={"component": "iot", "tag": "filesystem", "message_type": "write"}
            )
            #logging.info(languages[current_language]["record_added"].format(file_path=self.current_file_path))

            self._check_size_and_rotate()
        except Exception as e:
            error_message = languages[current_language]["error_writing_file"].format(file_path=self.current_file_path, e=e)
            logging.error(error_message)

    def _check_size_and_rotate(self):
        """
        Überprüft die Dateigröße und rotiert die Datei, wenn das Limit erreicht ist.
        """
        global current_language
        try:
            if not self.current_file_path:
                return
            file_size = os.path.getsize(self.current_file_path)
            #logging.debug(languages[current_language]["file_size"].format(file_path=self.current_file_path, file_size=file_size))
            if file_size >= self.size_limit:
                logging.info(languages[current_language]["file_limit_reached"].format(file_path=self.current_file_path, size_limit=self.size_limit))
                success = upload_file(self.current_file_path, self.file_type, self.remote_subdir, self.config)
                if success:
                    archive_file(self.current_file_path)
                    self.current_file_path = self._create_new_file()
        except Exception as e:
            error_message = languages[current_language]["error_writing_file"].format(file_path=self.current_file_path, e=e)
            logging.error(error_message)

# Generische Funktion zur SFTP-Übertragung von Dateien mit neuem Namensschema
def upload_file(file_path, file_type, remote_subdir, config):
    """
    Überträgt eine Datei via SFTP mit einem Zeitstempel und einem 5-stelligen Suffix im Dateinamen.

    :param file_path: Pfad zur lokalen Datei
    :param file_type: Typ der Datei ('json', 'txt')
    :param remote_subdir: Remote-Unterverzeichnis auf dem SFTP-Server
    :param config: Gesamte Konfigurationsdaten
    :return: True bei Erfolg, False bei Fehler
    """
    global current_language
    try:
        uploading_message = languages[current_language]["start_uploading_file"].format(file_path=file_path)
        #logging.debug(uploading_message)
        transport = paramiko.Transport((config['sftp']['host'], config['sftp']['port']))
        transport.connect(username=config['sftp']['username'], password=config['sftp']['password'])
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Remote-Verzeichnis inklusive Unterverzeichnis
        remote_base_dir = posixpath.join(config['sftp']['remote_path'], remote_subdir)
        try:
            sftp.chdir(remote_base_dir)
            directory_exists_message = languages[current_language]["remote_directory_exists"].format(remote_base_dir=remote_base_dir)
            #logging.debug(directory_exists_message)
        except IOError:
            sftp.mkdir(remote_base_dir)
            sftp.chdir(remote_base_dir)
            directory_created_message = languages[current_language]["remote_directory_created"].format(remote_base_dir=remote_base_dir)
            #logging.debug(directory_created_message)

        # Bestimmen des Basis-Dateinamens ohne Suffix
        # Da der lokale Dateiname bereits den Zeitstempel und Suffix enthält, wird er direkt verwendet
        remote_file_name = os.path.basename(file_path)
        remote_file_path = posixpath.join(remote_base_dir, remote_file_name)

        # Übertrage die Datei
        sftp.put(file_path, remote_file_path)
        upload_success_message = languages[current_language]["file_uploaded_successfully"].format(
            file_path=file_path, host=config['sftp']['host'], remote_file_path=remote_file_path)
        logging.info(upload_success_message)

        # Schließe die SFTP-Verbindung
        sftp.close()
        transport.close()
        finished_uploading_message = languages[current_language]["finished_uploading_file"].format(file_path=file_path)
        #logging.debug(finished_uploading_message)
        return True
    except Exception as e:
        error_message = languages[current_language]["error_sftp_upload"].format(file_path=file_path, e=e)
        logging.error(error_message)
        return False

# Funktion zur Archivierung der Datei nach der Übertragung
def archive_file(file_path):
    global current_language
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        archive_name = f"{os.path.splitext(file_path)[0]}_{timestamp}{os.path.splitext(file_path)[1]}"
        shutil.move(file_path, archive_name)
        archive_message = languages[current_language]["file_archived"].format(file_path=file_path, archive_name=archive_name)
        logging.info(archive_message)
    except Exception as e:
        error_message = languages[current_language]["error_archiving_file"].format(file_path=file_path, e=e)
        logging.error(error_message)

# Funktion zur Generierung eines logischen Satzes über den Chatbot-Agenten mit Retry-Mechanismus
def generate_logical_sentence(parameters, language_code, config, wait_seconds=5):
    """
    Sendet die Parameter an den Chatbot-Agenten in Form einer FIPA-ACL-Anfrage und erhält einen logischen Satz.
    Falls eine FIPA-ACL failure-Nachricht empfangen wird (z. B. wegen Verbindungsproblemen), wird ausgegeben,
    dass der Chatbot-Agent ein Problem meldet und der IoT-Agent wartet, bis eine OK-Antwort kommt.
    Sobald eine OK-Antwort empfangen wird, wird zusätzlich ausgegeben, dass das Problem behoben ist.
    """
    while True:
        try:
            # Erstellen des Prompts aus den Parametern
            prompt = (
                "Erstelle einen logischen Satz aus den folgenden JSON-Parametern:\n" +
                json.dumps(parameters, ensure_ascii=False, indent=4)
            )

            # Aufbau der FIPA-ACL-Anfrage
            acl_payload = {
                "performative": "request",
                "sender": "IoT_MQTT_Agent",
                "receiver": "Chatbot_Agent",
                "language": "fipa-sl",
                "ontology": "fujitsu-iot-ontology",
                "content": {
                    "question": prompt,
                    "usePublic": True,
                    "groups": [],
                    "language": language_code
                }
            }

            headers = {
                "Content-Type": "application/json",
                "X-API-KEY": config['chatbot_agent']['api_key']
            }

            response = requests.post(
                config['chatbot_agent']['api_url'],
                json=acl_payload,
                headers=headers,
                timeout=10
            )
            data = response.json()

            status_code = response.status_code  # Extrahiere den HTTP-Statuscode
            data = response.json()  # Versuche die JSON-Antwort zu parsen
            response_text = json.dumps(data, ensure_ascii=False, indent=2)  # JSON formatieren für das Logging

            # Einheitliche Formatierung
            flabel = format_text("Chatbot API Response", LABEL_WIDTH)

            # Extrahiere nur den Inhalt des "answer"-Schlüssels, falls vorhanden
            answer_text = data.get("answer", "No answer received").strip('"')  # Entfernt ggf. überflüssige Anführungszeichen

            logging.info(
                f"{answer_text}",
                extra={"component": "chatbot_agent", "tag": "response", "message_type": "Incoming"}
            )

            
            # logging.info(
                # f"{flabel} | Status: {status_code} | Response: {response_text}",
                # extra={"component": "chatbot_agent", "tag": "response", "message_type": "Incoming"}
            # )
            
            
            # Einheitliche Formatierung
            # flabel = format_text("Received message on topic", LABEL_WIDTH)
            # ftopic = format_text(msg.topic, TOPIC_WIDTH)
            # fparam = format_text(parameter, PARAMETER_WIDTH)
            # fvalue = format_text(payload, VALUE_WIDTH, ">")

            # logging.info(
                # f"{format_text('Chatbot API Response', LABEL_WIDTH)} | {ftopic} | Status: {status_code} | Response: {response}",
                # extra={"component": "chatbot_agent", "tag": "response", "message_type": "Incoming"}
            # )
        
            # Prüfen, ob der Chatbot-Agent ein Failure sendet
            if data.get("performative") == "failure":
                reason = data.get("content", {}).get("reason", "Unknown reason.")
                error_msg = f"ChatBot Agent reports a problem: {reason}. Waiting for recovery..."
                logging.error(error_msg)
                time.sleep(wait_seconds)
                continue  # Wiederhole die Anfrage

            # Falls keine Failure vorliegt, wird der erwartete Satz aus dem Feld "answer" entnommen.
            generated_sentence = data.get("answer", "")
            if not generated_sentence:
                raise ValueError("Empty 'answer' field in normal response.")
            
            # Ausgabe, dass nun ein OK empfangen wurde und das Problem behoben ist.
            ok_msg = "OK response received. Stable connection."
            logging.info(ok_msg)

            return generated_sentence
            
        except KeyboardInterrupt:
            # Sobald Strg+C gedrückt wird, wollen wir wirklich abbrechen.
            # -> Also re-raise, damit der Code bis "main" hochgeht.
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, ValueError) as e:
            logging.error(f"Error during request: {e}. Waiting for Recovery...")
            time.sleep(wait_seconds)
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Waiting for Recovery...")
            time.sleep(wait_seconds)


# Funktion zur Generierung lesbarer Sätze basierend auf konfigurierten Sprachen
def interpret_and_output(record, local_handlers, config):
    global current_language
    try:
        try:
            timestamp = datetime.fromisoformat(record["timestamp"]).strftime("%d-%m-%Y um %H:%M:%S")
        except ValueError:
            timestamp = record["timestamp"]  # Falls das Format nicht korrekt ist
            warning_message = languages[current_language]["file_empty_or_corrupted"].format(file_path=record["timestamp"])
            logging.warning(warning_message)

        vehicle = record.get("vehicle", "Unbekanntes Fahrzeug")
        parameter = record.get("parameter", "unbekannt")
        value = record.get("value", "nicht verfügbar")

        # Iteriere durch die konfigurierten Sprachen
        for language_code in config.get("languages", ["de", "en"]):
            if language_code not in config['files']['translated_text_files']:
                error_message = languages[current_language]["no_translation_file_configured"].format(language=language_code)
                logging.error(error_message)
                continue

            # Definiere die Parameter basierend auf der Sprache
            if language_code == "de":
                parameters = {
                    "Zeitpunkt": timestamp,
                    "Fahrzeug": vehicle,
                    "Parameter": parameter,
                    "Wert": value
                }
            elif language_code == "en":
                parameters = {
                    "Timestamp": timestamp,
                    "Vehicle": vehicle,
                    "Parameter": parameter,
                    "Value": value
                }
            else:
                warning_message = languages[current_language]["unknown_language"].format(language=language_code)
                logging.warning(warning_message)
                continue

            # Generieren des Satzes
            generated_sentence = generate_logical_sentence(parameters, language_code, config)

            if generated_sentence:
                # Bestimmen der vollen Sprachbezeichnung
                if language_code == "de":
                    language_full = "Deutsch"
                elif language_code == "en":
                    language_full = "English"
                else:
                    language_full = language_code.upper()

                # Loggen und Ausgeben des Satzes
                sentence_message = languages[current_language]["language_sentence_generated"].format(language_full=language_full, sentence=generated_sentence)
                #logging.info(sentence_message)
                # logging.info(
                    # f"{format_text('Chatbot API Response', LABEL_WIDTH)} | {ftopic} | Status: {status_code} | Response: {sentence_message}",
                    # extra={"component": "chatbot_agent", "tag": "sentence_message", "message_type": "Incoming"}
                # )
           
                logging.info(
                    f"{generated_sentence}",
                    extra={"component": "chatbot_agent", "tag": "sentence_message", "message_type": "Incoming"}
                )
                
                # Speichern des Satzes in der entsprechenden Textdatei
                handler_key = f"{language_code}_txt"
                if handler_key in local_handlers:
                    local_handlers[handler_key].append_text(generated_sentence)
                else:
                    file_handler_error_message = languages[current_language]["no_file_handler_found"].format(language=language_code)
                    logging.error(file_handler_error_message)
            else:
                # Bestimmen der vollen Sprachbezeichnung
                if language_code == "de":
                    language_full = "Deutsch"
                elif language_code == "en":
                    language_full = "Englisch"
                else:
                    language_full = language_code.upper()
                no_sentence_message = languages[current_language]["no_sentence_generated"].format(language_full=language_full)
                logging.warning(no_sentence_message)
    except Exception as e:
        error_message = languages[current_language]["error_in_interpret_and_output"].format(e=e)
        logging.error(error_message)

def display_startup_header(config):
    global current_language
    # Extrahiere Server-IP und Port aus der API-URL
    api_url = config.get("chatbot_agent", {}).get("api_url", "http://0.0.0.0:5001/ask")
    try:
        server_ip = api_url.split("//")[-1].split(":")[0]
        server_port = api_url.split(":")[-1].split("/")[0]
    except IndexError:
        server_ip = "0.0.0.0"
        server_port = "5001"

    api_key = config.get("chatbot_agent", {}).get("api_key", "default_api_key")
    api_key_status = "✔️ Set" if api_key != "default_api_key" else "❌ Not Set"

    header = f"""
────────────────────────────────────────────────
Fujitsu PrivateGPT MQTT IoT Agent - Startup
────────────────────────────────────────────────
System Information:
- Hostname      : {socket.gethostname()}
- Operating Sys : {platform.system()} {platform.release()}
- Python Version: {platform.python_version()}

Server Configuration:
- API Endpoint  : {api_url}
- API Key Status: {api_key_status}

Logs:
- Agent Log     : iot_agent.log
────────────────────────────────────────────────
🚀 Ready to serve requests!
"""

# Hauptfunktion
def main():
    global current_language  # Globale Variable für die aktuelle Sprache

    parser = argparse.ArgumentParser(description="MQTT zu JSON und Satzgenerierung mit SFTP-Übertragung.")
    parser.add_argument('--config', type=str, default='pgpt_iot_agent.json', help='Pfad zur JSON-Konfigurationsdatei.')
    args = parser.parse_args()

    # Temporäres Laden der Konfiguration, um die Sprache zu bestimmen
    try:
        with open(args.config, 'r', encoding='utf-8') as config_file:
            temp_config = json.load(config_file)
    except Exception as e:
        #print(f"Error loading configuration file: {e}")
        sys.exit(1)

    # Bestimme die aktuelle Sprache (erste in der Liste)
    languages_list = temp_config.get("languages", ["en"])
    current_language = languages_list[0] if languages_list else "en"

    # Laden der Konfiguration
    config = load_config(args.config, current_language)

    # Konfigurieren des Loggings
    log_level = getattr(logging, config['logging'].get('level', 'INFO').upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=config['logging'].get('format', '%(asctime)s - %(levelname)s - %(message)s'),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("iot_agent.log", encoding='utf-8')
        ]
    )

    # Initialisiere lokale Dateihandler basierend auf den konfigurierten Sprachen
    handlers = {
        'json': LocalFileHandler(
            base_name=config['files']['json_file_name'],
            local_dir=config['files']['local_subdirs']['json'],
            file_type="json",
            size_limit=config['files']['size_limits']['json'],
            remote_subdir=config['files']['sftp_subdirs']['json'],
            config=config,
            language_code="json"  # Sprache irrelevant für JSON-Dateien, aber erforderlich für die Klasse
        )
    }

    # Dynamisch Dateihandler für jede konfigurierte Sprache hinzufügen
    for language_code in config.get("languages", ["de", "en"]):
        if language_code in config['files']['translated_text_files']:
            handler_key = f"{language_code}_txt"
            handlers[handler_key] = LocalFileHandler(
                base_name=config['files']['translated_text_files'][language_code],
                local_dir=config['files']['local_subdirs'][f"{language_code}_txt"],
                file_type="txt",
                size_limit=config['files']['size_limits'][f"{language_code}_txt"],
                remote_subdir=config['files']['sftp_subdirs'][f"{language_code}_txt"],
                config=config,
                language_code=language_code
            )
        else:
            error_message = languages[current_language]["no_translation_file_in_config"].format(language=language_code)
            logging.error(error_message)

    # Erstellen einer Instanz von UserData
    user_data = UserData(handlers=handlers, config=config)

    # Initialisieren des MQTT-Clients mit MQTTv5 und benutzerdefiniertem userdata
    client = mqtt.Client(protocol=mqtt.MQTTv5, userdata=user_data)
    client.username_pw_set(config['mqtt']['username'], config['mqtt']['password'])
    client.on_connect = on_connect
    client.on_message = on_message

    # Anzeige des Startup-Headers
    display_startup_header(config)

    try:
        logging.info(languages[current_language]["start_uploading_file"].format(file_path=config['mqtt']['broker']))
        client.connect(config['mqtt']['broker'], config['mqtt']['port'], 60)
    except Exception as e:
        error_message = languages[current_language]["error_loading_config"].format(e=e)
        logging.error(error_message)
        return
    logging.info("Configuration loaded", extra={"component": "config", "tag": "load", "message_type": "Status"})
    client.loop_start()

    try:
        while True:
            time.sleep(1)  # Warte auf Ereignisse
    except KeyboardInterrupt:
        exit_message = languages[current_language]["user_exit"]
        logging.info("Shutting down IoT MQTT Agent", extra={"component": "main", "tag": "shutdown", "message_type": "Status"})
        client.loop_stop()
        client.disconnect()
        sys.exit(0)
        logging.info(exit_message)
        print(exit_message)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
    logging.info("Shutting down IoT MQTT Agent")
    # hier ggf. client.loop_stop() / client.disconnect()
    sys.exit(0)


