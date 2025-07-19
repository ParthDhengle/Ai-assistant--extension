import requests
from .os_actions import get_contextual_os_info
from .helpers import extract_json_from_text

def generate_response(prompt):
    print("🧠 Generating with Ollama...")

    cwd, folders, files = get_contextual_os_info()
    os_context = (
        f"Current working directory is: {cwd}\n"
        f"Folders: {folders}\n"
        f"Files: {files}\n"
        "Use these paths when deciding where to create, delete, or move files."
    )

    system_prompt = (
        "You are Spark, an intent parser.\n"
        "Analyze the user's request and determine the intent: either 'assistant' or 'os'.\n"
        "If the user wants to perform an OS-level task, return a JSON like:\n"
        "{ \"type\": \"os\", \"action\": \"create_file\", \"target\": \"path/to/file.txt\", \"message\": \"Creating the file now.\" }\n\n"
        "If the user asks you to write code to a file, return JSON like:\n"
        "{ \"type\": \"code\", \"target\": \"file.py\", \"code\": \"<insert full Python code here>\", \"message\": \"Writing code to the file.\" }\n\n"


        "Supported actions:\n"
        "- create_file → e.g., 'create a file named notes.txt'\n"
        "- delete_file → e.g., 'delete the file notes.txt'\n"
        "- create_folder → e.g., 'make a folder called projects'\n"
        "- delete_folder → e.g., 'remove the folder named projects'\n"
        "- copy_file → e.g., 'copy report.txt to backup/report.txt' → return { action: 'copy_file', source: '...', destination: '...' }\n\n"
        "- move_file → use format: source::destination (e.g., 'move data.csv to archive/data.csv')\n\n"

        "If it's a general assistant question (like greetings or queries), return JSON like:\n"
        "{ \"type\": \"assistant\", \"message\": \"Short helpful reply here.\" }\n\n"

        "Always respond with **only valid JSON**, no explanations or tags.\n\n"

        +os_context
    )

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "phi3:3.8b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
    )

    try:
        content = response.json()['message']['content']
        print("🔍 Phi3 Output:", content)
        return extract_json_from_text(content)
    except Exception as e:
        return {"type": "assistant", "message": f"Failed to parse response. {e}"}
