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

app = FastAPI(title="LOOPS CA Debug Bridge")

# --- Configuration ---
TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/api/chat")
HERMES_API_KEY = os.getenv("HERMES_API_KEY")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"

@app.on_event("startup")
async def startup_event():
    logger.info("========================================")
    logger.info("   LOOPS CA BRIDGE STARTING UP")
    logger.info(f"   Trusted Numbers: {TRUSTED_NUMBERS}")
    logger.info(f"   Debug Mode: {DEBUG_MODE}")
    logger.info("========================================")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    logger.info(f"[{timestamp}] STEP 1: Webhook Received from WAHA")
    
    try:
        data = await request.json()
        logger.info(f"[{timestamp}] STEP 2: Payload Parsed: {json.dumps(data)[:200]}...")
        
        # Filter for valid message events
        if data.get("event") not in ["message.upsert", "message"]:
            logger.info(f"[{timestamp}] IGNORED: Event type {data.get('event')} is not a message.")
            return {"status": "ignored_event"}

        payload = data.get("payload", {})
        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        
        # 1. Security: Trust Check
        logger.info(f"[{timestamp}] STEP 3: Checking Authorization for {from_number}")
        if from_number not in TRUSTED_NUMBERS:
            logger.warning(f"[{timestamp}] SECURITY ALERT: Unauthorized attempt from {from_number}")
            return {"status": "unauthorized"}

        # 2. Extract Message Content
        msg_type = payload.get("type", "chat")
        body = payload.get("body", "")
        logger.info(f"[{timestamp}] STEP 4: CEO Message Identified: '{body}' (Type: {msg_type})")

        # 3. Hand-off
        if DEBUG_MODE:
            logger.info(f"[{timestamp}] DEBUG: Bypassing AI, sending instant verification reply.")
            debug_reply = f"🚀 LOOPS CA ONLINE\n\nStatus: Systems 100% Operational\nTime: {timestamp}\nYour Msg: {body}\n\nConnection Verified."
            background_tasks.add_task(send_to_whatsapp, from_chat, debug_reply)
        else:
            logger.info(f"[{timestamp}] STEP 5: Routing to Assistant Core (Hermes)...")
            background_tasks.add_task(communicate_with_hermes, from_chat, body)

        return {"status": "received"}

    except Exception as e:
        logger.error(f"[{timestamp}] CRITICAL ERROR: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}

async def communicate_with_hermes(chat_id: str, message: str):
    """Deep Integration with the AI Core."""
    from_number = chat_id.split("@")[0]
    async with httpx.AsyncClient() as client:
        try:
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
                reply_text = response.json().get("response", "✅ Done.")
            else:
                reply_text = f"⚠️ Core Error ({response.status_code})"
                
        except Exception as e:
            reply_text = f"🛑 Bridge Connection Failure: {str(e)}"

        await send_to_whatsapp(chat_id, reply_text)

async def send_to_whatsapp(chat_id: str, text: str):
    """Final step: Send back to CEO via WAHA."""
    logger.info(f"STEP 6: Sending reply back to WhatsApp chat {chat_id}")
    try:
        async with httpx.AsyncClient() as client:
            url = f"{WAHA_API_URL}/api/sendText"
            payload = {
                "chatId": chat_id,
                "text": text,
                "session": "default"
            }
            res = await client.post(url, json=payload)
            if res.status_code == 201:
                logger.info("SUCCESS: Message delivered to CEO WhatsApp.")
            else:
                logger.error(f"FAILURE: WAHA responded with {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"WAHA CONNECTION ERROR: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
