"""Ask any LLM with an OpenAI-compatible API to suggest priorities and quarters. Posts one issue; edits nothing.

Set repo secrets LLM_BASE_URL, LLM_API_KEY and the workflow input `model`. Free examples:
  Gemini:     https://generativelanguage.googleapis.com/v1beta/openai   model gemini-2.5-flash
  OpenRouter: https://openrouter.ai/api/v1                              model <any ':free' model>
  Groq:       https://api.groq.com/openai/v1                            model llama-3.3-70b-versatile
"""
import json, os, subprocess, urllib.error, urllib.request

repo, model, scope = os.environ["REPO"], os.environ["MODEL"], os.environ.get("SCOPE", "all")
base, key = os.environ["LLM_BASE_URL"].rstrip("/"), os.environ["LLM_API_KEY"]
args = ["gh", "issue", "list", "-R", repo, "--state", "open", "--limit", "300", "--json", "number,title,labels,milestone,body,author"]
if scope != "all":
    args += ["--milestone", scope]
# The repo is public: only the owner's and the bots' issues reach the LLM (anyone else's text could carry
# instructions). OWNERS: comma-separated logins, default the repo owner account.
owners = {o.strip().lower() for o in os.environ.get("OWNERS", "Fa-d").split(",") if o.strip()}
def trusted(i):
    login = ((i.get("author") or {}).get("login") or "").lower()
    return login in owners or login.endswith("[bot]") or login.startswith("app/")
issues = [i for i in json.loads(subprocess.check_output(args))
          if trusted(i) and not any(l["name"] == "digest" for l in i["labels"])]
tasks = [{"n": i["number"], "title": i["title"], "labels": [l["name"] for l in i["labels"]],
          "quarter": (i["milestone"] or {}).get("title"), "body": (i["body"] or "")[:600]} for i in issues]
rules = open("AGENTS.md").read().split("## Prioritising (any LLM)")[1]

prompt = (f"You triage a solo developer's task list. Rules:{rules}\n"
          "Return a markdown table: #, title, impact, urgency, effort, suggested priority, suggested quarter, one-line reason. "
          "Then list the 5 tasks to do next, in order, and any tasks that should be merged or split.\n\n"
          f"Tasks (JSON):\n{json.dumps(tasks)}")
req = urllib.request.Request(f"{base}/chat/completions",
                             data=json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode(),
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
try:
    raw = urllib.request.urlopen(req, timeout=120).read().decode()
except urllib.error.HTTPError as e:
    raise SystemExit(f"the LLM API {e.code}: {e.read().decode()[:500]}")
try:
    answer = json.loads(raw)["choices"][0]["message"]["content"]
except (ValueError, KeyError, IndexError):
    raise SystemExit(f"Unexpected the LLM API response: {raw[:500]!r}")
subprocess.run(["gh", "issue", "create", "-R", repo, "--label", "digest", "--title", f"Triage suggestions ({model}, {scope})",
                "--body", answer + "\n\n_Suggestions only. Apply the ones you agree with on the board._"], check=True)
