# Python/network.py

import socket
import json
import logging
import time
from .language import languages

class NetworkError(Exception):
    pass

class NetworkClient:
    def __init__(self, server_ip, server_port, language="en", retries=3, delay=5):
        self.server_ip = server_ip
        self.server_port = server_port
        self.retries = retries
        self.delay = delay
        self.language = language if language in languages else "en"
        self.lang = languages[self.language]

    def get_lang_message(self, key, **kwargs):
        """
        Sichere Methode zum Abrufen von Nachrichten aus dem Sprachwörterbuch.
        Wenn der Schlüssel nicht existiert, wird eine Standardnachricht zurückgegeben.
        """
        message = self.lang.get(key, "Message not defined.")
        try:
            return message.format(**kwargs)
        except KeyError as e:
            logging.error(f"Missing placeholder in language file for key '{key}': {e}")
            return message

    def send_request(self, payload):
        payload_json = json.dumps(payload)
        logging.info(f"Prepared payload: {payload_json}")
        for attempt in range(1, self.retries + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                    client_socket.settimeout(30)  # Erhöhter Timeout auf 30 Sekunden
                    logging.info(
                        self.get_lang_message(
                            "connecting_to_server",
                            ip=self.server_ip,
                            port=self.server_port,
                            attempt=attempt,
                            retries=self.retries
                        )
                    )
                    client_socket.connect((self.server_ip, self.server_port))
                    logging.info(self.get_lang_message("connection_established"))

                    logging.info(
                        self.get_lang_message(
                            "sending_payload",
                            payload=payload_json
                        )
                    )
                    client_socket.sendall((payload_json + '\n').encode("utf-8"))  # Hinzufügen des Delimiters

                    response = b""
                    while True:
                        try:
                            part = client_socket.recv(4096)
                            if not part:
                                break
                            response += part
                            if b'\n' in part:
                                break  # Nachrichtende erkannt
                        except socket.timeout:
                            break  # Keine weiteren Daten empfangen

                    decoded = response.decode("utf-8").strip()
                    logging.info(f"Received response: {decoded}")

                    if not decoded:
                        raise ValueError("Empty response received")

                    try:
                        parsed_response = json.loads(decoded)
                        
                        # Loggen der formatierten JSON-Antwort als separates Feld
                        logging.info(
                            self.get_lang_message("formatted_response"),
                            extra={"data": parsed_response}
                        )
                        
                        # Zusätzliche Verarbeitung, falls nötig
                        if "data" in parsed_response and "personalGroups" in parsed_response["data"]:
                            personal_groups = parsed_response["data"]["personalGroups"]
                            logging.info(
                                self.get_lang_message("personal_groups_received", groups=personal_groups)
                            )
                        
                        return parsed_response
                    except json.JSONDecodeError:
                        logging.error(self.get_lang_message("invalid_json_response"))
                        raise NetworkError(self.get_lang_message("invalid_json_response"))

            except socket.timeout:
                logging.warning(self.get_lang_message("connection_timed_out"))
            except Exception as e:
                logging.error(
                    self.get_lang_message(
                        "connection_error",
                        error=str(e)
                    )
                )

            if attempt < self.retries:
                logging.info(
                    self.get_lang_message(
                        "retrying_in_seconds",
                        delay=self.delay
                    )
                )
                time.sleep(self.delay)

        logging.error(self.get_lang_message("all_retries_failed"))
        raise NetworkError(self.get_lang_message("all_retries_failed"))
