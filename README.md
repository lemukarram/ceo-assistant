# LOOPS CA - Executive Assistant Platform

This repository contains the production deployment and configuration files for **LOOPS CA**, a high-stakes CEO Assistant platform based on the Hermes Agent.

## 📁 Project Structure

- `plans/`: Deployment configurations (Docker Compose, Caddy, Rebranding).
- `src/`: Custom tools and executive audit scripts.
- `gemini.md`: Project roadmap and implementation status.
- `Makefile`: Commands for local testing and management.

## 🚀 Production Deployment (Dokploy)

1.  **Create Project:** In Dokploy, create a new Project named `LOOPS-CA`.
2.  **Docker Compose:** Create a new **Docker Compose** application.
3.  **Source:** Point it to this GitHub repository.
4.  **Configuration:** 
    *   Set the **Compose File Path** to `plans/docker-compose.yml`.
5.  **Environment Variables:** Add the following variables in the Dokploy UI:
    *   `HERMES_API_KEY`: A strong random string.
    *   `GEMINI_API_KEY`: Your Google Gemini key.
    *   `OPENAI_API_KEY`: Your OpenAI key.
6.  **Auth Credentials:** The dashboard is protected by a secure proxy.
    *   **User:** `admin`
    *   **Password:** `LoopsAdmin2026`

## 🛡️ Admin Commands (WhatsApp)
If your number is set as `MASTER_CEO` in the environment variables, you can manage access to the assistant directly from WhatsApp:

- `/add <number>` : Grants a new number access (e.g., `/add 923124277939`).
- `/remove <number>` : Revokes access from a number.
- `/list` : Shows all currently trusted numbers.

*Note: Use international format without the '+' (e.g., 1234567890).*

## 🧠 CEO Assistant Persona
The assistant's "Soul" (System Prompt) is located at `plans/SOUL.md`. You can modify this file to change how LOOPS CA behaves or onboard new executive rules.

## 🛠 Local Development
To run LOOPS CA locally for testing:
1. `python3 setup_env.py` (Initial setup)
2. `make up` (Start the stack)

## 🔑 SSH Management
To retrieve the assistant's public key for Hostinger/Server authorization:
```bash
docker exec hermes_core cat /opt/data/hermes_key.pub
```


I've hardened the TRUSTED_NUMBERS check and added
     secure logging. Only your approved phones can trigger the assistant.

     Port 9119: For the Admin Dashboard.
       * Port 8000: For the WhatsApp Webhook (WAHA will point its webhooks
         here).
