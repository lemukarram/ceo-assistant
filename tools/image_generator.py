import json
import os
import time
import urllib.parse
import requests
from tools.registry import registry

def generate_image(prompt: str, output_name: str = None):
    try:
        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Pollinations.ai provides free image generation via a simple GET request
        # Added parameters for better quality and no watermark
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        response = requests.get(url, timeout=45)
        
        if response.status_code == 200:
            if not output_name:
                output_name = f"generated_image_{int(time.time())}.jpg"
            if not output_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                output_name += ".jpg"
                
            # Save to the shared media directory so the Evolution bridge can send it
            output_dir = "/opt/data/media"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_name)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return json.dumps({
                "success": True, 
                "message": "Image generated successfully.",
                "file_path": output_path
            })
        else:
            return json.dumps({"error": f"API returned status code: {response.status_code}"})
            
    except Exception as e:
        return json.dumps({"error": str(e)})

# Schema for Hermes Agent
IMAGE_SCHEMA = {
    "name": "generate_free_image",
    "description": "Generate an image based on a text prompt using a free AI model. Use this whenever the user asks to draw, generate, or create a picture.",
    "parameters": {
        "type": "object",
        "properties": {
             "prompt": {"type": "string", "description": "A highly detailed description of the image you want to generate."},
             "output_name": {"type": "string", "description": "Optional. A simple filename for the image, ending in .jpg (e.g., 'cat.jpg')."}
        },
        "required": ["prompt"]
    }
}

registry.register(
    name="generate_free_image",
    toolset="custom",
    schema=IMAGE_SCHEMA,
    handler=lambda args, **kw: generate_image(args.get("prompt"), args.get("output_name"))
)