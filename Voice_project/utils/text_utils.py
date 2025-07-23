def estimate_tokens(text):
    """Roughly estimate the number of tokens (assuming 4 chars per token)"""
    return len(text) // 4 + 1

def clean_text(text):
    """Clean text to remove problematic Unicode characters"""
    if isinstance(text, str):
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        text = ''.join(char for char in text if ord(char) < 0xD800 or ord(char) > 0xDFFF)
    return text