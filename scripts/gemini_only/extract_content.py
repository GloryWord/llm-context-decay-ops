import sys
import re

def extract_content(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try to find the FULL_REVISED_DOCUMENT block
    # Pattern looks for ### FULL_REVISED_DOCUMENT followed by ```markdown ... ```
    pattern = r'### FULL_REVISED_DOCUMENT\s*[\r\n]+```markdown\s*[\r\n]+(.*?)\n```'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(1)
    
    # Fallback to REVISED_SECTIONS if Document is found there
    pattern_fallback = r'### Document\s*[\r\n]+```markdown\s*[\r\n]+(.*?)\n```'
    match_fallback = re.search(pattern_fallback, content, re.DOTALL)
    if match_fallback:
        return match_fallback.group(1)

    # If still not found, search for any markdown block after REVISED_SECTIONS
    if "REVISED_SECTIONS" in content:
        parts = content.split("REVISED_SECTIONS")
        if len(parts) > 1:
            m = re.search(r'```markdown\s*[\r\n]+(.*?)\n```', parts[1], re.DOTALL)
            if m:
                return m.group(1)

    # Last resort: return everything (likely contains logs)
    return content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_content.py <file_path>")
        sys.exit(1)
    
    print(extract_content(sys.argv[1]))
