import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Optional, List
from threading import local

import tiktoken
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from fastapi import FastAPI, Request, HTTPException

# --- Setup Standard Logging ---
logging.basicConfig(
    level=logging.INFO,  # Set to WARNING or ERROR in production
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Import Required Modules ---
# WARNING: Adjust the import paths based on your project structure.
from agents.OpenAI_Compatible_API_Agent.Python.open_ai_helper import (
    ChatInstance,
    ChatCompletionRequest,
    CompletionRequest,
    _resp_sync,
    _resp_async_generator,
    models,
    Message,
    _resp_async_generator_completions,
    _resp_sync_completions
)
from ...AgentInterface.Python.agent import PrivateGPTAgent
from ...AgentInterface.Python.config import Config, ConfigError

# Initialize FastAPI Application
app = FastAPI(title="OpenAI-Compatible API for PrivateGPT using MCP")

# Thread-local context storage for request headers
request_context = local()

# --- OPTIMIZATION: Use Dictionary Instead of List for Instances (O(1) lookup) ---
instances = {}

# Load Configuration
try:
    config_file = Path.absolute(Path(__file__).parent.parent / "pgpt_openai_api_mcp.json")
    config = Config(
        config_file=config_file,
        required_fields=["email", "password", "mcp_server"]
    )
    logger.info(f"Configuration loaded: {config}")
except ConfigError as e:
    logger.error(f"Configuration Error: {e}")
    exit(1)

# --- OPTIMIZATION: Load a Global PrivateGPTAgent Instance (if state is not user-specific) ---
GLOBAL_AGENT = PrivateGPTAgent(config)
logger.info("Global PrivateGPTAgent instance initialized.")

# Data Models for Requests
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "PGPT - Mistral NeMo 12B"
    messages: List[Message]
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = False

# Middleware to Store Request Headers for Later Use
@app.middleware("http")
async def store_request_headers(request: Request, call_next):
    request_context.headers = dict(request.headers)
    response = await call_next(request)
    return response

# Endpoint: Chat Completions
@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    headers = getattr(request_context, "headers", {})
    client_api_key = str(headers['authorization']).split(" ")[1]
    logger.info(f"[/chat/completions] Request received with API key: {client_api_key}")

    if request.messages:
        # Retrieve or Create Chat Instance
        if client_api_key in instances:
            pgpt = instances[client_api_key].agent
        else:
            # Check if API key is in the whitelist (if applicable)
            whitelist_keys = config.get("whitelist_keys", [])
            if len(whitelist_keys) > 0 and client_api_key not in whitelist_keys:
                response = {
                    "chatId": "0",
                    "answer": "API Key not valid",
                }
                logger.warning(f"Invalid API key: {client_api_key}")
                if request.stream:
                    return StreamingResponse(
                        _resp_async_generator(response, request),
                        media_type="application/x-ndjson"
                    )
                else:
                    return _resp_sync(response, request)

            # Use global agent instead of creating a new one
            pgpt = GLOBAL_AGENT
            instances[client_api_key] = ChatInstance(client_api_key, pgpt)
            logger.info(f"New chat instance created for API key {client_api_key}.")

        # Generate response
        response = pgpt.respond_with_context(request.messages)
        if "answer" not in response:
            response["answer"] = "No Response received"
    else:
        response = {
            "chatId": "0",
            "answer": "No input provided",
        }

    logger.info(f"💡 Response (preview): {response['answer'][:80]}...")
    if request.stream:
        return StreamingResponse(
            _resp_async_generator(response, request), 
            media_type="application/x-ndjson"
        )
    else:
        return _resp_sync(response, request)

# Endpoint: Text Completions
@app.post("/completions")
async def completions(request: CompletionRequest):
    headers = getattr(request_context, "headers", {})
    client_api_key = str(headers['authorization']).split(" ")[1]
    logger.info(f"[/completions] Request received with API key: {client_api_key}")

    if request.prompt:
        # Check if API key is in the whitelist (if applicable)
        whitelist_keys = config.get("whitelist_keys", [])
        if len(whitelist_keys) > 0 and client_api_key not in whitelist_keys:
            response = {
                "chatId": "0",
                "answer": "API Key not valid",
            }
            logger.warning(f"Invalid API key: {client_api_key}")
            if request.stream:
                return StreamingResponse(
                    _resp_async_generator(response, request),
                    media_type="application/x-ndjson"
                )
            else:
                return _resp_sync(response, request)

        # Use global agent instead of creating a new one
        pgpt = GLOBAL_AGENT
        response = pgpt.respond_with_context([Message(role="user", content=request.prompt)])
        if "answer" not in response:
            response["answer"] = "No Response received"
    else:
        response = {
            "chatId": "0",
            "answer": "No input provided",
        }

    logger.info(f"💡 Response (preview): {response['answer'][:80]}...")
    if request.stream:
        return StreamingResponse(
            _resp_async_generator_completions(response, request),
            media_type="application/x-ndjson"
        )
    else:
        return _resp_sync_completions(response, request)

# Endpoint: Retrieve Available Models
@app.get("/models")
def return_models():
    return {
        "object": "list",
        "data": models
    }

@app.get('/models/{model_id}')
async def get_model(model_id: str):
    filtered_entries = list(filter(lambda item: item["id"] == model_id, models))
    entry = filtered_entries[0] if filtered_entries else None
    if entry is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return entry

# Start FastAPI Server
if __name__ == "__main__":
    import uvicorn
    api_ip = config.get("api_ip", "0.0.0.0")
    api_port = config.get("api_port", 8002)
    logger.info(f"Starting API on http://{api_ip}:{api_port}")
    uvicorn.run(app, host=api_ip, port=int(api_port))
