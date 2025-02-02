<<<<<<< HEAD
import asyncio
import json
import time
import logging
=======
>>>>>>> 6c34cefbe81d36bc2a434262d7238f323fedc3bc
from pathlib import Path
from starlette.responses import StreamingResponse

from fastapi import FastAPI, Request
from threading import local
import uvicorn

from agents.OpenAI_Compatible_API_Agent.Python.open_ai_helper import _resp_sync, _resp_async_generator, get_models, \
    ChatCompletionRequest, ChatInstance
from ...AgentInterface.Python.agent import PrivateGPTAgent
from ...AgentInterface.Python.config import Config, ConfigError

app = FastAPI(title="OpenAI-compatible API for PrivateGPT using MCP")
request_context = local()
instances = []

# Konfiguration laden – hier sind die Felder "server_ip" und "server_port" nicht mehr erforderlich
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "pgpt_openai_api_mcp.json")
<<<<<<< HEAD
    config = Config(
        config_file=config_file,
        required_fields=["email", "password", "mcp_server"]
    )
    logging.info(config)
=======
    config = Config(config_file=config_file, required_fields=["server_ip", "server_port", "email", "password"])
    default_groups = config.get("groups", [])
>>>>>>> 6c34cefbe81d36bc2a434262d7238f323fedc3bc
except ConfigError as e:
    logging.error(f"Configuration Error: {e}")
    exit(1)

<<<<<<< HEAD
class ChatInstance:
    def __init__(self, api_key: str, agent: PrivateGPTAgent):
        self.api_key = api_key
        self.agent = agent

# data models
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "PGPT - Mistral NeMo 12B"
    messages: List[Message]
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = False
=======
>>>>>>> 6c34cefbe81d36bc2a434262d7238f323fedc3bc

@app.middleware("http")
async def store_request_headers(request: Request, call_next):
    request_context.headers = dict(request.headers)
    response = await call_next(request)
    return response

@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    headers = getattr(request_context, "headers", {})
    #print(headers)

    client_api_key = str(headers['authorization']).split(" ")[1]
    #print("API KEY: " + client_api_key)
    groups = default_groups
    if request.groups:
        groups = request.groups
    print("Groups: " + str(groups))

    if request.messages:
        #Check if this api-key already has a running instance
        indices = [i for i, x in enumerate(instances) if
                   x.api_key == client_api_key]
        index = -1
        if len(indices) > 0:
            index = indices[0]
        if index > -1:
            # if we already have an instance, just reuse it. No need to open new connection
            pgpt = instances[index].agent
            if pgpt.chosen_groups != groups:
                print("⚠️ New Groups requested, switching to new Chat..")
                config.set_value("groups", groups)
                instances[index].agent = PrivateGPTAgent(config)
                pgpt = instances[index].agent
        else:
            whitelist_keys = config.get("whitelist_keys", [])
            if len(whitelist_keys) > 0 and client_api_key not in whitelist_keys:
                response = {
                    "chatId": "0",
                    "answer": "API Key not valid",
                }
                print(f"💡 Response: {response["answer"]}")
                if request.stream:
                    return StreamingResponse(
                        _resp_async_generator(response, request), media_type="application/x-ndjson"
                    )
                else:
                    return _resp_sync(response, request)

            config.set_value("groups", groups)
            pgpt = PrivateGPTAgent(config)
            # remember that we already have an instance for the api key
            instance = ChatInstance(client_api_key, pgpt)
            instances.append(instance)

        print(f"💁 Request: {request.messages[len(request.messages) - 1].content}")
        # "oai_comp_api_chat",
        # "oai_comp_api_continue_chat"
        # 'chat'
        response = pgpt.respond_with_context(request.messages, request.response_format, request.tools, command="chat")


    else:
        response = {
            "chatId": "0",
            "answer": "No Input given",
        }
    if 'answer' in response:
        print(f"💡 Response: {response["answer"]}")

    elif 'error' in response:
        print(f"❌ Error: {response["error"]}")
        response = {
            "chatId": "0",
            "answer": str(response["error"]),
        }
    else:
        response = {
            "chatId": "0",
            "answer": str(response),
        }

    if request.stream:
        return StreamingResponse(
            _resp_async_generator(response, request), media_type="application/x-ndjson"
        )
    else:
        return _resp_sync(response, request)



@app.get("/models")
def return_models():
    return get_models()



if __name__ == "__main__":
    api_ip = config.get("api_ip", "0.0.0.0")
    api_port = config.get("api_port", 8002)
    uvicorn.run(app, host=api_ip, port=int(api_port))




