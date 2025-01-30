import socket
import json
import argparse

def send_create_source_request(server_ip, server_port, token, name, content, groups):
    """
    Sends a request to create a new source to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param name: Name of the new source
    :param content: Content to be formatted as markdown
    :param groups: List of groups to assign the source to
    :return: Response from the server
    """
    payload = {
        "command": "create_source",
        "token": token,
        "arguments": {
            "name": name,
            "content": content,
            "groups": groups or []
        }
    }

    # Convert the payload to a JSON string
    payload_json = json.dumps(payload)

    try:
        # Create a socket object
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            # Connect to the server
            client_socket.connect((server_ip, server_port))

            # Send the request
            client_socket.sendall(payload_json.encode('utf-8'))

            # Receive the response
            response = b""
            while True:
                part = client_socket.recv(4096)
                response += part
                if len(part) < 4096:
                    break

            # Decode the response
            return response.decode('utf-8')

    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a request to create a new source to the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--name", required=True, help="Name of the new source")
    parser.add_argument("--content", required=True, help="Content to be formatted as markdown")
    parser.add_argument("--groups", nargs='*', default=[], help="List of groups to assign the source to")

    args = parser.parse_args()

    response = send_create_source_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.name,
        args.content,
        args.groups
    )

    print("Response from server:", response)
