import requests
import re
import json
from core.task_executor import get_contextual_os_info
from utils.helpers import extract_json_from_text
from utils.prompt_templates import SYSTEM_PROMPT

def clean_text(text):
    if isinstance(text, str):
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        text = ''.join(char for char in text if ord(char) < 0xD800 or ord(char) > 0xDFFF)
    return text

def extract_code(text):
    code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
    return code_blocks[0].strip() if code_blocks else text.strip()

def generate_response(prompt, memory_manager):
    try:
        print("🧠 Generating with Ollama...")
        
        cwd, folders, files = get_contextual_os_info()
        os_context = (
            f"Current working directory is: {cwd}\n"
            f"Folders: {folders}\n"
            f"Files: {files}\n"
            "Use these paths when deciding where to create, delete, or move files."
        )
        print("OS Context:", os_context)

        # Get memory context
        recent_memory = memory_manager.get_recent_memory(3)
        summary = memory_manager.get_summary()
        vector_hits = memory_manager.get_relevant_memory(prompt, k=2)
        print("Recent Memory:", recent_memory)
        print("Summary:", summary)  
        print("Vector Hits:", vector_hits)
        # Handle empty vector_hits
        if vector_hits:
            vector_hits_str = '\n'.join([f"You: {u}\nSpark: {b}" for u, b in vector_hits])
        else:
            vector_hits_str = "No relevant memory found."
        # Format system prompt with memory
        formatted_prompt = SYSTEM_PROMPT.format(
            summary=summary,
            recent='\n'.join([f"You: {u}\nSpark: {b}" for u, b in recent_memory]),
            vector_hits='\n'.join([f"You: {u}\nSpark: {b}" for u, b in vector_hits]),
            query=prompt,
            os_context=os_context
        )
        print("Formatted prompt:", formatted_prompt)
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "phi3:3.8b",
                "messages": [
                    {"role": "system", "content": formatted_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()
        print("Raw response content:", response.text)

# Check if response is valid before parsing
        if response.text.strip():
            try:
                response_data = response.json()
                content = response_data.get('message', {}).get('content', '')
                content = clean_text(content)
            except json.JSONDecodeError as json_err:
                print(f"⚠️ Invalid JSON response: {json_err}")
                content = "Received an invalid response from the API."
        else:
            print("⚠️ Empty response from API")
            content = "Received an empty response from the API."
        
        
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

        if parsed.get("type") == "code":
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