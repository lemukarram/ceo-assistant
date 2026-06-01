import os
import logging
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
import httpx

# Clean, simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WAHA-BRIDGE] - %(levelname)s - %(message)s')
logger = logging.getLogger("WAHA-BRIDGE")

load_dotenv()

app = FastAPI(title="WhatsApp Only Bridge")

TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")

# In-memory cache to prevent duplicate processing of the same message ID
processed_message_ids = set()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        # 1. STRICT: Only process the primary 'message' event.
        # Ignore 'message.any', 'message.ack', 'message.upsert', etc.
        if data.get("event") != "message":
            return {"status": "ignored_non_message_event"}

        payload = data.get("payload", {})
        
        # 2. STRICT: Never reply to messages sent BY the bot itself
        if payload.get("fromMe") is True:
            return {"status": "ignored_self_message"}

        # 3. STRICT: Deduplication to prevent 4x replies
        msg_id = payload.get("id")
        if msg_id:
            # Clear cache occasionally to prevent memory leak
            if len(processed_message_ids) > 1000:
                processed_message_ids.clear()
                
            if msg_id in processed_message_ids:
                return {"status": "ignored_duplicate"}
            processed_message_ids.add(msg_id)

        # 4. STRICT: Trusted numbers only
        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        
        if from_number not in TRUSTED_NUMBERS:
            logger.warning(f"SECURITY ALERT: Blocked untrusted number {from_number}")
            return {"status": "unauthorized"}

        # Passed all checks! Trigger the background reply.
        logger.info(f"Valid message received from {from_number}. Sending assistant reply...")
        background_tasks.add_task(send_assistant_reply, from_chat)
        
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def send_assistant_reply(chat_id: str):
    """Sends the requested hardcoded reply directly to WhatsApp."""
    try:
        async with httpx.AsyncClient() as client:
            url = f"{WAHA_API_URL}/api/sendText"
            payload = {
                "chatId": chat_id,
                "text": "Hi I am your assistant.",
                "session": "default"
            }
            headers = {"Content-Type": "application/json"}
            if WAHA_API_KEY:
                headers["X-Api-Key"] = WAHA_API_KEY

            res = await client.post(url, json=payload, headers=headers)
            
            if res.status_code == 201:
                logger.info(f"✅ Reply successfully delivered to {chat_id}")
            else:
                logger.error(f"❌ Failed to deliver reply: {res.status_code} - {res.text}")
                
    except Exception as e:
        logger.error(f"❌ Delivery Crash: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Enforcing 1 worker ensures the memory cache works perfectly to block duplicates
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)