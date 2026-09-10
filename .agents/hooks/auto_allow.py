import sys
import json
import re

# Commands that ALWAYS require explicit user approval (mutating or sensitive git commands)
ASK_FOR_APPROVAL_PATTERNS = [
    r"^git\s+add\b",
    r"^git\s+commit\b",
    r"^git\s+push\b",
    r"^git\s+reset\b",
    r"^git\s+restore\b",
    r"^git\s+rebase\b",
    r"^git\s+merge\b",
    r"^git\s+clean\b",
    r"^git\s+branch\s+-[dD]\b",
]

# Safe, read-only and automated build/test commands that are automatically allowed
ALLOWED_PATTERNS = [
    # Safe Git read-only commands
    r"^git\s+status\b",
    r"^git\s+diff\b",
    r"^git\s+log\b",
    r"^git\s+show\b",
    r"^git\s+branch\b",
    r"^git\s+rev-parse\b",
    r"^git\s+checkout\s+-b\b",

    # Package management & test execution
    r"^uv\b",
    r"^pytest\b",
    r"^python\b",
    r"^py\b",

    # Shell utility commands
    r"^Get-Command\b",
    r"^New-Item\b",
    r"^Get-Content\b",
    r"^Out-File\b",
    r"^echo\b",
    r"^dir\b",
    r"^ls\b",
]

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "ask"}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        args = tool_call.get("args", {})
        command_line = args.get("CommandLine", "").strip()

        # 1. Check if the command matches the explicit "ask for approval" list
        for pattern in ASK_FOR_APPROVAL_PATTERNS:
            if re.search(pattern, command_line, re.IGNORECASE):
                print(json.dumps({
                    "decision": "force_ask",
                    "reason": f"Approval required for sensitive Git operation: {command_line[:50]}"
                }))
                return

        # 2. Check if the command matches the auto-allowed list
        for pattern in ALLOWED_PATTERNS:
            if re.search(pattern, command_line, re.IGNORECASE):
                print(json.dumps({
                    "decision": "allow",
                    "reason": f"Auto-approved by project allowlist: {command_line[:50]}"
                }))
                return

        # 3. Default fallback: prompt user
        print(json.dumps({
            "decision": "ask",
            "reason": "Command not in project allowlist"
        }))
    except Exception as e:
        print(json.dumps({"decision": "ask", "reason": f"Hook error: {str(e)}"}))

if __name__ == "__main__":
    main()

