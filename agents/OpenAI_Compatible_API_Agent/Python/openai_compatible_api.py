from pathlib import Path

from starlette.responses import StreamingResponse

from fastapi import FastAPI, Request
from threading import local

from agents.OpenAI_Compatible_API_Agent.Python.open_ai_helper import ChatInstance, \
    ChatCompletionRequest, _resp_sync, _resp_async_generator, get_models
from .pgpt_api import PrivateGPTAPI

from ...AgentInterface.Python.config import Config, ConfigError
import uvicorn

app = FastAPI(title="OpenAI-compatible API for PrivateGPT")
request_context = local()
instances = []

# Konfiguration laden
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "pgpt_openai_api_proxy.json")
    config = Config(config_file=config_file, required_fields=["base_url"])
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
    client_api_key = str(headers['authorization']).split(" ")[1]

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
            #otherwise connect via api-key
            pgpt = PrivateGPTAPI(config, client_api_key=client_api_key)
            # remember that we already have an instance for the api key
            instance = ChatInstance(client_api_key, pgpt)
            instances.append(instance)

        if pgpt.logged_in:
            response = pgpt.respond_with_context(request.messages)
            if "answer" not in response:
                response["answer"] = "No Response received"
        else:
            response = {
                "chatId": "0",
                "answer": "API Key not valid",
            }
    else:
        response = {
            "chatId": "0",
            "answer": "No Input given",
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



