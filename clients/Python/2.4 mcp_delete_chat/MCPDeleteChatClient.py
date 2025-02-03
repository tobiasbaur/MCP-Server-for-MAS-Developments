import socket
import json
import argparse

def send_delete_chat_request(server_ip, server_port, token, chat_id):
    """
    Sends a request to delete a specific chat from the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param chat_id: ID of the chat to be deleted
    :return: Response from the server
    """
    payload = {
        "command": "delete_chat",
        "token": token,
        "arguments": {
            "chatId": chat_id
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
    parser = argparse.ArgumentParser(description="Delete a specific chat on the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--chat-id", required=True, help="ID of the chat to be deleted")

    args = parser.parse_args()

    response = send_delete_chat_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.chat_id
    )
    print("Response from server:", response)
