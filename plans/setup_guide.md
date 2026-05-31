# Deployment Guide: Dokploy VPS

Follow these steps to get the Hermes Agent running on your infrastructure.

## Step 1: Dokploy Application Setup
1. Log into your Dokploy panel.
2. Navigate to your project and create a new **Docker Compose** application.
3. Paste the contents of `plans/dokploy-compose.yml` into the configuration editor.

## Step 2: Environment Variables
Before deploying, switch to the Environment section in Dokploy and add the required keys:

```env
HERMES_API_KEY=your_secure_random_string_here
GEMINI_API_KEY=your_google_gemini_key
OPENAI_API_KEY=your_openai_key
# TELEGRAM_BOT_TOKEN=your_telegram_token (Uncomment if ready)