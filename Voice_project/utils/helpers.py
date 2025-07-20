import json
import re

def extract_json_from_text(text):
    """
    Extract JSON from text that might contain markdown, explanations, or other content.
    """
    if not text:
        raise ValueError("Empty text provided")
    
    # Clean the text
    text = text.strip()
    
    # Try to find JSON blocks first
    json_patterns = [
        r'```json\s*(\{.*?\})\s*```',  # JSON in code blocks
        r'```\s*(\{.*?\})\s*```',      # JSON in generic code blocks
        r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',  # Simple JSON object
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # If no JSON blocks found, try to extract JSON from the entire text
    try:
        # Find the first { and last }
        start = text.find('{')
        end = text.rfind('}')
        
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end+1]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # Last resort: try to parse the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # If all else fails, return a default structure
    raise ValueError(f"Could not extract valid JSON from: {text[:200]}...")

def clean_filename(filename):
    """Clean filename to remove invalid characters"""
    # Remove invalid characters for filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

def validate_path(path):
    """Basic path validation"""
    if not path:
        return False
    
    # Check for dangerous patterns
    dangerous_patterns = ['../', '..\\', '/etc/', '/sys/', 'C:\\Windows\\']
    path_lower = path.lower()
    
    for pattern in dangerous_patterns:
        if pattern.lower() in path_lower:
            return False
    
    return True