#!/usr/bin/env python3
"""Per-project boards for the tracker (Intently-app/tracker#281). gh CLI only, no other dependencies.

  boards.py new <slug> "<Name>" [--repos a,b]   label project:<slug> + a board copied from the Hub (fields, views)
  boards.py backfill [--apply]                   give every issue a project:* label (and `chore` to pipeline chores)
  boards.py sync [--apply]                       put each labelled issue on its board and on the Hub; chores off
                                                 every board; board Status mirrored to the Hub
  boards.py close-audit [--days 7] [--apply]     closed issues without a verified PR or a "Verified:" line get
                                                 the label needs:verify (flag only; nothing is reopened)

Without --apply nothing changes on GitHub; the commands print what they would do.
The project board is where agents set Status; the Hub mirrors it (one-way, board -> Hub) on every sync.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(os.path.dirname(HERE), "projects.json")
# Client work lives in private repos and in this untracked file, so the public tracker never names it.
PRIVATE_CONF_PATH = os.path.join(os.path.dirname(HERE), "projects.private.json")
CHORE_TITLE = re.compile(r"^(Docs: update|Design: update the canvas|Changelog: one line|Article: draft|Check impact:)")
MIRRORED_FIELDS = ["Status", "Priority", "Size", "Quarter", "Blocked on", "Next step", "Code repo"]
VERIFY_MARK = re.compile(r"<!-- respite-verify v1 head=[0-9a-f]{40} issue=([A-Za-z0-9._/-]+#\d+) verdict=PASS -->")


def gh(*args, parse=True, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return json.loads(r.stdout) if parse and r.stdout.strip() else r.stdout


def load_conf():
    with open(CONF_PATH) as f:
        conf = json.load(f)
    if os.path.exists(PRIVATE_CONF_PATH):
        with open(PRIVATE_CONF_PATH) as f:
            for p in json.load(f).get("projects", []):
                p["private"] = True
                conf["projects"].append(p)
    return conf


def save_conf(conf):
    public = dict(conf, projects=[p for p in conf["projects"] if not p.get("private")])
    with open(CONF_PATH, "w") as f:
        json.dump(public, f, indent=2)
        f.write("\n")


def all_issues(repo):
    return gh("issue", "list", "-R", repo, "--state", "all", "--limit", "2000",
              "--json", "number,title,labels,state,stateReason,closedAt,url,id")


def issues_everywhere(conf):
    """The tracker's issues plus those of every project that keeps its issues in its own (private) repo."""
    repos = [conf["repo"]] + sorted({p["issue_repo"] for p in conf["projects"] if p.get("issue_repo")})
    return [i for r in repos for i in all_issues(r)]


def labels_of(issue):
    return {l["name"] for l in issue["labels"]}


def board_items(owner, number):
    return gh("project", "item-list", str(number), "--owner", owner, "--format", "json", "--limit", "3000")["items"]


class Board:
    """A project's fields (name -> id, options) and items (issue url -> item)."""

    def __init__(self, owner, number):
        self.owner, self.number = owner, number
        view = gh("project", "view", str(number), "--owner", owner, "--format", "json")
        self.id = view["id"]
        self.fields = {}
        for f in gh("project", "field-list", str(number), "--owner", owner, "--format", "json", "--limit", "100")["fields"]:
            self.fields[f["name"]] = {"id": f["id"], "type": f["type"],
                                      "options": {o["name"]: o["id"] for o in f.get("options", [])}}
        self.items = {}
        for it in board_items(owner, number):
            url = (it.get("content") or {}).get("url")
            if url:
                self.items[url] = it

    @staticmethod
    def value(item, field):
        # item-list exposes custom fields as lowercase keys ("next step", "code repo").
        v = item.get(field.lower())
        return v if v not in ("", None) else None

    def add(self, url):
        it = gh("project", "item-add", str(self.number), "--owner", self.owner, "--url", url, "--format", "json")
        self.items[url] = it
        return it

    def remove(self, url):
        gh("project", "item-delete", str(self.number), "--owner", self.owner, "--id", self.items[url]["id"], parse=False)
        del self.items[url]

    def set(self, url, field, value):
        f = self.fields.get(field)
        if not f or value is None:
            return False
        args = ["project", "item-edit", "--id", self.items[url]["id"], "--project-id", self.id, "--field-id", f["id"]]
        if f["options"]:
            if value not in f["options"]:
                return False
            args += ["--single-select-option-id", f["options"][value]]
        else:
            args += ["--text", str(value)]
        gh(*args, parse=False)
        return True


