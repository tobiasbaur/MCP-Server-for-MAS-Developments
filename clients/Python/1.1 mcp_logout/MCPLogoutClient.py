import argparse
import socket
import json

def send_logout_request(server_ip, server_port, token):
    """
    Sends a logout request to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :return: Response from the server
    """
    payload = {
        "command": "logout",
        "token": token
    }

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

            return response.decode('utf-8')
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a logout request to the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", type=int, required=True, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")

    args = parser.parse_args()

    response = send_logout_request(args.server_ip, args.server_port, args.token)
    print("Response from server:", response)
