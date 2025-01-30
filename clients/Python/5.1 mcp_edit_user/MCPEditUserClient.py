import socket
import json
import argparse
import sys

def send_edit_user_request(server_ip, server_port, token, name=None, email=None, password=None, language=None,
                           timezone=None, roles=None, groups=None, use_public=False, activate_ftp=False, ftp_password=None):
    """
    Sends a request to edit an existing user to the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param user_id: ID of the user to edit
    :param token: Authentication token
    :param name: New name of the user
    :param email: New email of the user
    :param password: New password of the user
    :param language: Preferred language of the user
    :param timezone: Timezone of the user
    :param roles: List of roles to assign to the user
    :param groups: List of groups to assign to the user
    :param use_public: Whether to enable public knowledge base access
    :param activate_ftp: Whether to activate FTP access
    :param ftp_password: Password for FTP access
    :return: Response from the server
    """
    payload = {
        "command": "edit_user",
        "token": token,
        "arguments": {
            "name": name,
            "email": email,
            "password": password,
            "language": language,
            "timezone": timezone,
            "roles": roles or [],
            "groups": groups or [],
            "usePublic": use_public,
            "activateFtp": activate_ftp,
            "ftpPassword": ftp_password
        }
    }

    # Remove keys with None values
    payload["arguments"] = {k: v for k, v in payload["arguments"].items() if v is not None}

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
        description="Send a request to edit an existing user to the MCP server.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server\nExample: --server-ip 192.168.0.1")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server\nExample: --server-port 5000")
    parser.add_argument("--token", required=True, help="Authentication token\nExample: --token YOUR_AUTH_TOKEN")
    parser.add_argument("--name", help="New name of the user\nExample: --name 'John Doe'")
    parser.add_argument("--email", help="New email of the user\nExample: --email john.doe@example.com")
    parser.add_argument("--password", help="New password of the user\nExample: --password NewSecret42!")
    parser.add_argument("--language", help="Preferred language of the user\nExample: --language en")
    parser.add_argument("--timezone", help="Timezone of the user\nExample: --timezone UTC")
    parser.add_argument("--roles", nargs="*", help="List of roles to assign to the user\nExample: --roles Admin User")
    parser.add_argument("--groups", nargs="*", help="List of groups to assign to the user\nExample: --groups Group1 Group2")
    parser.add_argument("--usePublic", action="store_true", help="Enable public knowledge base access\nExample: --usePublic")
    parser.add_argument("--activateFtp", action="store_true", help="Activate FTP access\nExample: --activateFtp")
    parser.add_argument("--ftpPassword", help="Password for FTP access\nExample: --ftpPassword NewValidFTP1$")

    # If no arguments are provided, print help and exit
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    response = send_edit_user_request(
        args.server_ip,
        args.server_port,
        args.token,
        name=args.name,
        email=args.email,
        password=args.password,
        language=args.language,
        timezone=args.timezone,
        roles=args.roles,
        groups=args.groups,
        use_public=args.usePublic,
        activate_ftp=args.activateFtp,
        ftp_password=args.ftpPassword
    )
    print("Response from server:", response)
