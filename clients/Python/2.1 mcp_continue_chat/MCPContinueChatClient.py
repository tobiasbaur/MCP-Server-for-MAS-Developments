import socket
import json
import argparse

def send_continue_chat_request(server_ip, server_port, token, conversation_id, message):
    """
    Sends a request to continue an existing chat to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param conversation_id: ID of the chat to continue
    :param message: Message to send in the chat
    :return: Response from the server
    """
    payload = {
        "command": "continue_chat",
        "token": token,
        "arguments": {
            "chatId": conversation_id,
            "question": message
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
    parser = argparse.ArgumentParser(description="Continue an existing chat with the MCP server.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--conversation-id", required=True, help="ID of the chat to continue")
    parser.add_argument("--message", required=True, help="Message to send in the chat")

    args = parser.parse_args()

    response = send_continue_chat_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.conversation_id,
        args.message
    )
    print("Response from server:", response)
