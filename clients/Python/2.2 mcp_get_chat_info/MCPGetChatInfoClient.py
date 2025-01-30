import socket
import json
import argparse

def send_request(server_ip, server_port, payload):
    """
    Sendet eine generische Anfrage an den Server.
    """
    payload_json = json.dumps(payload)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((server_ip, server_port))
            client_socket.sendall(payload_json.encode('utf-8'))

            response = b""
            while True:
                part = client_socket.recv(4096)
                response += part
                if len(part) < 4096:
                    break

            return json.loads(response.decode('utf-8'))
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Abrufen von Informationen über eine bestehende Konversation.")
    parser.add_argument("--server-ip", required=True, help="IP-Adresse des MCP-Servers")
    parser.add_argument("--server-port", required=True, type=int, help="Portnummer des MCP-Servers")
    parser.add_argument("--token", required=True, help="Authentifizierungs-Token")
    parser.add_argument("--chat-id", required=True, help="ID der Konversation")

    args = parser.parse_args()

    payload = {
        "command": "get_chat_info",
        "token": args.token,
        "arguments": {
            "chatId": args.chat_id
        }
    }

    print("📤 Anfrage senden...")
    response = send_request(args.server_ip, args.server_port, payload)
    print("✔️ Antwort:", json.dumps(response, indent=2))
