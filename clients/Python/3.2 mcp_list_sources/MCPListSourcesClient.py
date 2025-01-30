import socket
import json
import argparse

def send_list_sources_request(server_ip, server_port, token, group_name):
    """
    Sends a request to list sources in a specific group to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param group_name: Name of the group to list sources from
    :return: Response from the server
    """
    payload = {
        "command": "list_sources",
        "token": token,
        "attributes": {
            "groupName": group_name
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
    # Argument parser for command-line arguments
    parser = argparse.ArgumentParser(description="List sources in a specific group from the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--group-name", required=True, help="Name of the group to list sources from")

    args = parser.parse_args()

    # Send the request to list sources and print the response
    response = send_list_sources_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.group_name
    )
    print("Response from server:", response)
