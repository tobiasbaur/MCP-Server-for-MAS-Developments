import socket
import json
import argparse

def delete_source(server_ip, server_port, token, source_id):
    """
    Sends a request to the MCP server to delete an existing source.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authorization token
    :param source_id: ID of the source to delete
    :return: Response from the server
    """
    payload = {
        "command": "delete_source",
        "token": token,
        "arguments": {
            "sourceId": source_id
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
    parser = argparse.ArgumentParser(description="Delete a source from the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", type=int, required=True, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authorization token")
    parser.add_argument("--source-id", required=True, help="ID of the source to delete")

    args = parser.parse_args()

    response = delete_source(args.server_ip, args.server_port, args.token, args.source_id)
    print("Response from server:", response)
