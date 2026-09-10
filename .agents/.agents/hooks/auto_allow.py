import os
import sys

# Delegate to parent hooks/auto_allow.py
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_auto_allow = os.path.abspath(os.path.join(script_dir, "..", "..", "hooks", "auto_allow.py"))

with open(parent_auto_allow, "r") as f:
    code = f.read()
exec(compile(code, parent_auto_allow, "exec"))

