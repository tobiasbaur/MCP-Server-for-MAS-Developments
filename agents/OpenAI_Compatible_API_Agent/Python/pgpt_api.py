import json
import re
from pathlib import Path

import requests
import urllib3
import base64

from ...AgentInterface.Python.config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def initialize_session(proxy_user, proxy_password, access_header):
    """Set up the session with proxy authentication."""
    session = requests.Session()
    session.verify = False
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if access_header is not None:
        headers['X-Custom-Header'] = access_header
    elif proxy_user is not None and proxy_password is not None:
            auth = base64.b64encode(f"{proxy_user}:{proxy_password}".encode()).decode()
            headers['Authorization'] = f'Basic {auth}'
    session.headers.update(headers)
    return session


class PrivateGPTAPI:
    def __init__(self, config, client_api_key=None):
        """Initialize the chat client with proxy authentication."""
        self.token = None
        self.chat_id = None

        self.base_url = config.get("base_url")
        self.proxy_user = config.get("proxy_user", None)
        if self.proxy_user == "":
            self.proxy_user = None
        self.proxy_password = config.get("proxy_password", None)
        if self.proxy_password == "":
            self.proxy_password = None
        self.access_header = config.get("access_header", None)
        if self.access_header == "":
            self.access_header = None

        self.chosen_groups = config.data["groups"] or []
        self.language = config.get("language", "en")
        self.use_public = config.get("use_public", True)
        self.whitelist_keys = config.get("whitelist_keys", [])
        self.logged_in = False


        if client_api_key is not None:
            self.email, self.password = decrypt_api_key(client_api_key)
            if len(self.whitelist_keys) > 0:
                if client_api_key not in self.whitelist_keys:
                    print("not authorized")

        self.session = initialize_session(self.proxy_user, self.proxy_password, self.access_header)
        if self.login():
            if self.create_chat():
                self.logged_in = True


    def login(self):
        """Authenticate the user and retrieve the token."""
        url = f"{self.base_url}/login"
        payload = {"email": self.email, "password": self.password}
        try:
            response = self.session.post(url, json=payload)
            print(response.content)
            response.raise_for_status()
            data = response.json()
            self.token = data['data']['token']
            
            # Prüfen, ob der Header bereits existiert
            if 'Authorization' in self.session.headers:
                self.session.headers['Authorization'] += f', Bearer {self.token}'
            else:
                self.session.headers['Authorization'] = f'Bearer {self.token}'
            
            print("✅ Login successful.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Login failed: {e}")
        return False

    def create_chat(self):
        """Start a new chat session."""
        url = f"{self.base_url}/chats"
        payload = {"language": self.language, "question": "Hello", "usePublic": self.use_public, "groups": self.chosen_groups}
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            self.chat_id = data['data']['chatId']
            print("✅ Chat initialized.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to create chat: {e}")
            return False

    def query_private_gpt(self, user_input) -> json:
        """Send a question to the chat and retrieve the response."""
        if not self.chat_id:
            print("❌ Chat session not initialized.")
            return False
        url = f"{self.base_url}/chats/{self.chat_id}"
        payload = {"question": user_input}
        try:
            response = self.session.patch(url, json=payload)
            #response.raise_for_status()
            data = response.json()
            answer = data.get('data', {}).get('answer', "error")
            if answer.startswith("{\"role\":"):
                 answerj = json.loads(answer)
                 data["data"]["answer"] = answerj["content"]
                 data["data"]["chatId"] = "0"

            print(f"💡 Response: {answer}")
            return data
        except requests.exceptions.RequestException as e:
            # It seems we get disconnections from time to time..
            #print(f"⚠️ Failed to get response on first try, trying again..: {e}")
            try:
                response = self.session.patch(url, json=payload)
                response.raise_for_status()
                data = response.json()
                answer = data.get('data', {}).get('answer', "No answer provided.")
                print(f"💡 Response: {answer}")
                return data
            except:
                print(f"❌ Failed to get response: {e}")
                return {"error": f"❌ Failed to get response: {e}"}


    def get_document_info(self, source_id):
        """Send a source id to retrieve details. Working with version 1.3.3 and newer"""
        url = f"{self.base_url}/sources/{source_id}"
        try:
            response = self.session.get(url)
            data = response.json()
            info = data.get('data', {})
            print(f"💡 Response: {str(info)}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get response: {e}")
            return {"error": f"❌ Failed to get response: {e}"}


    def respond_with_context(self, messages, response_format=None, request_tools=None):
        last_user_message = next((p for p in reversed(messages) if p.role == "user"), None)
        user_input = last_user_message.content

        for message in messages:
            if message.role == "system":
                user_input = str(message)

        last_assistant_message = next((p for p in reversed(messages) if p.role == "assistant"), None)
        last_tool_message = next((p for p in reversed(messages) if p.role == "tool"), None)

        hastoolresult = False
        if last_tool_message is not None and last_assistant_message is not None and last_assistant_message.tool_calls is not None and len(last_assistant_message.tool_calls) > 0:
            user_input += "you called the tool: " + str(last_assistant_message.tool_calls[0]) + ". The result was: " + last_tool_message.content
            hastoolresult = True



        #Check if the latest message was a tool command.
        #add_tool_call_reply = True
        #if messages[len(messages) - 1].role == "tool":
        #    add_tool_call_reply = False


        last_user_message = next((p for p in reversed(messages) if p.role == "user"), None)
        #print(last_user_message)
        if last_user_message.content is not None:
            user_input += " " + str(last_user_message)


        print(f"💁 Request: " + user_input)

        # PGPT manages history and context itself so we don't need to forward the history.
        add_context = False
        if add_context:
            messages.pop()
            user_input += "\nHere is some context about the previous conversation:\n"
            for message in messages:
                user_input += f"{message.role}: {message.content}\n"

        if response_format is not None:
            print("Response format: " + str(response_format))
            user_input += add_response_format(response_format)

        if request_tools is not None and not hastoolresult:
            user_input += add_tools(request_tools, last_tool_message)

        result = self.query_private_gpt(user_input)

        if 'data' in result:
            response_data = result.get("data")
            if request_tools is not None and not hastoolresult and is_json(clean_response(response_data.get("answer"))):
                response_data["tool_call"] = clean_response(response_data.get("answer", ""))
            return response_data
        elif 'error' in result:
            # Try to login again and send the query once more on error.
            if self.login():
                if self.create_chat():
                    result = self.query_private_gpt(user_input)
                    if 'data' in result:
                        return result['data']
                    else:
                        return result

        else:
            return result

