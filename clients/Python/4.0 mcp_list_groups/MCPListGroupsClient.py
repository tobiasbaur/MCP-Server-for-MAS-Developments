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

def list_groups(server_ip, server_port, token):
    """
    Sendet eine Anfrage an den Server, um die Gruppen aufzulisten.
    """
    payload = {
        "command": "list_groups",
        "token": token
    }
    return send_request(server_ip, server_port, payload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List groups using MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token for the MCP server")

    args = parser.parse_args()

    print("📄 Abrufen der Gruppen...")
    response = list_groups(args.server_ip, args.server_port, args.token)
    print("✔️ Antwort:", response)
