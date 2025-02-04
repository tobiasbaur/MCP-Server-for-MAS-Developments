#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import os
import threading
import time
import paho.mqtt.client as mqtt
import requests

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
    handler.terminator = "\n"

    logging.basicConfig(level=log_level, handlers=[handler])

# ───────────────────────────────────────────────────────────────
# MQTT Callback-Funktionen
# ───────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info(
            "Connected to MQTT broker",
            extra={"component": "mqtt", "tag": "connect", "message_type": "Status"}
        )
        topic = userdata["mqtt"].get("topic", "#")
        client.subscribe(topic)
        logging.info(
            f"Subscribed to topic: {topic}",
            extra={"component": "mqtt", "tag": "subscribe", "message_type": "Status"}
        )
    else:
        logging.error(
            f"Failed to connect, return code {rc}",
            extra={"component": "mqtt", "tag": "connect", "message_type": "Error"}
        )

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
    except Exception:
        payload_str = str(msg.payload)

    parameter = msg.topic.split('/')[-1]

    # Einheitliche Formatierung
    flabel = format_text("Received message on topic", LABEL_WIDTH)
    ftopic = format_text(msg.topic, TOPIC_WIDTH)
    fparam = format_text(parameter, PARAMETER_WIDTH)
    fvalue = format_text(payload_str, VALUE_WIDTH, ">")

    # Einheitliche Log-Ausgabe für MQTT-Nachrichten
    logging.info(
        f"{flabel} | {ftopic} | Parameter: {fparam} | Wert: {fvalue}",
        extra={"component": "mqtt", "tag": "message", "message_type": "Incoming"}
    )

    # Nachricht an den Chatbot-Agenten weiterleiten
    chatbot_config = userdata.get("chatbot_agent", {})
    api_url = chatbot_config.get("api_url")
    api_key = chatbot_config.get("api_key")

    if not api_url or not api_key:
        logging.warning(
            "Chatbot Agent configuration missing. Cannot forward message.",
            extra={"component": "chatbot_agent", "tag": "config", "message_type": "Warning"}
        )
        return

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": api_key
    }

    acl_payload = {
        "performative": "request",
        "sender": "IoT_MQTT_Agent",
        "receiver": "Chatbot_Agent",
        "language": "fipa-sl",
        "ontology": "fujitsu-iot-ontology",
        "content": {
            "question": f"Parameter: {parameter}, Wert: {payload_str}",
            "usePublic": True,
            "groups": [],
            "language": "en"
        }
    }

    try:
        response = requests.post(api_url, json=acl_payload, headers=headers)

        # Einheitliche API-Logging
        status_code = format_text(str(response.status_code), STATUS_WIDTH, ">")
        response_text = format_text(response.text, RESPONSE_WIDTH)

        logging.info(
            f"{format_text('Chatbot API Request', LABEL_WIDTH)} | {ftopic} | Parameter: {fparam} | Wert: {fvalue}",
            extra={"component": "chatbot_agent", "tag": "request", "message_type": "Outgoing"}
        )
        logging.info(
            f"{format_text('Chatbot API Response', LABEL_WIDTH)} | {ftopic} | Status: {status_code} | Response: {response_text}",
            extra={"component": "chatbot_agent", "tag": "response", "message_type": "Incoming"}
        )

    except Exception as e:
        logging.error(
            f"Error sending message to Chatbot Agent API: {e}",
            extra={"component": "chatbot_agent", "tag": "post", "message_type": "Error"}
        )

# ───────────────────────────────────────────────────────────────
# Hauptfunktion mit sauberem Shutdown
# ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="IoT MQTT Agent")
    parser.add_argument("--config", required=True, help="Path to configuration JSON file")
    args = parser.parse_args()

    config_path = args.config
    if not os.path.isfile(config_path):
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "logging" in config:
        setup_logging(config["logging"])
    else:
        logging.basicConfig(level=logging.INFO)

    logging.info("Configuration loaded", extra={"component": "config", "tag": "load", "message_type": "Status"})

    mqtt_config = config.get("mqtt", {})
    broker = mqtt_config.get("broker", "localhost")
    port = mqtt_config.get("port", 1883)

    client = mqtt.Client(userdata=config)

    if "username" in mqtt_config and "password" in mqtt_config:
        client.username_pw_set(mqtt_config["username"], mqtt_config["password"])

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker, port, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down IoT MQTT Agent", extra={"component": "main", "tag": "shutdown", "message_type": "Status"})
        client.disconnect()
        sys.exit(0)

if __name__ == "__main__":
    main()
