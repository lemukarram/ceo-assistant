import os
import logging
import base64
import re
import mimetypes
import io
import json
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
import httpx

# Clean, simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WAHA-BRIDGE] - %(levelname)s - %(message)s')
logger = logging.getLogger("WAHA-BRIDGE")

load_dotenv()

app = FastAPI(title="WhatsApp Media & Dynamic Admin Bridge")

# --- Configuration ---
# MASTER_CEO is the permanent admin number from .env
MASTER_CEO = os.getenv("MASTER_CEO", "").strip().replace("+", "")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://hermes_core:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Shared Storage Paths
DATA_DIR = "/opt/data"
MEDIA_DIR = os.path.join(DATA_DIR, "media")
TRUSTED_DB_PATH = os.path.join(DATA_DIR, "trusted_numbers.json")

os.makedirs(MEDIA_DIR, exist_ok=True)

# In-memory deduplication
processed_message_ids = set()

# In-memory conversational context (chat_id -> list of messages)
chat_history = {}

# --- Dynamic Trust Management ---
def load_trusted_numbers():
    """Loads trusted numbers from environment and JSON file."""
    trusted = {MASTER_CEO} if MASTER_CEO else set()
    
    # Load from TRUSTED_NUMBERS env var (comma-separated)
    env_trusted = os.getenv("TRUSTED_NUMBERS", "")
    if env_trusted:
        for num in env_trusted.split(","):
            clean_num = num.strip().replace("+", "")
            if clean_num:
                trusted.add(clean_num)

    if os.path.exists(TRUSTED_DB_PATH):
        try:
            with open(TRUSTED_DB_PATH, "r") as f:
                data = json.load(f)
                trusted.update(data)
        except Exception as e:
            logger.error(f"Error loading trusted DB: {e}")
    return {n for n in trusted if n} # Remove empty strings

