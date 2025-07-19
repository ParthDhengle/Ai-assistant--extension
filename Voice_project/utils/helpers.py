import re, ast

def extract_json_from_text(text):
    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        json_text = match.group(0)
        try:
            parsed = ast.literal_eval(json_text)
            if isinstance(parsed, dict) and "code" in parsed:
                code = parsed["code"]
                if isinstance(code, tuple):
                    code = code[0]
                parsed["code"] = str(code).strip()
            return parsed
        except Exception as e:
            print(f"[!] AST parse failed: {e}")
    return {"type": "assistant", "message": "Failed to extract JSON from response."}
