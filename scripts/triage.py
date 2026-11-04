"""Ask any GitHub Models model to suggest priorities and quarters. Posts one comment issue; edits nothing."""
import json, os, subprocess, urllib.request

repo, model, scope = os.environ["REPO"], os.environ.get("MODEL", "openai/gpt-4.1"), os.environ.get("SCOPE", "all")
args = ["gh", "issue", "list", "-R", repo, "--state", "open", "--limit", "300", "--json", "number,title,labels,milestone,body"]
if scope != "all":
    args += ["--milestone", scope]
issues = [i for i in json.loads(subprocess.check_output(args)) if not any(l["name"] == "digest" for l in i["labels"])]
tasks = [{"n": i["number"], "title": i["title"], "labels": [l["name"] for l in i["labels"]],
          "quarter": (i["milestone"] or {}).get("title"), "body": (i["body"] or "")[:600]} for i in issues]
rules = open("AGENTS.md").read().split("## Prioritising (any LLM)")[1]

prompt = (f"You triage a solo developer's task list. Rules:{rules}\n"
          "Return a markdown table: #, title, impact, urgency, effort, suggested priority, suggested quarter, one-line reason. "
          "Then list the 5 tasks to do next, in order, and any tasks that should be merged or split.\n\n"
          f"Tasks (JSON):\n{json.dumps(tasks)}")
req = urllib.request.Request("https://models.github.ai/inference/chat/completions",
                             data=json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode(),
                             headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"})
answer = json.load(urllib.request.urlopen(req))["choices"][0]["message"]["content"]
subprocess.run(["gh", "issue", "create", "-R", repo, "--label", "digest", "--title", f"Triage suggestions ({model}, {scope})",
                "--body", answer + "\n\n_Suggestions only. Apply the ones you agree with on the board._"], check=True)
