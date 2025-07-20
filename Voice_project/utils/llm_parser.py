# Updated `llm_parser.py` with encoding fixes and improved error handling

import requests
import re
import json
from .os_actions import get_contextual_os_info
from .helpers import extract_json_from_text

def clean_text(text):
    """Clean text to remove problematic Unicode characters"""
    if isinstance(text, str):
        # Remove or replace problematic Unicode characters
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        # Remove surrogate characters
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

        # Optimized system prompt for better clarity and extensibility
        system_prompt = (
        "You are Spark, an intent parser.\n"
        "Your only task is to analyze the user's request and determine the intent: 'assistant', 'os', or 'code'.\n"
        "Always include a 'message' field in your JSON response describing the action or intent.\n"
        "If the intent is assistant level task, return JSON with 'type' as 'assistant', 'action' for the specific question, and 'target' for the file or folder involved.\n"
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

        # Step 1: Parse intent using Phi-3
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
            timeout=30  # Add timeout
        )
        response.raise_for_status()
        
        # Get and clean the content
        response_data = response.json()
        content = response_data.get('message', {}).get('content', '')
        content = clean_text(content)
        
        print("🔍 Phi3 Output:", content)

        # Try to parse JSON from the response
        try:
            parsed = extract_json_from_text(content)
        except Exception as json_error:
            print(f"⚠️ JSON parsing failed: {json_error}")
            # Fallback: treat as assistant response
            parsed = {
                "type": "assistant",
                "message": content or "I'm having trouble understanding that request."
            }

        if "message" not in parsed:
            parsed["message"] = f"Parsed as {parsed.get('type', 'unknown')} task."

        # Step 2: Confirm OS actions before executing
        if parsed.get("type") == "os":
            parsed["confirm"] = True  # GUI or speech handler must confirm with user before execution
            return parsed

        # Step 3: Generate code if type is 'code'
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
                    timeout=60  # Longer timeout for code generation
                )
                code_response.raise_for_status()
                
                code_content = code_response.json().get('message', {}).get('content', '')
                code_content = clean_text(code_content)
                parsed["code"] = extract_code(code_content)

                # Generate follow-up message
                try:
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
                except Exception as followup_error:
                    print(f"⚠️ Followup message failed: {followup_error}")
                    parsed["message"] = "Code generated successfully."
                    
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