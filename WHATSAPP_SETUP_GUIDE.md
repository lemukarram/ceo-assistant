# 📱 LOOPS CA: WhatsApp Webhook & Evolution API Setup Guide

This guide will walk you through connecting your WhatsApp account to LOOPS CA via the new Evolution API Manager.

---

## 🔐 1. Accessing the Evolution Manager Dashboard
I have configured the system to expose the Evolution API Manager through our secure proxy.

*   **URL:** `http://[YOUR_SERVER_IP]:3005`
*   **Username:** `admin`
*   **Password:** `LoopsAdmin2026`
*(Note: I've added a security layer so you use the same credentials as the main dashboard).*

---

## 🚀 2. Setting up the WhatsApp Session
1.  Open the Evolution Manager Dashboard.
2.  Navigate to **Instances** in the sidebar.
3.  Click on **Add Instance**.
    *   **Instance Name:** `loops` (This must match the EVOLUTION_INSTANCE_NAME in the environment variables).
    *   **Token:** (Optional, or matching your API key settings).
4.  Once the instance is created, click to view its QR Code.
5.  Open WhatsApp on your phone > **Linked Devices** > **Link a Device** and scan the code.

---

## 🔗 3. Configuring the Webhook
Our Docker Compose configuration automatically injects the global webhook (`WEBHOOK_GLOBAL_URL=http://evolution-bridge:8000/webhook/whatsapp`), so you typically don't need to do this manually. 

However, to verify it in the Evolution Manager:
1.  Go to your Instance settings or Global Webhook settings.
2.  Ensure the Webhook URL is pointing to your bridge.
3.  Ensure the enabled event is `MESSAGES_UPSERT` and that **Base64** is enabled (this is required so the AI can receive media/images directly).

---

## ✅ 4. Final Verification
1.  Ensure you have added your phone number to the **`TRUSTED_NUMBERS`** or **`MASTER_CEO`** environment variables.
2.  Send a message (e.g., "Hi LOOPS CA") from your phone to the number you linked in Evolution API.
3.  **LOOPS CA** should respond back to you on WhatsApp!

---

## 🛠 Troubleshooting
*   **Not responding?** Check the logs in Dokploy for the `loops_evolution_bridge` container. It will show if it's rejecting the number or if there is a connection error with the AI core.
*   **401 Error?** Ensure your `EVOLUTION_API_KEY` is matching across your `docker-compose.yml` environment blocks.