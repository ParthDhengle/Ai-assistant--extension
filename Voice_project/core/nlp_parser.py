import requests
import re
import json
from core.task_executor import get_contextual_os_info
from utils.prompt_templates import SYSTEM_PROMPT

def clean_text(text):
    """Clean text to remove problematic unicode characters"""
    if isinstance(text, str):
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        text = ''.join(char for char in text if ord(char) < 0xD800 or ord(char) > 0xDFFF)
    return text

def extract_code(text):
    """Extract code from markdown code blocks"""
    code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
    return code_blocks[0].strip() if code_blocks else text.strip()

def extract_json_from_text(text):
    """
    Improved JSON extraction that handles various formats
    """
    if not text:
        return None
    
    # Clean the text first
    text = clean_text(text).strip()
    
    # Try to find JSON within the text
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested JSON
        r'\{.*?\}',  # Basic JSON pattern
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                # Clean up the match
                match = match.strip()
                # Try to parse as JSON
                parsed = json.loads(match)
                if isinstance(parsed, dict) and ('type' in parsed or 'message' in parsed):
                    return parsed
            except json.JSONDecodeError:
                continue
    
    # If no valid JSON found, try to extract structured information
    # Look for action patterns in the text
    if 'open' in text.lower() and 'youtube' in text.lower():
        if 'search' in text.lower() or 'playlist' in text.lower():
            # Extract search query
            query_match = re.search(r'(?:search for|find|look for)\s+([^.]+)', text.lower())
            query = query_match.group(1).strip() if query_match else "music"
            return {
                "type": "os",
                "action": "search_platform",
                "platform": "youtube",
                "query": query,
                "message": f"Searching for {query} on YouTube"
            }
        else:
            return {
                "type": "os",
                "action": "open_website",
                "url": "youtube.com",
                "message": "Opening YouTube"
            }
    
    # If still no valid structure, return as assistant response
    return {
        "type": "assistant",
        "message": text if text else "I'm not sure how to help with that."
    }

def validate_parsed_response(parsed):
    """Validate and fix common issues in parsed responses"""
    if not isinstance(parsed, dict):
        return {
            "type": "assistant",
            "message": "I encountered an error processing your request."
        }
    
    # Ensure required fields exist
    if 'type' not in parsed:
        parsed['type'] = 'assistant'
    
    if 'message' not in parsed:
        if parsed['type'] == 'os':
            action = parsed.get('action', 'unknown')
            parsed['message'] = f"Executing {action} action"
        else:
            parsed['message'] = "Processing your request"
    
    # Validate OS actions
    if parsed['type'] == 'os':
        if 'action' not in parsed:
            return {
                "type": "assistant",
                "message": "I'm not sure what action to perform."
            }
        
        action = parsed['action']
        
        # Fix common action format issues
        if action == 'open_website' and 'url' not in parsed:
            parsed['url'] = 'google.com'
        elif action == 'play_youtube_video' and 'query' not in parsed:
            parsed['query'] = 'music'
        elif action in ['create_file', 'delete_file', 'open_file'] and 'target' not in parsed and 'file_path' not in parsed:
            parsed['target'] = 'untitled.txt'
    
    return parsed

def generate_response(prompt, memory_manager):
    """
    Generate response using Ollama with improved error handling and JSON parsing
    """
    try:
        print(f"🧠 Processing: '{prompt}'")
        
        # Get contextual information
        cwd, folders, files = get_contextual_os_info()
        os_context = (
            f"Current working directory is: {cwd}\n"
            f"Folders: {folders}\n"
            f"Files: {files}\n"
            "Use these paths when deciding where to create, delete, or move files."
        )

        # Get memory context
        recent_memory = memory_manager.get_recent_memory(3)
        summary = memory_manager.get_summary()
        vector_hits = memory_manager.get_relevant_memory(prompt, k=2)
        
        # Handle empty memory gracefully
        recent_str = '\n'.join([f"You: {u}\nSpark: {b}" for u, b in recent_memory]) if recent_memory else "No recent conversation"
        vector_str = '\n'.join([f"You: {u}\nSpark: {b}" for u, b in vector_hits]) if vector_hits else "No relevant memory found"
        
        # Format system prompt with memory
        formatted_prompt = SYSTEM_PROMPT.format(
            summary=summary or "No conversation summary available",
            recent=recent_str,
            vector_hits=vector_str,
            query=prompt,
            os_context=os_context
        )
        
        print("🔍 Sending request to Ollama...")
        
        response = requests.post(
            "http://localhost:11434/api/chat",
            
            json={
                "model": "mistral:7b",
                "messages": [
                    {"role": "system", "content": formatted_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()

        # Parse response safely
        if not response.text.strip():
            print("⚠️ Empty response from API")
            return {
                "type": "assistant",
                "message": "I received an empty response. Please try again."
            }
        
        try:
            response_data = response.json()
            content = response_data.get('message', {}).get('content', '')
            content = clean_text(content)
        except json.JSONDecodeError as json_err:
            print(f"⚠️ Invalid JSON response from API: {json_err}")
            return {
                "type": "assistant",
                "message": "I received an invalid response from the server."
            }
        
        if not content:
            print("⚠️ Empty content in API response")
            return {
                "type": "assistant",
                "message": "I didn't receive any content to process."
            }
        
        print(f"🔍 Raw Phi3 Output: {content[:200]}...")  # Show first 200 chars
        
        # Extract and validate JSON
        try:
            parsed = extract_json_from_text(content)
            parsed = validate_parsed_response(parsed)
        except Exception as json_error:
            print(f"⚠️ JSON parsing failed: {json_error}")
            # Fallback: treat as assistant response
            parsed = {
                "type": "assistant",
                "message": content[:500] if len(content) > 500 else content  # Limit length
            }

        print(f"✅ Parsed response: {parsed}")

        # Handle code generation
        if parsed.get("type") == "code":
            print("📝 Generating code with secondary model...")
            try:
                code_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "mistral:7b",
                        "messages": [
                            {"role": "system", "content": "Generate only Python code, no explanation. Write clean, functional code."},
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

                # Generate summary message
                followup_response = requests.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "phi3:3.8b",
                        "messages": [
                            {"role": "system", "content": "You are Spark. Summarize the code generation task in one sentence."},
                            {"role": "user", "content": f"I generated code for: {prompt}"}
                        ],
                        "stream": False
                    },
                    timeout=30
                )
                followup_response.raise_for_status()
                followup_content = followup_response.json().get('message', {}).get('content', '')
                parsed["message"] = clean_text(followup_content) or "I've generated the requested code."
                
            except Exception as code_e:
                print(f"❌ Code generation failed: {code_e}")
                parsed["message"] = f"I tried to generate code but encountered an error: {str(code_e)}"
                parsed["code"] = f"# Code generation failed\n# Error: {str(code_e)}"

        return parsed

    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Cannot connect to Ollama")
        return {
            "type": "assistant", 
            "message": "Cannot connect to Ollama. Please make sure Ollama is running on localhost:11434."
        }
    except requests.exceptions.Timeout:
        print("❌ Request timeout")
        return {
            "type": "assistant", 
            "message": "Request timed out. The model might be taking too long to respond."
        }
    except requests.exceptions.RequestException as req_error:
        print(f"❌ Network error: {req_error}")
        return {
            "type": "assistant", 
            "message": f"Network error: {str(req_error)}"
        }
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {
            "type": "assistant", 
            "message": f"I encountered an unexpected error: {str(e)}"
        }