# Hermes System Architecture & Data Flow

This outlines the architecture using the official Hermes ecosystem, eliminating the need for a custom-built backend.

## 1. Core Engine
- **Image:** `nousresearch/hermes-agent:latest`
- **Execution Mode:** `gateway run`. This keeps the API, scheduled cron jobs, and messaging channels (like Telegram) active 24/7.
- **LLM Routing:** Hermes natively routes requests to Gemini or OpenAI based on the configuration set in the UI, managing token limits and context windows automatically.

## 2. Storage & Memory (Local Volume)
Instead of an external PostgreSQL/Redis setup, Hermes uses a self-contained memory architecture optimized for single-tenant or managed multi-tenant setups.
- **Path:** `/opt/data` (Mounted to a Dokploy local volume).
- **Function:** Stores vector embeddings of uploaded documents (using SQLite FTS5 or Chroma internally), user profiles, tool connection strings, and long-term conversation memories.

## 3. Tool Execution Sandbox
Hermes comes with a massive library of pre-built tools.
- **Execution:** When Hermes decides a tool is needed (e.g., querying a database), it formats a JSON payload matching the tool's schema.
- **Security:** Tools like SSH or executing local Python scripts run within the container's boundaries. It is highly recommended to provide Hermes with *read-only* database credentials unless writing data is strictly required.

## 4. UI Layer
- The system exposes an administrative and chat dashboard natively on port `9119`.
- The core API runs on port `8642`, allowing local development tools or custom frontends to interact with the agent securely using the `API_SERVER_KEY`.