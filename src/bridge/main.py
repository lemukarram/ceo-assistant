import os
import logging
import base64
import re
import mimetypes
import io
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
import httpx

# Clean, simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WAHA-BRIDGE] - %(levelname)s - %(message)s')
logger = logging.getLogger("WAHA-BRIDGE")

load_dotenv()

app = FastAPI(title="WhatsApp Media & Voice Vision Bridge")

# --- Configuration ---
TRUSTED_NUMBERS = os.getenv("TRUSTED_NUMBERS", "").split(",")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# In-memory cache to prevent duplicate processing
processed_message_ids = set()

# Ensure media directory exists for document sharing
MEDIA_DIR = "/opt/data/media"
os.makedirs(MEDIA_DIR, exist_ok=True)

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        
        if data.get("event") != "message":
            return {"status": "ignored_non_message_event"}

        payload = data.get("payload", {})
        
        if payload.get("fromMe") is True:
            return {"status": "ignored_self_message"}

        msg_id = payload.get("id")
        if msg_id:
            if len(processed_message_ids) > 1000:
                processed_message_ids.clear()
            if msg_id in processed_message_ids:
                return {"status": "ignored_duplicate"}
            processed_message_ids.add(msg_id)

        from_chat = payload.get("from", "")
        from_number = from_chat.split("@")[0]
        
        if from_number not in TRUSTED_NUMBERS:
            logger.warning(f"SECURITY ALERT: Blocked untrusted number {from_number}")
            return {"status": "unauthorized"}

        # Extract message content and media
        body = payload.get("body", "")
        has_media = payload.get("hasMedia", False)
        media_info = payload.get("media") if has_media else None
        
        # Detect if it's a voice message (WAHA often marks these as 'ptt' or via mimetype)
        msg_type = payload.get("type", "chat")
        is_voice = msg_type in ["ptt", "audio"]

        logger.info(f"Message from {from_number} (Media: {has_media}, Voice: {is_voice}). Routing...")
        background_tasks.add_task(process_and_reply, from_chat, body, media_info, is_voice)
        
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def download_media(media_url: str):
    """Downloads media from WAHA and returns the binary content."""
    async with httpx.AsyncClient() as client:
        headers = {}
        if WAHA_API_KEY:
            headers["X-Api-Key"] = WAHA_API_KEY
        
        res = await client.get(media_url, headers=headers)
        if res.status_code == 200:
            return res.content
        else:
            logger.error(f"Failed to download media: {res.status_code}")
            return None

async def transcribe_audio(audio_data: bytes, mimetype: str):
    """Transcribes audio using OpenAI Whisper."""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Cannot transcribe voice.")
        return "[CEO sent a voice message, but transcription is disabled.]"
    
    try:
        # Determine extension from mimetype
        ext = mimetypes.guess_extension(mimetype) or ".ogg"
        filename = f"voice{ext}"
        
        async with httpx.AsyncClient() as client:
            files = {'file': (filename, io.BytesIO(audio_data), mimetype)}
            data = {'model': 'whisper-1'}
            headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}
            
            res = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=60.0
            )
            
            if res.status_code == 200:
                return res.json().get("text", "")
            else:
                logger.error(f"Whisper Error: {res.status_code} - {res.text}")
                return "[Error transcribing voice message]"
    except Exception as e:
        logger.error(f"Transcription Crash: {str(e)}")
        return "[Error during voice processing]"

async def process_and_reply(chat_id: str, user_message: str, media_info: dict = None, is_voice: bool = False):
    """Handles multi-modal input and routes to Hermes."""
    try:
        async with httpx.AsyncClient() as client:
            content = []
            
            # --- Phase 1: Handle Media (Images, Docs, Voice) ---
            if media_info:
                media_url = media_info.get("url").replace("localhost:3000", "waha:3000")
                mimetype = media_info.get("mimetype", "")
                media_data = await download_media(media_url)
                
                if media_data:
                    if is_voice:
                        logger.info("Processing voice message...")
                        transcription = await transcribe_audio(media_data, mimetype)
                        user_message = f"{user_message} {transcription}".strip()
                    elif mimetype.startswith("image/"):
                        base64_image = base64.b64encode(media_data).decode('utf-8')
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mimetype};base64,{base64_image}"}
                        })
                    else:
                        # Document path
                        filename = media_info.get("filename") or f"incoming_{int(client._transport._pool.time())}"
                        file_path = os.path.join(MEDIA_DIR, filename)
                        with open(file_path, "wb") as f:
                            f.write(media_data)
                        user_message = f"{user_message}\n[CEO has uploaded a document: {file_path}. Use your 'read_file' tool to analyze it.]".strip()

            # Add final text content
            if user_message:
                content.append({"type": "text", "text": user_message})

            # --- Phase 2: Call Hermes AI ---
            hermes_payload = {
                "model": "hermes-agent",
                "messages": [{"role": "user", "content": content}],
                "stream": False
            }
            hermes_headers = {
                "Authorization": f"Bearer {HERMES_API_KEY}",
                "Content-Type": "application/json"
            }

            logger.info("Calling Hermes AI...")
            h_res = await client.post(HERMES_API_URL, json=hermes_payload, headers=hermes_headers, timeout=150.0)
            
            if h_res.status_code == 200:
                h_data = h_res.json()
                reply_text = h_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logger.error(f"Hermes Error: {h_res.status_code}")
                reply_text = f"⚠️ Core logic trouble (Error {h_res.status_code})."

            # --- Phase 3: Send back to WhatsApp ---
            file_paths = re.findall(r'(/opt/data/[^\s,]+\.[a-zA-Z0-9]+)', reply_text)
            await send_to_whatsapp(client, chat_id, "text", {"text": reply_text})
            
            for path in file_paths:
                if os.path.exists(path):
                    mime, _ = mimetypes.guess_type(path)
                    msg_type = "image" if mime and mime.startswith("image/") else "document"
                    await send_to_whatsapp(client, chat_id, msg_type, {"path": path, "filename": os.path.basename(path)})

    except Exception as e:
        logger.error(f"Processing Crash: {str(e)}", exc_info=True)

async def send_to_whatsapp(client, chat_id: str, msg_type: str, data: dict):
    """Delivers text or media to WhatsApp via WAHA."""
    try:
        url = f"{WAHA_API_URL}/api/sendText"
        payload = {"chatId": chat_id, "session": "default"}
        
        if msg_type == "text":
            payload["text"] = data["text"]
        elif msg_type == "image":
            url = f"{WAHA_API_URL}/api/sendImage"
            with open(data["path"], "rb") as f:
                payload["file"] = f"data:{mimetypes.guess_type(data['path'])[0]};base64," + base64.b64encode(f.read()).decode('utf-8')
        elif msg_type == "document":
            url = f"{WAHA_API_URL}/api/sendDocument"
            with open(data["path"], "rb") as f:
                payload["file"] = f"data:{mimetypes.guess_type(data['path'])[0]};base64," + base64.b64encode(f.read()).decode('utf-8')
                payload["filename"] = data.get("filename", "document")

        headers = {"Content-Type": "application/json"}
        if WAHA_API_KEY:
            headers["X-Api-Key"] = WAHA_API_KEY

        res = await client.post(url, json=payload, headers=headers)
        if res.status_code not in [200, 201]:
            logger.error(f"WAHA {msg_type} delivery failed: {res.status_code}")
            
    except Exception as e:
        logger.error(f"WhatsApp Delivery Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
