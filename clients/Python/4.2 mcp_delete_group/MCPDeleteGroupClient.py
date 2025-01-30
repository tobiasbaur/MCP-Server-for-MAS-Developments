import socket
import json
import argparse

def send_delete_group_request(server_ip, server_port, token, group_name):
    """
    Sends a request to delete an existing group to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param group_name: Name of the group to delete
    :return: Response from the server
    """
    # Prepare the request payload
    payload = {
        "command": "delete_group",
        "token": token,
        "arguments": {
            "groupName": group_name
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
    # Argument parser for command-line arguments
    parser = argparse.ArgumentParser(description="Send a request to delete an existing group to the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--group-name", required=True, help="Name of the group to delete")

    args = parser.parse_args()

    # Send the delete group request and print the response
    response = send_delete_group_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.group_name
    )
    print("Response from server:", response)
