import os
import json
import httpx
import logging
import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

# 100% Visibility Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LOOPS-CA-BRIDGE] - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LOOPS-CA")

load_dotenv()

app = FastAPI(title="LOOPS CA Executive Bridge")

# --- Configuration ---
TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/api/chat")
HERMES_API_KEY = os.getenv("HERMES_API_KEY")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

@app.on_event("startup")
async def startup_event():
    logger.info("========================================")
    logger.info("   LOOPS CA BRIDGE STARTING UP")
    logger.info(f"   Trusted Numbers: {TRUSTED_NUMBERS}")
    logger.info(f"   Debug Mode: {DEBUG_MODE}")
    logger.info(f"   WAHA API Key Set: {'Yes' if WAHA_API_KEY else 'No'}")
    logger.info("========================================")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        data = await request.json()
        
        # Filter for valid message events
        event_type = data.get("event")
        if event_type not in ["message", "message.upsert", "message.any"]:
            return {"status": "ignored_event"}

        payload = data.get("payload", {})
        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        
        # 1. Security: Trust Check
        logger.info(f"[{timestamp}] Checking Trust: Sender={from_number} (Full: {from_chat})")
        
        if from_number not in TRUSTED_NUMBERS:
            logger.warning(f"[{timestamp}] SECURITY ALERT: Unauthorized attempt from {from_number}. Trusted: {TRUSTED_NUMBERS}")
            return {"status": "unauthorized"}

        # 2. Extract Message Content
        msg_type = payload.get("type", "chat")
        body = payload.get("body", "")
        
        logger.info(f"[{timestamp}] CEO REQUEST ({msg_type}) from {from_number}: {body[:50]}...")

        # 3. Hand-off to Hermes
        background_tasks.add_task(
            communicate_with_hermes, 
            from_chat, 
            body, 
            from_number
        )

        return {"status": "received"}

    except Exception as e:
        logger.error(f"[{timestamp}] WEBHOOK ERROR: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}

async def communicate_with_hermes(chat_id: str, message: str, from_number: str):
    """The 'Never-Fail' communication loop with the Assistant Core."""
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Routing to Hermes: {message[:50]}...")
            
            response = await client.post(
                HERMES_API_URL,
                headers={"X-API-Key": HERMES_API_KEY},
                json={
                    "message": message,
                    "session_id": f"whatsapp_{from_number}",
                    "stream": False
                },
                timeout=120.0
            )

            if response.status_code == 200:
                hermes_data = response.json()
                reply_text = hermes_data.get("response", "✅ Task completed, CEO.")
            else:
                logger.error(f"Hermes Error ({response.status_code}): {response.text}")
                reply_text = f"⚠️ CEO, my core logic responded with an error ({response.status_code})."

        except Exception as e:
            logger.error(f"SYSTEM CRASH: {str(e)}", exc_info=True)
            reply_text = "🛑 I've encountered a system-level exception."

        # Final Delivery back to WhatsApp
        await send_to_whatsapp(chat_id, reply_text)

async def send_to_whatsapp(chat_id: str, text: str):
    """Reliable delivery back to the CEO."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{WAHA_API_URL}/api/sendText"
            payload = {
                "chatId": chat_id,
                "text": text,
                "session": "default"
            }
            headers = {}
            if WAHA_API_KEY:
                headers["X-Api-Key"] = WAHA_API_KEY

            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 201:
                logger.error(f"WAHA Delivery Failed ({res.status_code}): {res.text}")
            else:
                logger.info(f"Message delivered to {chat_id}")
    except Exception as e:
        logger.error(f"WhatsApp Delivery Crash: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
