"""Weekly digest of open tasks, grouped by what needs attention. Uses only the gh CLI."""
import json, os, subprocess
from datetime import datetime, timedelta, timezone

repo = os.environ["REPO"]
issues = json.loads(subprocess.check_output(["gh", "issue", "list", "-R", repo, "--state", "open", "--limit", "500",
                                             "--json", "number,title,labels,milestone,updatedAt"]))
issues = [i for i in issues if not any(l["name"] == "digest" for l in i["labels"])]
has = lambda i, n: any(l["name"] == n for l in i["labels"])
stale_before = datetime.now(timezone.utc) - timedelta(days=14)
line = lambda i: f"- #{i['number']} {i['title']} ({(i['milestone'] or {}).get('title', 'no quarter')})"

sections = [
    ("Waiting on you (needs:human)", [i for i in issues if has(i, "needs:human")]),
    ("Blocked", [i for i in issues if has(i, "blocked")]),
    ("Selected for an agent", [i for i in issues if has(i, "agent:ready")]),
    ("Open bugs", [i for i in issues if has(i, "bug")]),
    ("No update in 14 days", [i for i in issues if datetime.fromisoformat(i["updatedAt"].replace("Z", "+00:00")) < stale_before]),
]
print(f"{len(issues)} open tasks.\n")
for name, rows in sections:
    print(f"## {name} ({len(rows)})")
    print("\n".join(map(line, rows)) or "- none")
    print()
