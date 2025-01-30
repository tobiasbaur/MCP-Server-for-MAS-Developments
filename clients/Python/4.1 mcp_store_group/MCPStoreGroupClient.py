import socket
import json
import argparse
import sys

def send_store_group_request(server_ip, server_port, group_name, token, description=""):
    """
    Sends a request to store a new group to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param group_name: Name of the group to store
    :param description: Description of the group (optional)
    :param token: Authentication token
    :return: Response from the server
    """

    payload = {
        "command": "store_group",
        "token": token,
        "arguments": {
            "groupName": group_name,
            "description": description
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
        description="Send a request to store a new group to the MCP server.",
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
        "--group-name",
        required=True,
        help="Name of the group to store\nExample: --group-name MyGroup"
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Authentication token\nExample: --token YOUR_AUTH_TOKEN"
    )
    parser.add_argument(
        "--description",
        default="",
        help="Description of the group (optional)\nExample: --description 'This is a test group'"
    )

    # If no arguments are provided, print help and exit
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    response = send_store_group_request(
        args.server_ip,
        args.server_port,
        args.group_name,
        args.token,
        args.description
    )
    print("Response from server:", response)
