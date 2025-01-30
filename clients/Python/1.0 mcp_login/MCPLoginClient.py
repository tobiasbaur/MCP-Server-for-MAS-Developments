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

def login(server_ip, server_port, email, password):
    """
    Führt den Login durch und gibt die gesamte Antwort zurück.
    """
    payload = {
        "command": "login",
        "arguments": {
            "email": email,
            "password": password
        }
    }

    response = send_request(server_ip, server_port, payload)
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Login to MCP server and retrieve a token.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--email", required=True, help="Email address for login")
    parser.add_argument("--password", required=True, help="Password for login")

    args = parser.parse_args()

    try:
        print("🔐 Logging in...")
        response = login(args.server_ip, args.server_port, args.email, args.password)
        print("✅ Server Response:")
        print(json.dumps(response, indent=4))  # Zeige die gesamte Antwort an, schön formatiert
    except Exception as e:
        print("❌ ERROR:", e)
