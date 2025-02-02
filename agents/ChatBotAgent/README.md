
# PrivateGPT ChatBot Agent

## Overview
The **PrivateGPT ChatBot Agent** is a core component of the Fujitsu PrivateGPT multi-agent system. It serves as a client that communicates with a private GPT server to answer questions and provide information. The agent supports both local knowledge data and server-based responses and uses **FIPA ACL (Agent Communication Language)** to standardize communications with other agents in the system.

---

## Features
- **Multi-Agent Communication via FIPA ACL:**  
  - Processes structured messages with standard fields such as `performative`, `sender`, `receiver`, `ontology`, and `content`.
  - Returns FIPA ACL failure messages when a connection to the MCP server cannot be established.
  
- **Flask API Server:**  
  - Provides RESTful endpoints (e.g., `/ask`, `/logs`, `/status`) using Flask.
  - Serves requests with Waitress, ensuring production-readiness.
  - Implements Cross-Origin Resource Sharing (CORS) for all origins (`origins: "*"`) so that requests from any domain are allowed.
  
- **Authentication:**  
  - Endpoints (except OPTIONS and `/status`) require an API key sent via the `X-API-KEY` header.
  
- **MCP Server Connectivity:**  
  - Validates connectivity to the MCP server (as defined in `config.json`) before processing requests.
  
- **Logging:**  
  - Detailed logs are maintained for both the agent (in `agent.log`) and the Flask server (in `flask.log`).

## Prerequisites
- **Python:** 3.8 or higher
- **Dependencies:**  
  Install required packages as listed in the corresponding `requirements.txt` (e.g., Flask, waitress, flask-cors, paho-mqtt, paramiko, etc.)

---

## Setup
1. **Clone the Repository:**
   ```bash
   git clone https://github.com/pgpt-dev/MCP-Server-for-MAS-Developments.git
   cd MCP-Server-for-MAS-Developments
   ```

2. **(Optional) Create and Activate a Virtual Environment:**
   - **Windows:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
     
   - **Unix/MacOS:**
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r agents/ChatBotAgent/requirements.txt
   ```

4. **Configure the Agent:**
   Copy the example configuration file and adjust it to your environment:

   ```bash
   cp agents/ChatBotAgent/config.json.example agents/ChatBotAgent/config.json
   ```

   **Example `config.json`:**

   ```json
   {
       "email": "<YOUR EMAIL>",
       "password": "<YOUR PASSWORD>",
       "api_ip": "0.0.0.0",
       "api_port": 5001,
       "api_key": "<YOUR_API_KEY>",
       "mcp_server": {
           "host": "172.24.123.123",
           "port": 5000
       },
       "language": "en",
       "groups": ["<Your Group>"]
   }
   ```

   **Note:** All parameters, including `email` and `password`, are read exclusively from this JSON file.

## Running the Agent
To start the ChatBot Agent, ensure you're in the repository's root directory and run:

```bash
python -m agents.ChatBotAgent.Python.chatbot_agent
```
The agent will launch a Flask API server (using Waitress) on the configured `api_ip` and `api_port`, and it will start its internal processing loop in a separate thread.

---

## API Endpoints

### `/ask` (POST)
- **Purpose:**  
  Accepts a question for the ChatBot Agent. The endpoint supports both a **FIPA ACL** structured message and a legacy JSON format.
  
- **Authentication:**  
  Requires the `X-API-KEY` header with the correct API key.
  
- **FIPA ACL Request Example:**

  ```json
  {
      "performative": "request",
      "sender": "IoT_MQTT_Agent",
      "receiver": "Chatbot_Agent",
      "ontology": "fujitsu-iot-ontology",
      "content": {
          "question": "What is the system status?",
          "usePublic": false,
          "groups": ["group1"],
          "language": "en"
      }
  }
  ```

- **Legacy JSON Request Example:**

  ```json
  {
      "question": "What is the system status?",
      "usePublic": false,
      "groups": ["group1"],
      "language": "en"
  }
  ```
  
---

- **Response:**  
  Returns a JSON object containing the generated answer from the PrivateGPT server. If the MCP server connection fails, a FIPA ACL failure message is returned.

### `/logs` (GET)
- **Purpose:**  
  Retrieves the contents of the Flask log file (`flask.log`) for debugging purposes.

### `/status` (GET)
- **Purpose:**  
  Provides a simple JSON message confirming that the agent is running. This endpoint does **not** require authentication.
  
---

## Multi-Agent Communication & FIPA ACL
The ChatBot Agent uses **FIPA ACL** to structure its communications with other agents. Key points include:

- **Standardized Message Fields:**  
  Each FIPA ACL message includes:
  - `performative` (e.g., "request", "failure")
  - `sender` and `receiver` identifiers
  - `ontology` defining the domain (e.g., `fujitsu-iot-ontology`)
  - `content` containing the actual data or question
  
- **Failure Handling:**  
  If the MCP server connection fails during a request to `/ask`, the agent returns a FIPA ACL failure message to inform the sender of the issue.

This structured messaging facilitates reliable interactions in a multi-agent system.

---

## Logging & Debugging
- **Agent Logs:**  
  Key events, errors, and status messages are logged to `agent.log`.

- **Flask Logs:**  
  Flask-specific errors and request logs are maintained in `flask.log`.

These logs are essential for troubleshooting and monitoring the agent's operation.

---

## Example Conversation
```plaintext
🎉 Welcome to the PrivateGPT ChatBot Agent.
You: What is your name?
Agent: I am the PrivateGPT ChatBot Agent.
You: Provide system status.
Agent: The system is running normally.
```

---

## License
This project is licensed under the MIT License - see the LICENSE file for details.
