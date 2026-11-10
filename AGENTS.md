# Hub protocol for AI agents (any model)

This repo is the owner's single task list for every project on every GitHub account. Each issue is one
task. The board is the GitHub Project **Hub** (`gh project view 2 --owner Fa-d --web`). Every agent
(Claude Code, Codex, Gemini CLI, Aider, a GitHub Action) follows the same rules. Work only through the
`gh` CLI or the GitHub API, so the hub stays tool- and model-agnostic.

## Where things are

| What | Where |
|---|---|
| Tasks | issues in `Intently-app/tracker` |
| Quarter | milestone `Q4-2026`, `Q1-2027`, … (also the project field `Quarter`) |
| Platform / area | labels `platform:*`, `area:*`, `bug` |
| Status | project field `Status`: Todo, In progress, Blocked, Done (closing an issue = Done) |
| Priority / size | project fields `Priority` (P0 urgent … P3 someday), `Size` (S days, M 1–3 weeks, L month+) |
| Code location | project field `Code repo` (`owner/repo`), any account |
| Why it's waiting | label `blocked` + field `Blocked on` |
| Owner-only steps | label `needs:human` (console clicks, sign-ins, payments, approvals) |
| Selected for an agent | label `agent:ready` |

## At the start of a session

1. Read the queue: `gh issue list -R Intently-app/tracker --label agent:ready --state open`.
2. If the owner asked for something specific, find its issue first:
   `gh issue list -R Intently-app/tracker --search "<words>" --state all`. If there is none, create one before
   starting work (see "Filing").

## While working

- Comment on the issue when you start, with what you plan to do. Remove `agent:ready`. Set Status to
  In progress.
- Do the work in the repo named in `Code repo`. Reference the task in commits and PRs as
  `Intently-app/tracker#<n>` (a full reference works across accounts).
- Never do anything under `needs:human` yourself. Write the exact steps for the owner in a comment.

## At the end of every session (required)

For each issue you touched:
- **Done and verified:** close it with a comment that says what changed, where (commit, PR, deploy
  id), and how it was verified. Work that sits on a branch is not done yet: see "Finished code" below.
- **Partly done:** comment with done / not done / exact next step. Update the `Next step` field.
- **Waiting:** add `blocked`, set Status Blocked, and fill `Blocked on` (who or what, and since when).

Also file, before you stop:
- every new bug you noticed, even if you didn't fix it (label `bug`);
- every follow-up the work revealed;
- every step you handed to the owner (label `needs:human`).

**Never leave state only in chat.** If it isn't in an issue, it is lost.

## Finished code: the pull request is the trigger

Code is done when it is on `main`, not when the branch is pushed. Agents never merge and never close
a finished code task by hand. The pull request does both:

1. Push the branch and open a pull request. Put `Closes Intently-app/tracker#<n>` in its description
   and add the label `auto:merge`.
2. Comment on the issue with what changed, the commit, the pull request and the test result. Leave it
   open, Status In progress, `Next step`: "merges itself when checks pass".
3. When the pull request's checks pass it merges itself, and the merge closes the issue with a comment
   pointing at the merge commit.

If something is left (an owner-only step, a failing check, a follow-up), write `Part of
Intently-app/tracker#<n>` instead of `Closes`, so the merge does not close the issue. A pull request
that changes `.github/` never auto-merges; the owner merges it. In a repo that has no `auto:merge`
workflow yet, open the pull request the same way and write "owner: merge" in `Next step`.

## Filing

`gh issue create -R Intently-app/tracker --title "<verb + object>" --milestone <quarter> --label platform:<x> --label area:<y> --body "<context, done when, next step>"`,
then `gh project item-add 2 --owner Fa-d --url <issue url>` and set the fields. Before creating an
issue, search for an existing one. Titles start with a verb. The body ends with **Done when:**.

## Prioritising (any LLM)

Score each task on impact on installs, revenue or retention (1–5), urgency (deadline, decay, or
blocking others; 1–5) and effort (S=1, M=2, L=3). Priority = (impact × urgency) / effort:
≥ 8 → P0, 4–8 → P1, 2–4 → P2, < 2 → P3. Put a task in the quarter when its dependencies clear.
Propose changes as a comment; the owner applies them.
