import requests
import re
from .os_actions import get_contextual_os_info
from .helpers import extract_json_from_text

def extract_code(text):
    """Extract code from CodeLlama response, removing markdown or extra text."""
    code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
    return code_blocks[0].strip() if code_blocks else text.strip()

def generate_response(prompt):
    print("🧠 Generating with Ollama...")

    cwd, folders, files = get_contextual_os_info()
    os_context = (
        f"Current working directory is: {cwd}\n"
        f"Folders: {folders}\n"
        f"Files: {files}\n"
        "Use these paths when deciding where to create, delete, or move files."
    )

    # System prompt for Phi-3: strictly parse intent, always include "message"
    system_prompt = (
        "You are Spark, an intent parser.\n"
        "Your only task is to analyze the user's request and determine the intent: 'assistant', 'os', or 'code'.\n"
        "Always include a 'message' field in your JSON response describing the action or intent.\n"
        "If the intent is an OS-level task, return JSON like:\n"
        "{ \"type\": \"os\", \"action\": \"create_file\", \"target\": \"path/to/file.txt\", \"message\": \"Creating the file now.\" }\n\n"
        "If the user asks to write code to a file, return JSON like:\n"
        "{ \"type\": \"code\", \"target\": \"file.py\", \"message\": \"Code generation requested for file.py\" }\n\n"
        "Do NOT generate code or describe code functionality. Only identify the intent and target file name.\n"
        "Supported OS actions:\n"
        "- create_file → e.g., 'create a file named notes.txt'\n"
        "- delete_file → e.g., 'delete the file notes.txt'\n"
        "- create_folder → e.g., 'make a folder called projects'\n"
        "- delete_folder → e.g., 'remove the folder named projects'\n"
        "- copy_file → e.g., 'copy report.txt to backup/report.txt' → return { \"action\": \"copy_file\", \"source\": \"...\", \"destination\": \"...\" }\n"
        "- move_file → e.g., 'move data.csv to archive/data.csv' → return { \"action\": \"move_file\", \"source\": \"...\", \"destination\": \"...\" }\n\n"
        "If it’s a general assistant question, return JSON like:\n"
        "{ \"type\": \"assistant\", \"message\": \"Short helpful reply here.\" }\n\n"
        "Respond with valid JSON only, no explanations or extra text.\n\n"
        + os_context
    )

    # Step 1: Use Phi-3 to parse intent
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "codellama:13b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        content = response.json()['message']['content']
        print("🔍 Phi3 Output:", content)
        parsed = extract_json_from_text(content)

        # Ensure "message" field is present
        if "message" not in parsed:
            parsed["message"] = f"Intent parsed successfully for {parsed.get('type', 'unknown')} task."

        # Step 2: If intent is "code", use CodeLlama to generate the code
        if parsed.get("type") == "code":
            print("📝 Generating code with CodeLlama...")
            try:
                code_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "codellama:13b",
                        "messages": [
                            {"role": "system", "content": "Generate only the Python code for the user's request. Do not include any explanations, comments, or additional text. Output only the code."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    }
                )
                code_response.raise_for_status()
                code_content = code_response.json()['message']['content']
                parsed["code"] = extract_code(code_content)
                parsed["message"] = f"Writing code to {parsed['target']}."
            except Exception as code_e:
                parsed["message"] = f"Failed to generate code with CodeLlama: {str(code_e)}"
                parsed["code"] = ""  # Ensure code field is present even on failure

        return parsed
    except Exception as e:
        return {"type": "assistant", "message": f"Failed to parse response: {str(e)}"}