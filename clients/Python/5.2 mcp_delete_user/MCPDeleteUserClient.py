import socket
import json
import argparse
import sys

def send_delete_user_request(server_ip, server_port, email, token):
    """
    Sends a request to delete a user from the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param email: Email of the user to delete
    :param token: Authentication token
    :return: Response from the server
    """
    payload = {
        "command": "delete_user",
        "token": token,
        "arguments": {
            "email": email
        }
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
    parser = argparse.ArgumentParser(
        description="Send a request to delete a user from the MCP server.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--server-ip",
        required=True,
        help="IP address of the MCP server\nExample: --server-ip 192.168.0.1"
    )
    parser.add_argument(
        "--server-port",
        required=True,
        type=int,
        help="Port number of the MCP server\nExample: --server-port 5000"
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the user to delete\nExample: --email roy@acme.com"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Authentication token\nExample: --token YOUR_AUTH_TOKEN"
    )

    # If no arguments are provided, print help and exit
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    response = send_delete_user_request(
        args.server_ip,
        args.server_port,
        args.email,
        args.token
    )
    print("Response from server:", response)