# --------------------------------------------------------------------------------------------------- new
def cmd_new(conf, slug, name, repos, apply):
    if any(p["slug"] == slug for p in conf["projects"]):
        sys.exit(f"project {slug} already exists in projects.json")
    label = f"project:{slug}"
    print(f"label {label}; board '{name}' copied from Hub #{conf['hub']}; linked to {conf['repo']}")
    if not apply:
        return
    gh("label", "create", label, "-R", conf["repo"], "--color", "BFD4F2", "--description", f"{name} project", "--force", parse=False)
    out = gh("project", "copy", str(conf["hub"]), "--source-owner", conf["owner"], "--target-owner", conf["owner"],
             "--title", name, "--format", "json")
    number = out["number"]
    gh("project", "link", str(number), "--owner", conf["owner"], "--repo", conf["repo"], parse=False, check=False)
    conf["projects"].append({"slug": slug, "name": name, "label": label, "board": number, "repos": repos})
    save_conf(conf)
    print(f"created board #{number}: https://github.com/users/{conf['owner']}/projects/{number}")


# ---------------------------------------------------------------------------------------------- backfill
def guess_project(issue, hub_item, conf):
    title = issue["title"]
    for p in conf["projects"]:  # a word in the title, from each project's title_keywords
        if any(re.search(rf"\b{re.escape(k)}\b", title, re.I) for k in p.get("title_keywords", [])):
            return p["slug"]
    for p in conf["projects"]:
        if issue["number"] in p.get("issues", []):
            return p["slug"]
    if hub_item and hub_item.get("project") == "Respite":
        return "respite"
    if hub_item and hub_item.get("project") == "Other":  # before the labels, "Other" on the Hub meant Hisab
        return "hisab"
    if CHORE_TITLE.match(title) or re.search(r"\b(respite|pawse|intently)\b", title, re.I):
        return "respite"
    lab = labels_of(issue)
    if lab & {"digest", "metrics-digest"} or any(l.startswith(("platform:", "area:")) for l in lab):
        return "respite"
    return None


def cmd_backfill(conf, apply):
    issues = all_issues(conf["repo"])
    hub = {(it.get("content") or {}).get("url"): it for it in board_items(conf["owner"], conf["hub"])}
    known = {p["slug"] for p in conf["projects"]}
    todo, unknown = [], []
    for i in issues:
        lab = labels_of(i)
        add = []
        if not any(l.startswith("project:") for l in lab):
            slug = guess_project(i, hub.get(i["url"]), conf)
            if slug in known:
                add.append(f"project:{slug}")
            elif i["state"] == "OPEN":
                unknown.append(i)
        if CHORE_TITLE.match(i["title"]) and "chore" not in lab:
            add.append("chore")
        if add:
            todo.append((i, add))
    for i, add in todo:
        print(f"#{i['number']:<4} +{' +'.join(add):<32} {i['title'][:80]}")
        if apply:
            gh("issue", "edit", str(i["number"]), "-R", conf["repo"], *sum([["--add-label", a] for a in add], []), parse=False)
    print(f"\n{len(todo)} issue(s) {'labelled' if apply else 'to label'}")
    if unknown:
        print("\nOpen issues with no project (label them by hand):")
        for i in unknown:
            print(f"  #{i['number']} {i['title']}")


