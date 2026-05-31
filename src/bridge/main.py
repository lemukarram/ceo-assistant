import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LOOPS CA WhatsApp Bridge")

# Configuration
TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/api/chat")
HERMES_API_KEY = os.getenv("HERMES_API_KEY")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    
    # WAHA message format
    # https://waha.devlike.pro/docs/how-to/receive-messages/
    if data.get("event") != "message.upsert":
        return {"status": "ignored_event"}

    payload = data.get("payload", {})
    from_number = payload.get("from", "").split("@")[0]
    message_body = payload.get("body", "")
    
    # 1. Security Check
    if from_number not in TRUSTED_NUMBERS:
        print(f"Unauthorized access attempt from: {from_number}")
        return {"status": "unauthorized"}

    print(f"Received message from CEO ({from_number}): {message_body}")

    # 2. Forward to Hermes (LOOPS CA)
    async with httpx.AsyncClient() as client:
        try:
            # We use the Hermes API Gateway
            # We might need to handle session mapping here
            response = await client.post(
                HERMES_API_URL,
                headers={"X-API-Key": HERMES_API_KEY},
                json={
                    "message": message_body,
                    "session_id": f"whatsapp_{from_number}",
                    "stream": False
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                print(f"Hermes Error: {response.text}")
                reply_text = "⚠️ My apologies, CEO. I encountered an error connecting to my core logic."
            else:
                hermes_data = response.json()
                reply_text = hermes_data.get("response", "No response from assistant.")

        except Exception as e:
            print(f"Bridge Error: {str(e)}")
            reply_text = "⚠️ System Failure: Unable to reach the assistant core."

    # 3. Send Reply back via WAHA
    await send_whatsapp_message(payload.get("from"), reply_text)
    
    return {"status": "success"}

async def send_whatsapp_message(chat_id: str, text: str):
    async with httpx.AsyncClient() as client:
        url = f"{WAHA_API_URL}/api/sendText"
        payload = {
            "chatId": chat_id,
            "text": text,
            "session": "default"
        }
        await client.post(url, json=payload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
