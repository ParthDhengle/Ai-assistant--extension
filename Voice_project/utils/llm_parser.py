# Updated `llm_parser.py` with encoding fixes and improved error handling

import requests
import re
import json
from .os_actions import get_contextual_os_info
from .helpers import extract_json_from_text

def clean_text(text):
    """Clean text to remove problematic Unicode characters"""
    if isinstance(text, str):
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        text = ''.join(char for char in text if ord(char) < 0xD800 or ord(char) > 0xDFFF)
    return text

def extract_code(text):
    code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
    return code_blocks[0].strip() if code_blocks else text.strip()

def generate_response(prompt):
    try:
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
            "Your only task is to analyze the user's request and determine the intent: 'assistant', 'os', or 'code'.\n"
            "Always include a 'message' field in your JSON response describing the action or intent.\n"
            "If the intent is an assistant-level task, return JSON with 'type' as 'assistant' and 'message'.\n"
            "If the intent is an OS-level task, return JSON with 'type' as 'os', 'action', and necessary fields.\n"
            "If the user asks to write code to a file, return JSON with 'type' as 'code', 'target', and 'message'.\n"
            "Do NOT generate code or describe code functionality unless it's a 'code' task.\n"
            "Supported OS actions:\n"
            "- create_file → e.g., 'create a file named notes.txt' → { \"action\": \"create_file\", \"target\": \"notes.txt\" }\n"
            "- delete_file → e.g., 'delete the file notes.txt' → { \"action\": \"delete_file\", \"target\": \"notes.txt\" }\n"
            "- create_folder → e.g., 'make a folder called projects' → { \"action\": \"create_folder\", \"target\": \"projects\" }\n"
            "- delete_folder → e.g., 'remove the folder named projects' → { \"action\": \"delete_folder\", \"target\": \"projects\" }\n"
            "- copy_file → e.g., 'copy report.txt to backup/report.txt' → { \"action\": \"copy_file\", \"source\": \"report.txt\", \"destination\": \"backup/report.txt\" }\n"
            "- move_file → e.g., 'move data.csv to archive/data.csv' → { \"action\": \"move_file\", \"source\": \"data.csv\", \"destination\": \"archive/data.csv\" }\n"
            "- open_application → e.g., 'open chrome' → { \"action\": \"open_application\", \"app_name\": \"chrome\" }\n"
            "- open_website → e.g., 'open youtube.com' → { \"action\": \"open_website\", \"url\": \"youtube.com\" }\n"
            "- open_file → e.g., 'open mydocument.docx' → { \"action\": \"open_file\", \"file_path\": \"mydocument.docx\" }\n"
            "- system_command → e.g., 'shutdown the computer' → { \"action\": \"system_command\", \"command\": \"shutdown\" }\n"
            "- play_media → e.g., 'play chihiro song on youtube' → { \"action\": \"play_media\", \"platform\": \"youtube\", \"query\": \"chihiro song\" }\n"
            "- play_local_media → e.g., 'play chihiro.mp3' → { \"action\": \"play_local_media\", \"file_path\": \"chihiro.mp3\" }\n\n"
            "For each action, include the necessary fields as shown above.\n"
            "Examples:\n"
            "- 'Open Chrome' → { \"type\": \"os\", \"action\": \"open_application\", \"app_name\": \"chrome\", \"message\": \"Opening Chrome\" }\n"
            "- 'Play Hello by Adele on YouTube' → { \"type\": \"os\", \"action\": \"play_media\", \"platform\": \"youtube\", \"query\": \"Hello by Adele\", \"message\": \"Playing Hello by Adele on YouTube\" }\n"
            "- 'Shutdown the computer' → { \"type\": \"os\", \"action\": \"system_command\", \"command\": \"shutdown\", \"message\": \"Shutting down the computer\" }\n"
            "Respond with valid JSON only, no explanations or extra text.\n\n"
            + os_context
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
            },
            timeout=30
        )
        response.raise_for_status()
        
        response_data = response.json()
        content = response_data.get('message', {}).get('content', '')
        content = clean_text(content)
        
        print("🔍 Phi3 Output:", content)

        try:
            parsed = extract_json_from_text(content)
        except Exception as json_error:
            print(f"⚠️ JSON parsing failed: {json_error}")
            parsed = {
                "type": "assistant",
                "message": content or "I'm having trouble understanding that request."
            }

        if "message" not in parsed:
            parsed["message"] = f"Parsed as {parsed.get('type', 'unknown')} task."

        if parsed.get("type") == "os":
            parsed["confirm"] = True
            return parsed

        elif parsed.get("type") == "code":
            print("📝 Generating code with CodeLlama...")
            try:
                code_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "mistral:7b",
                        "messages": [
                            {"role": "system", "content": "Generate only Python code, no explanation."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    },
                    timeout=60
                )
                code_response.raise_for_status()
                
                code_content = code_response.json().get('message', {}).get('content', '')
                code_content = clean_text(code_content)
                parsed["code"] = extract_code(code_content)

                followup_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "phi3:3.8b",
                        "messages": [
                            {"role": "system", "content": "You are Spark. Summarize what you just did in one sentence."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    },
                    timeout=30
                )
                followup_response.raise_for_status()
                followup_content = followup_response.json().get('message', {}).get('content', '')
                parsed["message"] = clean_text(followup_content)
            except Exception as code_e:
                print(f"❌ Code generation failed: {code_e}")
                parsed["message"] = f"Failed to generate code: {str(code_e)}"
                parsed["code"] = ""

        return parsed

    except requests.exceptions.ConnectionError:
        return {
            "type": "assistant", 
            "message": "Cannot connect to Ollama. Please make sure Ollama is running on localhost:11434."
        }
    except requests.exceptions.Timeout:
        return {
            "type": "assistant", 
            "message": "Request timed out. The model might be taking too long to respond."
        }
    except requests.exceptions.RequestException as req_error:
        return {
            "type": "assistant", 
            "message": f"Network error: {str(req_error)}"
        }
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {
            "type": "assistant", 
            "message": f"I encountered an error: {str(e)}"
        }