# -------------------------------------------------------------------------------------------------- sync
def cmd_sync(conf, apply):
    issues = issues_everywhere(conf)
    hub = Board(conf["owner"], conf["hub"])
    boards = {p["slug"]: Board(conf["owner"], p["board"]) for p in conf["projects"]}
    by_label = {p["label"]: p["slug"] for p in conf["projects"]}
    stats = {"added": 0, "removed": 0, "mirrored": 0}
    unlabelled = []

    def act(msg, fn, *a):
        print(("" if apply else "would: ") + msg)
        if apply:
            fn(*a)

    for i in issues:
        url, lab = i["url"], labels_of(i)
        chore = "chore" in lab
        want = {by_label[l] for l in lab if l in by_label}
        if not want and not chore and i["state"] == "OPEN":
            unlabelled.append(i)
        for slug, b in boards.items():
            on = url in b.items
            if (slug in want and not chore) and not on:
                if i["state"] == "CLOSED" and url not in hub.items:
                    continue  # closed history that never was on the Hub stays off the new boards
                stats["added"] += 1
                print(("" if apply else "would: ") + f"add #{i['number']} to {slug}")
                if apply:
                    b.add(url)
                    src = hub.items.get(url) or {}
                    for f in MIRRORED_FIELDS:
                        b.set(url, f, Board.value(src, f))
                    if i["state"] == "CLOSED":
                        b.set(url, "Status", "Done")
            elif on and (chore or slug not in want):
                stats["removed"] += 1
                act(f"remove #{i['number']} from {slug} ({'chore' if chore else 'not ' + slug})", b.remove, url)
        if chore and url in hub.items:
            stats["removed"] += 1
            act(f"remove chore #{i['number']} from the Hub", hub.remove, url)
            continue
        if want and not chore and url not in hub.items and i["state"] == "OPEN":
            stats["added"] += 1
            act(f"add #{i['number']} to the Hub", hub.add, url)
        # mirror Status from the project board to the Hub
        for slug in want:
            b = boards[slug]
            if url in b.items and url in hub.items:
                bs, hs = Board.value(b.items[url], "Status"), Board.value(hub.items[url], "Status")
                if bs and bs != hs:
                    stats["mirrored"] += 1
                    act(f"Hub Status of #{i['number']}: {hs} -> {bs} (from {slug})", hub.set, url, "Status", bs)
            break
    print(f"\n{stats['added']} add, {stats['removed']} remove, {stats['mirrored']} Status mirror"
          f"{'' if apply else ' (dry run)'}")
    if unlabelled:
        print("\nOpen issues with no project:* label (run backfill or label by hand):")
        for i in unlabelled:
            print(f"  {i['url']} {i['title']}")


# -------------------------------------------------------------------------------------------- close-audit
def cmd_close_audit(conf, days, apply):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = """query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){
      comments(last:20){nodes{body}}
      timelineItems(itemTypes:[CLOSED_EVENT],last:1){nodes{...on ClosedEvent{closer{__typename
        ...on PullRequest{number repository{nameWithOwner} comments(last:50){nodes{body}}}}}}}}}}"""
    owner, name = conf["repo"].split("/")
    flagged = []
    for i in all_issues(conf["repo"]):
        if i["state"] != "CLOSED" or i["stateReason"] in ("NOT_PLANNED", "DUPLICATE"):
            continue
        if not i["closedAt"] or datetime.fromisoformat(i["closedAt"].replace("Z", "+00:00")) < since:
            continue
        lab = labels_of(i)
        if lab & {"chore", "docs:auto", "digest", "metrics-digest", "needs:verify"}:
            continue
        d = gh("api", "graphql", "-F", f"owner={owner}", "-F", f"name={name}", "-F", f"n={i['number']}", "-f", f"query={q}")
        issue = d["data"]["repository"]["issue"]
        closer = (issue["timelineItems"]["nodes"] or [{}])[0].get("closer") or {}
        ok, why = False, "closed by hand with no 'Verified:' line"
        if closer.get("__typename") == "PullRequest":
            ref = f"{conf['repo']}#{i['number']}"
            marks = [m for c in closer["comments"]["nodes"] for m in VERIFY_MARK.findall(c["body"])]
            ok = ref in marks
            why = f"closed by {closer['repository']['nameWithOwner']}#{closer['number']} with no verifier PASS for it"
        if not ok and any(re.search(r"^\**Verified:", c["body"], re.M) for c in issue["comments"]["nodes"]):
            ok = True
        if not ok:
            flagged.append((i, why))
    for i, why in flagged:
        print(f"#{i['number']:<4} {why}: {i['title'][:70]}")
        if apply:
            gh("issue", "edit", str(i["number"]), "-R", conf["repo"], "--add-label", "needs:verify", parse=False)
    print(f"\n{len(flagged)} closed issue(s) in the last {days} days {'flagged' if apply else 'to flag'} needs:verify")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    apply = "--apply" in argv
    argv = [a for a in argv if a != "--apply"]
    conf = load_conf()
    cmd = argv[0]
    if cmd == "new" and len(argv) >= 3:
        repos = argv[argv.index("--repos") + 1].split(",") if "--repos" in argv else []
        cmd_new(conf, argv[1], argv[2], repos, apply)
    elif cmd == "backfill":
        cmd_backfill(conf, apply)
    elif cmd == "sync":
        cmd_sync(conf, apply)
    elif cmd == "close-audit":
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
        cmd_close_audit(conf, days, apply)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
