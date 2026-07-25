import json
import os
import subprocess

files = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", "scripts", "--", "scripts/"],
    text=True,
).strip().splitlines()
for path in files:
    data = subprocess.check_output(["git", "show", f"scripts:{path}"])
    obj = json.loads(data.decode("utf-8"))
    print(f"{os.path.basename(path)}: {obj.get('description', '')}")
