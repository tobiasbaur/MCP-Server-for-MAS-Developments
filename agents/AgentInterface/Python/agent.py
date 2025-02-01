# Python/agent.py

import logging
import json
import atexit
from .network import NetworkClient, NetworkError
from .color import Color
from .language import languages

class GroupValidationError(Exception):
    """Exception raised for errors in the group validation process."""
    pass

class PrivateGPTAgent:

    def __init__(self, config):

        logging.basicConfig(
            level=logging.ERROR,
            encoding= "utf-8",
            format='%(asctime)s %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler("agent.log"),
                logging.StreamHandler()
            ]
        )


        self.config = config
        self.server_ip = config.get("server_ip")
        self.server_port = config.get("server_port")
        self.email = config.get("email")
        self.password = config.get("password")
        self.chosen_groups = config.data["groups"] or []
        self.language = config.get("language", "en")  # Standard ist Englisch
        self.api_key = config.get("api_key", "default_api_key")  # Stellen Sie sicher, dass ein API-Key gesetzt ist

        # Überprüfen, ob die gewählte Sprache unterstützt wird
        if self.language not in languages:
            self.language = "en"
            logging.warning(f"Unsupported language '{config.get('language')}'. Falling back to English.")

        self.lang = languages[self.language]  # Sprachwörterbuch für die gewählte Sprache

        self.network_client = NetworkClient(self.server_ip, self.server_port, language=self.language)
        self.token = None

        # Register logout to be called upon exit
        atexit.register(self.logout)

        # Perform login
        self.login()

        # Fetch personal groups
        if self.token:
            self.allowed_groups = self.list_personal_groups()
            if not self.allowed_groups:
                logging.warning(self.lang["no_personal_groups"])
                print(self.lang["no_personal_groups"], flush=True)
                self.allowed_groups = []

            # Validate groups
            invalid = self.validate_groups(self.chosen_groups)
            if invalid:
                # Dem Benutzer eine Meldung ausgeben, bevor wir den Agenten beenden.
                print(self.lang["invalid_group"].format(groups=invalid), flush=True)
                logging.error(self.lang["invalid_group_error"])
                raise GroupValidationError(self.lang["invalid_group"].format(groups=invalid))
        else:
            self.allowed_groups = []

        # Local knowledge base
        self.knowledge_base = {
            "What is AI?": self.lang["knowledge_ai"],
            "Who created Python?": self.lang["knowledge_python"],
            "What is Machine Learning?": self.lang["knowledge_ml"]
        }

    def get_lang_message(self, key, **kwargs):
        """
        Sichere Methode zum Abrufen von Nachrichten aus dem Sprachwörterbuch.
        Wenn der Schlüssel nicht existiert, wird eine Standardnachricht zurückgegeben.
        """
        message = self.lang.get(key, "Message not defined.")
        try:
            #return message
            return message.format(**kwargs,  encoding="utf-8")
        except KeyError as e:
            logging.error(f"Missing placeholder in language file for key '{key}': {e}")
            return message

    def validate_groups(self, groups):
        """
        Überprüft, ob alle ausgewählten Gruppen in self.allowed_groups vorhanden sind.
        Gibt eine Liste der ungültigen Gruppen zurück.
        """
        if groups is None:
            return []
        invalid = [g for g in groups if g not in self.allowed_groups]
        if invalid:
            logging.error(self.get_lang_message("group_validation_error", error=invalid))
            return invalid  # Rückgabe der Liste der ungültigen Gruppen
        return []  # Leere Liste bedeutet, dass alle Gruppen gültig sind

    def login(self):
        payload = {
            "command": "login",
            "arguments": {
                "email": self.email,
                "password": self.password
            }
        }
        logging.info(self.get_lang_message("login_attempt"))
        try:
            resp = self.network_client.send_request(payload)
            logging.info(self.get_lang_message("received_response", response=resp))

            if resp.get("status") == 200 and resp.get("message") == "success":
                self.token = resp.get("token")
                logging.info(self.get_lang_message("login_success"))
                return True
            else:
                msg = resp.get("message", self.get_lang_message("no_server_message"))
                logging.error(self.get_lang_message("login_failed", message=msg))
                return False
        except NetworkError as e:
            logging.error(self.get_lang_message("login_failed", message=str(e)))
            return False

    def list_personal_groups(self):
        if not self.token:
            logging.error(self.get_lang_message("authentication_failed"))
            return []

        payload = {
            "command": "list_groups",
            "token": self.token
        }
        try:
            resp = self.network_client.send_request(payload)
            data_block = resp.get("data")
            if not data_block:
                #logging.warning(self.lang["no_data_in_response"].format(response=resp))
                return []

            if data_block.get("status") == 200 and data_block.get("message") == "success":
                personal = data_block.get("personalGroups", [])
                #logging.info(self.lang["personal_groups"].format(groups=personal))
                return personal
            else:
                #logging.warning(self.lang["list_groups_failed"].format(message=data_block.get("message", self.lang["no_server_message"])))
                return []
        except NetworkError as e:
            logging.error(self.lang["list_groups_failed"].format(message=str(e)))
            return []

    def query_private_gpt(self, prompt, use_public=False, language="en", groups=None, command="chat"):
        if not self.token:
            error_msg = self.get_lang_message("authentication_failed")
            logging.error(error_msg)
            return json.dumps({"error": error_msg})

        # Validieren der Sprache
        if language not in languages:
            language = 'en'
            logging.warning(f"Unsupported language '{language}'. Falling back to English.")

        lang = languages[language]

        # Use provided groups or default to self.chosen_groups
        if groups is None:
            groups = self.chosen_groups
        else:
            # Entferne leere Strings und trimme Gruppen
            groups = [g.strip() for g in groups if g.strip()]

        # Validate and filter groups based on allowed_groups
        relevant_groups = [g for g in groups if g in self.allowed_groups]

        payload = {
            "command": command,
            "token": self.token,
            "arguments": {
                "question": prompt,
                "usePublic": use_public,
                "groups": relevant_groups,
                "language": language
            }
        }
        logging.info(lang["sending_payload"].format(payload=json.dumps(payload)))
        try:
            resp = self.network_client.send_request(payload)
            logging.info(lang["received_response"].format(response=resp))
            if resp.get("status") == 200 and resp.get("message") == "success":
                content = resp.get("content", {})
                #answer = content.get("answer", lang["agent_error"].format(error=lang["no_answer_received"]))
                return content
            else:
                return {"error": resp.get("message", lang["agent_error"].format(error=lang["unknown_error"]))}
        except NetworkError as e:
            error_msg = lang["agent_error"].format(error=str(e))
            logging.error(f"❌ {error_msg}")
            return json.dumps({"error": error_msg})



    def respond(self, user_input, groups=None):
        response = self.knowledge_base.get(user_input, None)
        if response:
            logging.info(self.get_lang_message("knowledge_response", input=user_input))
            return json.dumps({"answer": response})
        else:
            return self.query_private_gpt(user_input, groups=groups)

    def respond_with_context(self, messages, response_format=None, request_tools = None, command="chat"):
        user_input = f'{messages[len(messages) - 1].content}'
        for message in messages:
            if message.role == "system":
                user_input = str(message) + " " + str(messages[len(messages) - 1])

        # PGPT manages history and context itself so we don't need to forward the history.
        add_context = False
        if add_context:
            messages.pop()
            user_input += "\nHere is some context about the previous conversation:\n"
            for message in messages:
                user_input += f"{message.role}: {message.content}\n"

        if response_format is not None:
            user_input += self.add_response_format(response_format)

        if request_tools is not None:
            user_input += self.add_tools(request_tools)

        result = self.query_private_gpt(user_input, command=command)
        if 'error' in result:
            # Try to login again and send the query once more on error.
            if self.login():
                result = self.query_private_gpt(user_input, command=command)
                return result

        return result


    def add_response_format(self, response_format):
        prompt = "\nPlease fill in the following json template with realistic and appropriate information. In your reply, only return the generated json. If you can't answer return an empty json.\n"
        prompt += json.dumps(response_format)
        return prompt

    def add_tools(self, response_tools):
        prompt = "\nPlease use the following provided tools. In your reply, only return the generated result of the tool\n"
        for tool in response_tools:
            prompt += json.dumps(tool)
        return prompt

    def send_create_source_request(self, name, content, groups):
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
            "token": self.token,
            "arguments": {
                "name": name,
                "content": content,
                "groups": groups or []
            }
        }

        try:
            resp = self.network_client.send_request(payload)
            logging.info(self.lang["received_response"].format(response=resp))
            print(resp)
            if resp.get("status") == 200 and resp.get("message") == "success":
                return json.dumps(resp["data"])
            else:
                return json.dumps(
                    {"error": resp.get("message", self.lang["agent_error"].format(error=self.lang["unknown_error"]))})
        except NetworkError as e:
            error_msg = self.lang["agent_error"].format(error=str(e))
            logging.error(f"❌ {error_msg}")
            return json.dumps({"error": error_msg})

    def delete_source(self, source_id):
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
            "token": self.token,
            "arguments": {
                "sourceId": source_id
            }
        }

        try:
            response = self.network_client.send_request(payload)
            logging.info(self.lang["received_response"].format(response=response))
            resp = response.get("data")

            if resp.get("status") == 200 and resp.get("message") == "success":
                return json.dumps(resp["data"])
            else:
                return json.dumps(
                    {"error": resp.get("message", self.lang["agent_error"].format(error=self.lang["unknown_error"]))})
        except NetworkError as e:
            error_msg = self.lang["agent_error"].format(error=str(e))
            logging.error(f"❌ {error_msg}")
            return json.dumps({"error": error_msg})


    def send_list_sources_request(self, group_name):
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
            "token": self.token,
            "attributes": {
                "groupName": group_name
            }
        }

        try:
            response = self.network_client.send_request(payload)
            logging.info(self.lang["received_response"].format(response=response))
            resp = response.get('content')

            if resp.get("status") == 200 and resp.get("message") == "success":
                return json.dumps(resp["data"])
            else:
                return json.dumps(
                    {"error": response.get("message", self.lang["agent_error"].format(error=self.lang["unknown_error"]))})
        except NetworkError as e:
            error_msg = self.lang["agent_error"].format(error=str(e))
            logging.error(f"❌ {error_msg}")
            return json.dumps({"error": error_msg})

    def logout(self):
        if not self.token:
            logging.info(self.get_lang_message("no_token_logout"))
            return

        payload = {
            "command": "logout",
            "token": self.token
        }
        logging.info(self.get_lang_message("logout_attempt"))
        try:
            resp = self.network_client.send_request(payload)
            logging.info(self.get_lang_message("received_response", response=resp))

            if resp.get("status") == 200 and resp.get("message") == "success":
                logging.info(self.get_lang_message("logout_success"))
                self.token = None
            else:
                msg = resp.get("message", self.get_lang_message("no_server_message"))
                logging.warning(self.get_lang_message("logout_failed", message=msg))
        except NetworkError as e:
            logging.error(self.get_lang_message("logout_failed", message=str(e)))


    def run(self):
        pass


