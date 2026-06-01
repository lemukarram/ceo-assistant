# 📱 LOOPS CA: WhatsApp Webhook & WAHA Setup Guide

This guide will walk you through connecting your WhatsApp account to LOOPS CA.

---

## 🔐 1. Accessing the WAHA Dashboard
I have configured the system to expose the WAHA dashboard through our secure proxy.

*   **URL:** `http://[YOUR_SERVER_IP]:3001`
*   **Username:** `admin`
*   **Password:** `LoopsAdmin2026`
*(Note: I've added a security layer so you use the same credentials as the main dashboard).*

---

## 🚀 2. Setting up the WhatsApp Session
1.  Open the WAHA Dashboard.
2.  Click on **"Sessions"** in the sidebar.
3.  If no session exists, click **"Add Session"**.
    *   **Name:** `default` (This matches our bridge config).
4.  Once the session is "Starting," click **"Scan QR Code"**.
5.  Open WhatsApp on your phone > **Linked Devices** > **Link a Device** and scan the code.

---

## 🔗 3. Configuring the Webhook
Our system is designed to handle the webhook automatically, but here is how to verify it in the WAHA Dashboard:

1.  Go to the **"Webhooks"** tab.
2.  Ensure there is a webhook pointing to:
    *   **URL:** `http://waha-bridge:8000/webhook/whatsapp`
    *   **Events:** `message.upsert`
3.  This is already set in your `docker-compose.yml`, so it should be active as soon as the session is connected.

---

## ✅ 4. Final Verification
1.  Ensure you have added your phone number to the **`TRUSTED_NUMBERS`** environment variable in Dokploy.
2.  Send a message (e.g., "Hi LOOPS CA") from your phone to the number you linked in WAHA.
3.  **LOOPS CA** should respond back to you on WhatsApp!

---

## 🛠 Troubleshooting
*   **Not responding?** Check the logs in Dokploy for the `loops_waha_bridge` container. It will show if it's rejecting the number or if there is a connection error with the AI core.
*   **401 Error?** Ensure you have selected **Gemini 1.5 Pro** as your default model in the main LOOPS CA dashboard (port 9119).