def save_trusted_numbers(numbers):
    """Saves trusted numbers to JSON file."""
    try:
        # Don't save the MASTER_CEO to the JSON to keep it clean (it's always in .env)
        to_save = list(set(numbers) - {MASTER_CEO})
        with open(TRUSTED_DB_PATH, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        logger.error(f"Error saving trusted DB: {e}")

# Initial load
TRUSTED_LIST = load_trusted_numbers()

async def get_waha_chat_id(phone_number: str):
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-Api-Key": WAHA_API_KEY} if WAHA_API_KEY else {}
            res = await client.get(
                f"{WAHA_API_URL}/api/contacts/check-exists",
                params={"phone": phone_number, "session": "default"},
                headers=headers,
                timeout=10.0
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("numberExists") and data.get("chatId"):
                    return data.get("chatId")
    except Exception as e:
        logger.error(f"Error checking WAHA contacts: {e}")
    # Fallback
    return f"{phone_number}@c.us" if "@" not in phone_number else phone_number

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    global TRUSTED_LIST
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
        body = payload.get("body", "").strip()

        logger.info(f"INCOMING WHATSAPP MESSAGE FROM {from_number}: {body}")

        # --- ADMIN COMMAND LOGIC ---
        if from_number == MASTER_CEO and body.startswith("/"):
            logger.info(f"Admin command from CEO: {body}")
            if body.startswith("/add "):
                raw_num = body.replace("/add ", "").strip().replace("+", "")
                
                # Fetch correct ID from WAHA (handles LID or alternative formats)
                resolved_chat_id = await get_waha_chat_id(raw_num)
                clean_id = resolved_chat_id.split("@")[0]
                
                # Add both the internal ID and raw number just to be safe
                TRUSTED_LIST.add(clean_id)
                TRUSTED_LIST.add(raw_num)
                save_trusted_numbers(TRUSTED_LIST)
                
                background_tasks.add_task(send_to_whatsapp_simple, from_chat, f"✅ Added {raw_num} (ID: {clean_id}) to trusted list.")
                
                # Send greeting to the newly added number
                greeting_msg = "Hello! You have been granted access to LOOPS CA. How can I assist you today?"
                background_tasks.add_task(send_to_whatsapp_simple, resolved_chat_id, greeting_msg)
                
                return {"status": "admin_command_executed"}
            
            elif body.startswith("/remove "):
                rem_num = body.replace("/remove ", "").strip().replace("+", "")
                if rem_num == MASTER_CEO:
                    background_tasks.add_task(send_to_whatsapp_simple, from_chat, "❌ Cannot remove the Master CEO.")
                else:
                    TRUSTED_LIST.discard(rem_num)
                    save_trusted_numbers(TRUSTED_LIST)
                    background_tasks.add_task(send_to_whatsapp_simple, from_chat, f"🗑️ Removed {rem_num} from trusted list.")
                return {"status": "admin_command_executed"}
            
            elif body == "/list":
                msg = "📋 *Trusted Numbers:*\n" + "\n".join([f"- {n}" for n in sorted(TRUSTED_LIST)])
                background_tasks.add_task(send_to_whatsapp_simple, from_chat, msg)
                return {"status": "admin_command_executed"}

        # --- REGULAR MESSAGE LOGIC ---
        if from_number not in TRUSTED_LIST:
            logger.warning(f"SECURITY: Blocked untrusted number {from_number}")
            return {"status": "unauthorized"}

        has_media = payload.get("hasMedia", False)
        media_info = payload.get("media") if has_media else None
        msg_type = payload.get("type", "chat")
        is_voice = msg_type in ["ptt", "audio"]

        background_tasks.add_task(process_and_reply, from_chat, body, media_info, is_voice)
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook Error: {str(e)}")
        return {"status": "error"}

async def download_media(media_url: str):
    async with httpx.AsyncClient() as client:
        headers = {"X-Api-Key": WAHA_API_KEY} if WAHA_API_KEY else {}
        res = await client.get(media_url, headers=headers)
        return res.content if res.status_code == 200 else None

async def transcribe_audio(audio_data: bytes, mimetype: str):
    if not OPENAI_API_KEY: return "[Voice transcription disabled]"
    try:
        ext = mimetypes.guess_extension(mimetype) or ".ogg"
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
                files={'file': (f"voice{ext}", io.BytesIO(audio_data), mimetype)},
                data={'model': 'whisper-1'},
                timeout=60.0
            )
            return res.json().get("text", "") if res.status_code == 200 else "[Transcription error]"
    except Exception: return "[Voice processing error]"

async def process_and_reply(chat_id: str, user_message: str, media_info: dict = None, is_voice: bool = False):
    try:
        import time
        async with httpx.AsyncClient() as client:
            content = []
            if media_info:
                media_url = media_info.get("url").replace("localhost:3000", "waha:3000")
                mimetype = media_info.get("mimetype", "")
                media_data = await download_media(media_url)
                if media_data:
                    # 1. ALWAYS Save file to Shared Volume (Dual-Context)
                    ext = mimetypes.guess_extension(mimetype) or ".bin"
                    filename = media_info.get("filename") or f"incoming_{int(time.time())}{ext}"
                    file_path = os.path.join(MEDIA_DIR, filename)
                    with open(file_path, "wb") as f: f.write(media_data)

                    if is_voice:
                        transcription = await transcribe_audio(media_data, mimetype)
                        user_message = f"{user_message} {transcription}".strip()
                    elif mimetype.startswith("image/"):
                        # 2. Images: Send Base64 (Vision) AND Local Path (Tool capability)
                        content.append({"type": "image_url", "image_url": {"url": f"data:{mimetype};base64,{base64.b64encode(media_data).decode('utf-8')}"}})
                        user_message = f"{user_message}\n[System Note: Image also saved locally at {file_path} for script/tool processing]".strip()
                    else:
                        # 3. Standard Docs
                        user_message = f"{user_message}\n[System Note: Document saved locally at {file_path}]".strip()

            if user_message: content.append({"type": "text", "text": user_message})

            # Retrieve and update conversation history
            if chat_id not in chat_history:
                chat_history[chat_id] = []
            
            chat_history[chat_id].append({"role": "user", "content": content})
            
            # Keep history bounded (e.g., last 3 messages to avoid token bloat)
            if len(chat_history[chat_id]) > 3:
                chat_history[chat_id] = chat_history[chat_id][-3:]

            h_res = await client.post(HERMES_API_URL, headers={"Authorization": f"Bearer {HERMES_API_KEY}"}, json={"model": "hermes-agent", "messages": chat_history[chat_id], "stream": False}, timeout=150.0)
            reply_text = h_res.json().get("choices", [{}])[0].get("message", {}).get("content", "") if h_res.status_code == 200 else "⚠️ AI Error."

            logger.info(f"RAW HERMES REPLY: {reply_text}")

            # Save the assistant's reply back to history
            if h_res.status_code == 200 and reply_text:
                chat_history[chat_id].append({"role": "assistant", "content": reply_text})

            # Explicit Outbound Media Protocol Parsing
            media_to_send = []
            def extract_media_tags(match):
                media_to_send.append(match.group(1).strip())
                return "" # Remove the tag from the final message
            
            clean_reply = re.sub(r'<send_media>(.*?)</send_media>', extract_media_tags, reply_text)
            
            # Also catch markdown images/links and raw paths pointing to /opt/data/
            for path_match in re.finditer(r'(/opt/data/[a-zA-Z0-9_./-]+)', clean_reply):
                path = path_match.group(1)
                if path not in media_to_send and os.path.exists(path) and os.path.isfile(path):
                    media_to_send.append(path)
            
            # Clean up empty markdown image tags that might be left behind if we just keep the path
            clean_reply = re.sub(r'!\[.*?\]\((/opt/data/.*?)\)', '', clean_reply)
            
            clean_reply = clean_reply.strip()

            if clean_reply:
                await send_to_whatsapp_full(client, chat_id, "text", {"text": clean_reply})
            
            for path in media_to_send:
                if os.path.exists(path):
                    mime, _ = mimetypes.guess_type(path)
                    m_type = "image" if mime and mime.startswith("image/") else "document"
                    await send_to_whatsapp_full(client, chat_id, m_type, {"path": path, "filename": os.path.basename(path)})
                else:
                    logger.warning(f"Agent attempted to send missing file: {path}")

    except Exception as e: logger.error(f"Processing Crash: {e}")

async def send_to_whatsapp_simple(chat_id: str, text: str):
    async with httpx.AsyncClient() as client:
        await send_to_whatsapp_full(client, chat_id, "text", {"text": text})

async def send_to_whatsapp_full(client, chat_id: str, msg_type: str, data: dict):
    try:
        url = f"{WAHA_API_URL}/api/sendText"
        payload = {"chatId": chat_id, "session": "default"}
        if msg_type == "text": payload["text"] = data["text"]
        else:
            url = f"{WAHA_API_URL}/api/sendImage" if msg_type == "image" else f"{WAHA_API_URL}/api/sendDocument"
            mime_type = mimetypes.guess_type(data["path"])[0] or "application/octet-stream"
            filename = data.get("filename", os.path.basename(data["path"]))
            with open(data["path"], "rb") as f:
                payload["file"] = {
                    "mimetype": mime_type,
                    "filename": filename,
                    "data": base64.b64encode(f.read()).decode('utf-8')
                }
        
        headers = {"Content-Type": "application/json"}
        if WAHA_API_KEY: headers["X-Api-Key"] = WAHA_API_KEY
        res = await client.post(url, json=payload, headers=headers)
        if res.status_code >= 400:
            logger.error(f"WAHA API Error ({res.status_code}): {res.text}")
    except Exception as e: logger.error(f"WhatsApp Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
