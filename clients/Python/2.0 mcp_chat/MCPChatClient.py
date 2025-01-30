import socket
import json
import argparse

def send_mcp_request(server_ip, server_port, token, question, use_public, groups=None, language="de"):
    """
    Sends a question to an MCP server and retrieves the response.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token for the MCP server
    :param question: The question to send
    :param use_public: Whether to use the public knowledge base
    :param groups: List of groups for retrieval-augmented generation
    :param language: Language code for the request
    :return: Response from the server
    """
    # Prepare the request payload
    payload = {
        "command": "chat",
        "token": token,
        "arguments": {
            "question": question,
            "usePublic": use_public,
            "groups": groups or [],
            "language": language
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
            return json.loads(response.decode('utf-8'))

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a question to the MCP server and retrieve the response.")
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--question", required=True, help="The question to ask the MCP server")
    parser.add_argument("--use-public", action="store_true", help="Use the public knowledge base")
    parser.add_argument("--groups", nargs="*", help="List of groups for retrieval-augmented generation", default=[])
    parser.add_argument("--language", default="de", help="Language code for the request (default: 'de')")

    args = parser.parse_args()

    # Send the question to the MCP server
    response = send_mcp_request(
        server_ip=args.server_ip,
        server_port=args.server_port,
        token=args.token,
        question=args.question,
        use_public=args.use_public,
        groups=args.groups,
        language=args.language
    )

    print("Response from server:", json.dumps(response, indent=2, ensure_ascii=False))