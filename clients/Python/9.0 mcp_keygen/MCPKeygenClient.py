import argparse
import socket
import json

def send_keygen_request(server_ip, server_port, token, password):
    """
    Sends a keygen request to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param password: Plaintext password to send to the server
    :return: Response from the server
    """
    payload = {
        "command": "keygen",
        "token": token,
        "arguments": {
            "password": password
        }
    }

    payload_json = json.dumps(payload)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((server_ip, server_port))
            client_socket.sendall(payload_json.encode("utf-8"))

            response = b""
            while True:
                part = client_socket.recv(4096)
                response += part
                if len(part) < 4096:
                    break

            return response.decode("utf-8")
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a keygen request to the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", type=int, required=True, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--password", required=True, help="Password to send for key generation")

    args = parser.parse_args()

    # Send the keygen request
    response = send_keygen_request(args.server_ip, args.server_port, args.token, args.password)
    print("Response from server:", response)
