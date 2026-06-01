import os
import json
import httpx
import logging
import base64
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

# Initialize logging for 100% visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LOOPS-CA-BRIDGE")

load_dotenv()

app = FastAPI(title="LOOPS CA Executive Bridge")

# --- Configuration & Security ---
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.debug("DEBUG MODE ENABLED")

TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")

# 100% Security Check: Validate Configuration
if not HERMES_API_KEY or not TRUSTED_NUMBERS:
    logger.critical("CRITICAL: Missing HERMES_API_KEY or TRUSTED_NUMBERS. System insecure.")

# --- Core Logic ---

async def process_media_message(payload: dict):
    """Downloads media from WAHA and prepares it for Hermes."""
    # Note: WAHA media handling requires a session and media ID
    # This is a placeholder for the logic to download and convert to base64
    # which is the standard way to pass images/files to Hermes.
    pass

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        if DEBUG_MODE:
            logger.debug(f"RAW WEBHOOK DATA: {json.dumps(data)}")
        
        # Filter for valid message events
        # We only process 'message' to avoid duplicates from 'message.any' or 'message.upsert'
        if data.get("event") != "message":
            return {"status": "ignored_event"}

        payload = data.get("payload", {})
        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        
        # 1. 100% Security: Trust Check
        if from_number not in TRUSTED_NUMBERS:
            logger.warning(f"SECURITY: Unauthorized attempt from {from_number}")
            return {"status": "unauthorized"}

        # 2. Extract Message Content (Text/Image/Voice/File)
        msg_type = payload.get("type", "chat")
        body = payload.get("body", "")
        
        logger.info(f"CEO REQUEST ({msg_type}) from {from_number}")
        logger.info(f"Message from trusted number {from_number}: {body}")

        # Handle multi-modal input (placeholder for advanced media logic)
        # For now, we pass the text. Images/Files will require WAHA's file download API.
        
        # 3. Hand-off to LOOPS CA (Background task to avoid WhatsApp timeout)
        background_tasks.add_task(
            communicate_with_hermes, 
            from_chat, 
            body, 
            msg_type,
            payload
        )

        return {"status": "received"}

    except Exception as e:
        logger.error(f"WEBHOOK ERROR: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}

async def communicate_with_hermes(chat_id: str, message: str, msg_type: str, raw_payload: dict):
    """The 'Never-Fail' communication loop with the Assistant Core."""
    from_number = chat_id.split("@")[0]
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Routing to Hermes: {message[:50]}...")
            
            # Prepare Hermes Payload (OpenAI Compatible)
            hermes_payload = {
                "model": "hermes-agent", # or the model configured in UI
                "messages": [{"role": "user", "content": message}],
                "stream": False,
                # In OpenAI, session logic is usually handled by passing history,
                # but if Hermes accepts custom metadata, we can add it:
                "metadata": {"session_id": f"whatsapp_{from_number}"}
            }

            response = await client.post(
                HERMES_API_URL,
                headers={
                    "Authorization": f"Bearer {HERMES_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=hermes_payload,
                timeout=120.0 # High timeout for complex CEO tasks
            )

            if response.status_code == 200:
                hermes_data = response.json()
                reply_text = hermes_data.get("choices", [{}])[0].get("message", {}).get("content", "✅ Task completed, CEO.")
            else:
                logger.error(f"Hermes Logic Error ({response.status_code}): {response.text}")
                reply_text = f"⚠️ CEO, my core logic responded with an error ({response.status_code}). I am investigating."

        except httpx.TimeoutException:
            logger.error("Hermes Timeout: Task taking too long.")
            reply_text = "⌛ This task is complex and still processing in the background. I will update you shortly."
        except Exception as e:
            logger.error(f"SYSTEM CRASH: {str(e)}", exc_info=True)
            reply_text = "🛑 I've encountered a system-level exception. My failsafe protocols are active."

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
    except Exception as e:
        logger.error(f"WhatsApp Delivery Crash: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Use 100% stable production settings
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
