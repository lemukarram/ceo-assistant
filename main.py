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
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")

# In-memory cache to prevent duplicate processing of the same message ID
processed_message_ids = set()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        # 1. STRICT: Only process the primary 'message' event.
        if data.get("event") != "message":
            return {"status": "ignored_non_message_event"}

        payload = data.get("payload", {})
        
        # 2. STRICT: Never reply to messages sent BY the bot itself
        if payload.get("fromMe") is True:
            return {"status": "ignored_self_message"}

        # 3. STRICT: Deduplication to prevent 4x replies
        msg_id = payload.get("id")
        if msg_id:
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

        # 5. Extract user message
        body = payload.get("body", "")

        # Trigger the background reply logic
        logger.info(f"Valid message from {from_number}. Routing to Hermes...")
        background_tasks.add_task(process_and_reply, from_chat, body)
        
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def process_and_reply(chat_id: str, user_message: str):
    """Passes the message to Hermes and returns the reply to WhatsApp."""
    try:
        async with httpx.AsyncClient() as client:
            # --- Phase 1: Call Hermes ---
            hermes_payload = {
                "model": "hermes-agent",
                "messages": [{"role": "user", "content": user_message}],
                "stream": False
            }
            hermes_headers = {
                "Authorization": f"Bearer {HERMES_API_KEY}",
                "Content-Type": "application/json"
            }

            logger.info(f"Calling Hermes API at {HERMES_API_URL}")
            h_res = await client.post(HERMES_API_URL, json=hermes_payload, headers=hermes_headers, timeout=120.0)
            
            if h_res.status_code == 200:
                h_data = h_res.json()
                reply_text = h_data.get("choices", [{}])[0].get("message", {}).get("content", "I processed your request but had no words to reply.")
            else:
                logger.error(f"Hermes Error: {h_res.status_code} - {h_res.text}")
                reply_text = f"⚠️ Sorry, my core logic is having trouble (Error {h_res.status_code})."

            # --- Phase 2: Reply to WhatsApp ---
            waha_url = f"{WAHA_API_URL}/api/sendText"
            waha_payload = {
                "chatId": chat_id,
                "text": reply_text,
                "session": "default"
            }
            waha_headers = {"Content-Type": "application/json"}
            if WAHA_API_KEY:
                waha_headers["X-Api-Key"] = WAHA_API_KEY

            w_res = await client.post(waha_url, json=waha_payload, headers=waha_headers)
            
            if w_res.status_code == 201:
                logger.info(f"✅ Reply delivered to {chat_id}")
            else:
                logger.error(f"❌ WAHA delivery failed: {w_res.status_code} - {w_res.text}")
                
    except Exception as e:
        logger.error(f"❌ Processing Crash: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Enforcing 1 worker ensures the memory cache works perfectly to block duplicates
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)