def is_json(myjson):
  try:
    json.loads(myjson)
  except ValueError as e:
    return False
  return True

def add_response_format(response_format):
    #prompt = "\nPlease fill in the following template with realistic and appropriate information. Be creative. The field 'type' defines the output format. In your reply, only return the generated json\n"
    prompt = "\nPlease fill in the following json template with realistic and appropriate information. In your reply, only return the generated json. If you can't answer return an empty json.\n"
    prompt += json.dumps(response_format)
    return prompt


def add_tools(response_tools, last_tool_message):
    #if last_tool_message is not None:
    #    prompt = "\nDescribe what you are doing with the tool to generate the answer."
    #else:
    prompt = "\nPlease select the fitting provided tool to create your answer. Only return the generated result of the tool.\n"
    index = 1
    for tool in response_tools:
        prompt += "\n" + json.dumps(tool) + "\n"
        index += 1

    return prompt

def clean_response(response):
    # Remove artefacts from reply here
    response = response.replace("[TOOL_CALLS] ", "")
    return response

def decrypt_api_key(api_key):
    """
    This is PoC code and methods should be replaced with a more secure way to deal with credentials (e.g. in a db)
    """
    try:
        base64_bytes = api_key.encode("ascii")
        decoded_string_bytes = base64.b64decode(base64_bytes)
        decoded_key = decoded_string_bytes.decode("ascii")
    except Exception as e:
        print(e)
        decoded_key = "invalid:invalid"

    return decoded_key.split(":")[0], decoded_key.split(":")[1]


def main():
    """Main function to run the chat application."""
    config_file = Path.absolute(Path(__file__).parent.parent / "pgpt_openai_api_proxy.json")
    config = Config(config_file=config_file, required_fields=["base_url"])
    chat = PrivateGPTAPI(config)

    print("Type your questions below. Type 'quit' to exit.")
    while True:
        try:
            question = input("❓ Question: ").strip()
            if question.lower() == 'quit':
                break
            if question:
                 chat.query_private_gpt(question)
        except KeyboardInterrupt:
            print("\nExiting chat...")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            break


if __name__ == "__main__":
    main()