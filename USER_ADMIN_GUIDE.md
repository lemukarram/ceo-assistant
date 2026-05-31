# Hermes Platform Guide

This guide explains how to use and manage your Hermes AI Agent Platform.

---

## 🔑 Understanding Your Models
Even though you only have **two API keys** (Gemini and OpenAI), they unlock a wide range of "Brains" for your agent:

| Provider | Key Models Available | Best Use Case |
| :--- | :--- | :--- |
| **Gemini** | `gemini-1.5-pro` | Complex reasoning, huge documents (2M context). |
| **Gemini** | `gemini-1.5-flash` | Fast responses, simple tasks, low cost. |
| **OpenAI** | `gpt-4o` | State-of-the-art logic and tool use. |
| **OpenAI** | `gpt-4o-mini` | High-speed, high-efficiency tasks. |

**Note:** In the "Models" tab, you will see many other options (like Anthropic/Claude). These will only work if you add their respective keys. Stick to the ones listed above for now.

---

## 🛠 Admin Guide (Configuration)

### 1. Setting the Primary Model
1. Go to the **Settings** or **Models** tab in the Dashboard.
2. Select **Gemini 1.5 Pro** as your default model (it is excellent for long-term memory).
3. Ensure your `GEMINI_API_KEY` is showing as "Configured".

### 2. Managing Skills (Tools)
Hermes comes with 90+ skills. 
*   **To Enable/Disable:** Browse the **Skills** tab.
*   **Custom Tools:** Tools you create (like our CRM audit script) can be added here by pointing Hermes to the local path.

### 3. Security
*   The dashboard is currently in **Insecure Mode** for local testing. 
*   When moving to a VPS (Dokploy), we will enable the **OAuth/Auth gate** to protect your API keys.

---

## 💬 User Guide (Daily Use)

### 1. Starting a Conversation
*   Click the **Chat** icon on the sidebar.
*   You can treat Hermes like ChatGPT, but remember: it can **see your files** and **run commands**.

### 2. Working with Files
*   **Upload:** Drag and drop a PDF or Text file into the chat.
*   **Ask:** "Summarize this document" or "Search for [X] in my project files."

### 3. Using the Terminal
*   You can ask Hermes to perform technical tasks:
    *   *"Show me the status of my docker containers."*
    *   *"Run the CRM audit script in the src folder."*

---

## 🎨 Modernizing the UI
The Hermes UI is designed to be functional and "hacker-ready." While we cannot easily change the core React code without rebuilding the image, we can inject **Custom CSS** to give it a more modern look (e.g., darker themes, smoother borders, or custom fonts).

### Proposed "Modern" CSS Tweaks:
I have prepared a `modern-ui.css` file. To apply it, we can mount it to the container's assets.
