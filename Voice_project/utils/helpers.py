# utils/helpers.py
import json
import re

def extract_json_from_text(text):
    """
    Extract JSON from text with multiple fallback strategies
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Strategy 1: Direct JSON parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Find JSON blocks in text
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested braces
        r'\{.*?\}',  # Simple braces
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                match = match.strip()
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    
    # Strategy 3: Extract key-value pairs manually
    try:
        # Look for common patterns
        type_match = re.search(r'"type":\s*"(\w+)"', text)
        message_match = re.search(r'"message":\s*"([^"]+)"', text)
        action_match = re.search(r'"action":\s*"([^"]+)"', text)
        
        result = {}
        
        if type_match:
            result["type"] = type_match.group(1)
        if message_match:
            result["message"] = message_match.group(1)
        if action_match:
            result["action"] = action_match.group(1)
            
        # Extract additional fields based on action type
        if result.get("action") == "open_website":
            url_match = re.search(r'"url":\s*"([^"]+)"', text)
            if url_match:
                result["url"] = url_match.group(1)
        elif result.get("action") == "play_youtube_video":
            query_match = re.search(r'"query":\s*"([^"]+)"', text)
            if query_match:
                result["query"] = query_match.group(1)
        elif result.get("action") in ["create_file", "delete_file"]:
            target_match = re.search(r'"target":\s*"([^"]+)"', text)
            if target_match:
                result["target"] = target_match.group(1)
        
        if result and "type" in result:
            return result
            
    except Exception:
        pass
    
    # Strategy 4: Intelligent parsing based on content
    return parse_intent_from_text(text)

def parse_intent_from_text(text):
    """
    Parse user intent when JSON extraction fails
    """
    text_lower = text.lower()
    
    # Common website patterns
    if any(site in text_lower for site in ['youtube', 'google', 'facebook', 'twitter']):
        if 'youtube' in text_lower:
            if any(word in text_lower for word in ['play', 'watch', 'song', 'music', 'video']):
                # Extract potential search query
                query_patterns = [
                    r'play\s+([^.!?]+)',
                    r'watch\s+([^.!?]+)',
                    r'search\s+(?:for\s+)?([^.!?]+)',
                ]
                
                query = "music"  # default
                for pattern in query_patterns:
                    match = re.search(pattern, text_lower)
                    if match:
                        query = match.group(1).strip()
                        # Clean up the query
                        query = re.sub(r'\s+on\s+youtube.*$', '', query)
                        break
                
                return {
                    "type": "os",
                    "action": "play_youtube_video",
                    "query": query,
                    "message": f"Playing {query} on YouTube"
                }
            else:
                return {
                    "type": "os",
                    "action": "open_website",
                    "url": "youtube.com",
                    "message": "Opening YouTube"
                }
    
    # File operations
    if any(word in text_lower for word in ['create', 'make', 'new']) and 'file' in text_lower:
        filename_match = re.search(r'(?:create|make|new)\s+(?:a\s+)?(?:file\s+)?(?:named\s+|called\s+)?([^\s.]+(?:\.[a-z]+)?)', text_lower)
        filename = filename_match.group(1) if filename_match else "new_file.txt"
        return {
            "type": "os",
            "action": "create_file",
            "target": filename,
            "message": f"Creating file {filename}"
        }
    
    # Open applications
    app_patterns = [
        (r'open\s+([a-zA-Z]+)', 'open_application'),
        (r'start\s+([a-zA-Z]+)', 'open_application'),
        (r'launch\s+([a-zA-Z]+)', 'open_application'),
    ]
    
    for pattern, action in app_patterns:
        match = re.search(pattern, text_lower)
        if match:
            app_name = match.group(1)
            return {
                "type": "os",
                "action": action,
                "app_name": app_name,
                "message": f"Opening {app_name}"
            }
    
    # Default to assistant response
    return {
        "type": "assistant",
        "message": text if text else "I'm not sure how to help with that."
    }

def validate_json_response(data):
    """
    Validate and fix common issues in JSON responses
    """
    if not isinstance(data, dict):
        return {
            "type": "assistant",
            "message": "Invalid response format"
        }
    
    # Ensure required fields
    if 'type' not in data:
        data['type'] = 'assistant'
    
    if 'message' not in data:
        if data['type'] == 'os':
            action = data.get('action', 'unknown')
            data['message'] = f"Performing {action}"
        else:
            data['message'] = "Processing request"
    
    return data