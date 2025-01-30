import socket
import json
import argparse
import sys

def send_store_user_request(server_ip, server_port, token, name, email, password, language, timezone, roles, groups, usePublic, activateFtp, ftpPassword):
    """
    Sends a request to create a new user on the MCP server.

    :param server_ip: IP address of the MCP server
    :param server_port: Port number of the MCP server
    :param token: Authentication token
    :param name: Name of the new user
    :param email: Email of the new user
    :param password: Password for the new user
    :param language: Preferred language of the new user
    :param timezone: Timezone of the new user
    :param roles: Roles assigned to the new user
    :param groups: Groups assigned to the new user
    :param usePublic: Whether to use the public knowledge base
    :param activateFtp: Whether to activate FTP for the user
    :param ftpPassword: FTP password for the user
    :return: Response from the server
    """

    payload = {
        "command": "store_user",
        "token": token,
        "arguments": {
            "name": name,
            "email": email,
            "password": password,
            "language": language,
            "timezone": timezone,
            "roles": roles,
            "groups": groups,
            "usePublic": usePublic,
            "activateFtp": activateFtp,
            "ftpPassword": ftpPassword
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
        description="Send a request to create a new user on the MCP server.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--server-ip", required=True, help="IP address of the MCP server\nExample: --server-ip 192.168.0.1")
    parser.add_argument("--server-port", required=True, type=int, help="Port number of the MCP server\nExample: --server-port 5000")
    parser.add_argument("--token", required=True, help="Authentication token\nExample: --token YOUR_AUTH_TOKEN")
    parser.add_argument("--name", required=True, help="Name of the user\nExample: --name 'Max Mustermann'")
    parser.add_argument("--email", required=True, help="Email of the user\nExample: --email max@example.com")
    parser.add_argument("--password", required=True, help="Password for the user\nExample: --password 'SuperSecret42!'")
    parser.add_argument("--language", default="en", help="Language code (optional)\nExample: --language de")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Timezone (optional)\nExample: --timezone 'Europe/Berlin'")
    parser.add_argument("--roles", nargs="+", default=[], help="Roles for the user (optional)\nExample: --roles Admin User")
    parser.add_argument("--groups", nargs="+", default=[], help="Groups for the user (optional)\nExample: --groups GroupA GroupB")
    parser.add_argument("--usePublic", action="store_true", help="Use the public knowledge base")
    parser.add_argument("--activateFtp", action="store_true", help="Activate FTP for the user")
    parser.add_argument("--ftpPassword", default="", help="FTP password for the user (optional)\nExample: --ftpPassword 'MyFTP$Password'")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    response = send_store_user_request(
        args.server_ip,
        args.server_port,
        args.token,
        args.name,
        args.email,
        args.password,
        args.language,
        args.timezone,
        args.roles,
        args.groups,
        args.usePublic,
        args.activateFtp,
        args.ftpPassword
    )
    print("Response from server:", response)
