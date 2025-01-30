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

# Konfiguration laden
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "pgpt_openai_api_mcp.json")
    config = Config(config_file=config_file, required_fields=["server_ip", "server_port", "email", "password"])
except ConfigError as e:
    print(f"Configuration Error: {e}")
    exit(1)


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

            pgpt = PrivateGPTAgent(config)
            # remember that we already have an instance for the api key
            instance = ChatInstance(client_api_key, pgpt)
            instances.append(instance)

        print(f"💁 Request: {request.messages[len(request.messages) - 1].content}")
        response = pgpt.respond_with_context(request.messages)
        if "answer" not in response:
            response["answer"] = "No Response received"

    else:
        response = {
            "chatId": "0",
            "answer": "No Input given",
        }
    print(f"💡 Response: {response["answer"]}")
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




