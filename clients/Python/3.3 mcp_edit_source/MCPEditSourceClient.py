import socket
import json
import argparse

def send_edit_source_request(server_ip, server_port, token, source_id, title=None, content=None, groups=None):
    """
    Sends a request to edit an existing source to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param source_id: ID of the source to edit
    :param title: New title for the source (optional)
    :param content: Updated content in markdown format (optional)
    :param groups: List of updated groups (optional)
    :return: Response from the server
    """
    payload = {
        "command": "edit_source",
        "token": token,
        "arguments": {
            "sourceId": source_id,
            "title": title,  # Title is used instead of name
            "content": content,
            "groups": groups or []  # Empty array if no groups are provided
        }
    }

    # Remove None values from the payload
    payload["arguments"] = {k: v for k, v in payload["arguments"].items() if v is not None}

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
    parser = argparse.ArgumentParser(description="Send a request to edit an existing source to the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--source-id", required=True, help="ID of the source to edit")
    parser.add_argument("--title", help="New title for the source (optional)")
    parser.add_argument("--content", help="Updated content in markdown format (optional)")
    parser.add_argument("--groups", nargs='*', default=[], help="List of updated groups (optional)")

    args = parser.parse_args()

    response = send_edit_source_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.source_id,
        args.title,
        args.content,
        args.groups
    )

    print("Response from server:", response)
