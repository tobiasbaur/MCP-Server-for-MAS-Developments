# PrivateGPT Agent

## Description
The PrivateGPT Agent is a client that communicates with a private GPT server to answer questions and provide information. The agent supports both local knowledge data and server-based responses.

## Prerequisites
- Python 3.8 or higher
- Access to the PrivateGPT server

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
    pip install -r .\agents\ChatBotAgent\requirements.txt
    ```

4. **Customise configuration file:**
    Copy the `config.json.example` file to `config.json` e.g. with  `cp .\agents\ChatBotAgent\config.json.example .\agents\ChatBotAgent\config.json`
    Make sure that the `config.json` is configured correctly and contains all necessary fields. The file should look like this:
    ```json
    {
        "server_ip": "<IP of your MCP Instance>",
        "server_port": 5000,
        "email": "<YOUR EMAIL (USER) for PGPT>",
        "password": "<YOUR PASSWORD>",
        "language": "en",
        "groups": ["<Create a Group on PGPT for the ChatBot>"]
    }
    ```

    **Note:** All parameters, including `email` and `password`, are read **exclusively from the JSON file**. No environment variables** are used.

5. **Start the AI agent, make sure you're in the MCP-Server-for-MAS-Developments - directory:**
    ```bash
    python -m agents.ChatBotAgent.Python.chatbot_agent
    ```

## Utilisation
- **Ask a question:**
   Enter your question and press Enter.

- **Exit:**
    Enter `exit` to exit the agent.


## Example
```plaintext
🎉 Welcome to the PrivateGPT Agent. Ask your question or enter ‘exit’ to exit.
You: What is your name?
Agent: I am called PrivateGPT.
You: Say something about NIS2
Agent: The NIS2 Directive aims to strengthen cybersecurity in the European Union by imposing stricter requirements on companies and organisations operating critical infrastructure.
Sources:

┌───────┬───────────────────────┐
│ Index │ Quelle                │
├───────┼───────────────────────│
│ 1     │ EU-Richtlinie NIS2    │
│ 2     │ Cybersicherheitsgesetz│
└───────┴───────────────────────┘
You: exit
👋 Goodbye.
```
 