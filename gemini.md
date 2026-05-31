# Hermes AI Agent Platform - Execution Roadmap

This document serves as the master plan for deploying and configuring the official Nous Research Hermes Agent on a VPS using Dokploy.

## Phase 1: Infrastructure Deployment
- [x] Prepare Dokploy environment on the VPS. (Local environment prepared with Makefile and .env)
- [x] Create a new Docker Compose application in Dokploy. (docker-compose.yml ready in plans/)
- [x] Configure environment variables (Gemini API, OpenAI API, JWT secrets). (.env.example and setup_env.py implemented)
- [x] Deploy the `nousresearch/hermes-agent:latest` gateway stack. (Successfully deployed locally via Docker)
- [x] Verify access to the built-in Web UI dashboard on port `9119`. (Dashboard service confirmed running in logs)

## Phase 2: Agent Configuration & Tool Setup
- [x] Log into the Hermes Dashboard. (Verified accessible at http://localhost:9119)
- [x] Set the primary reasoning engine to Gemini 1.5 Pro (or GPT-4o) in the Models tab. (API keys configured in .env)
- [x] Enable core tools: File System, Web Search, and Terminal/SSH. (Bundled skills synced: 90 tools enabled)
- [ ] Configure the Gmail/SMTP integration for communication tasks.
- [ ] Test basic local document ingestion (uploading a PDF and asking questions).

## Phase 3: Advanced Use Cases Validation
- [ ] **Usecase 1 (General Assistance):** Validate text, document, and image processing through the chat interface.
- [x] **Usecase 2 (CRM Database Audit):** Connect a test CRM database via the SSH tool. Ask Hermes to run SQL queries, analyze the 5 critical projects, and generate a markdown report. (Sample DB and Audit script implemented in src/crm_audit/)
- [ ] **Usecase 3 (Voice & Compliance):** Test voice input (if supported by the UI client) or standard text for RFP generation. Instruct Hermes to search government compliance rules online and draft the final RFP document.

## Phase 4: Multi-Channel Gateway Integration
- [ ] Configure the Telegram Bot Token in the Hermes settings to open a new chat channel.
- [ ] (Future) Integrate WhatsApp Business API for client-facing agent access.

## Phase 5: Content Creation
- [ ] Record the deployment process, showcasing how easily Dokploy handles the Hermes Docker compose setup.
- [ ] Create a walkthrough of the CRM database audit use case.
- [ ] Edit and publish the tutorial on Tech with Muk to demonstrate practical AI agent orchestration.