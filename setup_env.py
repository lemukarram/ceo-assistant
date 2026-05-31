import secrets
import os

def generate_key(length=32):
    return secrets.token_urlsafe(length)

def setup_env():
    env_path = ".env"
    example_path = ".env.example"
    
    if os.path.exists(env_path):
        print(f"{env_path} already exists. Skipping.")
        return

    if not os.path.exists(example_path):
        print(f"Error: {example_path} not found.")
        return

    with open(example_path, "r") as f:
        content = f.read()

    # Generate a secure key for HERMES_API_KEY
    hermes_key = generate_key()
    content = content.replace("your_secure_random_string_here", hermes_key)
    
    # Prompt for other keys or leave as is
    print("Generating .env file with a secure HERMES_API_KEY.")
    print("Please manually update GEMINI_API_KEY and OPENAI_API_KEY in the .env file.")

    with open(env_path, "w") as f:
        f.write(content)
    
    print(f"{env_path} created successfully.")

if __name__ == "__main__":
    setup_env()
