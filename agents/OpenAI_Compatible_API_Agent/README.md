# PrivateGPT OpenAI-Compatible API Agent

## Description
The PrivateGPT OpenAI-Compatible API Agent is a client that communicates with a private GPT server and provides an interface to openai-compatible libraries and tools.
It comes in two variations. Variation 1 (*openai_compatible_api.p*) uses the PGPT API directly, Variation 2 (*openai_mcp_api.py*) uses communicates through the PGPT MCP Server.

---

## Prerequisites
- Python 3.8 or higher
- Access to the PrivateGPT server
- For Variation 2, access to MCP server

---

## Setup
1. **Clone the repository:**
    ```bash
    git clone [https://github.com/pgpt-dev/MCP-Server-for-MAS-Developments.git](https://github.com/pgpt-dev/MCP-Server-for-MAS-Developments.git)
    cd MCP-Server-for-MAS-Developments
    ```

2. **Optional: Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    ```

    - **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```

    - **Unix/MacOS:**
        ```bash
        source venv/bin/activate
        ```

3. **Install dependencies:**
    ```bash
    pip install -r .\agents\OpenAI_Compatible_API_Agent\requirements.txt
    ```

4. **Customise configuration file:**

   - 4.1 **OpenAI-Compatible API via PGPT API:**

       Copy the `pgpt_api_proxy.json.example` file to `pgpt_api_proxy.json` e.g. with  `cp  .\agents\OpenAI_Compatible_API_Agent\pgpt_api_proxy.json.example  .\agents\OpenAI_Compatible_API_Agent\pgpt_api_proxy.json`
       Make sure that the `pgpt_api_proxy.json` is configured correctly and contains all necessary fields. The file should look like this:
       ```json
        {
            "base_url": "<Url to your private GPT instance>",
            "proxy_user": "<Proxy User>",
            "proxy_password": "<Proxy Password>",
            "access_header": "<Access Header>", // The access header will be used instead of User and Password, if available
            "groups": ["<Groups to access>"],
            "language": "en",
            "use_public": true,
            "api_ip": "0.0.0.0",
            "api_port": 8001,
            "whitelist_keys": ["key1", "key2"] // Generate API key with generate_key.py for individual users, add them here to give access, leave empty to avoid checks
        }
       ```
      - 4.2 **OpenAI-Compatible API via MCP Server:**

       Copy the `pgpt_openai_api_mcp.json.example` file to `pgpt_openai_api_mcp.json` e.g. with  `cp .\pgpt_openai_api_mcp.json.example .\pgpt_openai_api_mcp.json`
       Make sure that the `pgpt_openai_api_mcp.json` is configured correctly and contains all necessary fields. The file should look like this:
       ```json
        {
            "email": "<Your PGPT account>",
            "password": "<Your PGPT password>",
            "groups": ["<Groups to access>"],
            "language": "en",
            "api_ip": "0.0.0.0",
            "api_port": 8002,
            "whitelist_keys": ["key1", "key2"], // Generate API key with generate_key.py for individual users, add them here to give access, leave empty to avoid checks
            "mcp_server": {
                "host": "172.24.123.123",
                "port": 5000
            }
        }
       ```

    
5. **Start the AI agents:**
   - 5.1 **Start the OpenAI-compatible API agent that uses the PGPT API directly:**
     ```bash
     python -m agents.OpenAI_Compatible_API_Agent.Python.openai_compatible_api
     ```

   - 5.2 **Start the OpenAI-compatible API agent that uses the MCP server to communicate:**
     ```bash
     python -m agents.OpenAI_Compatible_API_Agent.Python.openai_mcp_api
     ```

---

## Utilisation
- **Use libraries (like litellm, ollama, smolagents) or tools (like Msty) to use PGPT with the OpenAI API interface:**
   Use the API Key you created with generate_api_key.py when required.
   
---

## License
This project is licensed under the MIT License - see the LICENSE file for details.