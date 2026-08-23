# harah-bot — the GitHub App identity

When the app credentials are present on the mini, Harah's outward writes —
PR comments, pushed commits, merges — happen AS **harah-bot[bot]** (the
dependabot-style badge), not as Alex's login. Without them, everything
falls back to the legacy identity (Alex's gh auth + the `— Harah`
signature + the Harah git author). Detection is automatic: routines try
`app/as-bot.sh` and fall back on its clear exit-1.

## REGISTERED 2026-08-23 — App ID 4689872

Created live (Alex logged in; the session drove the form on his word) and
installed on BOTH `lxRbckl` and `lxrbckl-labs` (all repositories). First
token minted and verified (40 org repos visible); first comment posted as
`harah-bot[bot]`. **Granted permission set — Alex's full-custodian word
("everything except deleting repositories"), wider than the original plan
below:** write on contents, PRs, issues, checks, statuses, actions,
administration, workflows, deployments, environments, pages, packages,
discussions, projects, merge queues, advisories, code scanning, Dependabot
alerts, webhooks, custom properties; read on metadata + misc read-onlies;
**all four secrets permissions: none** (exfiltration surface — POLICY
forbids). CAVEAT: GitHub's Administration toggle cannot exclude repo
deletion, so the no-delete line is enforced by POLICY's hard floor, not by
GitHub. Remaining step: **the .pem sits on the MacBook**
(~/Downloads/harah-bot.2026-08-23.private-key.pem + a staged copy in
~/.harah/app/ used for verification) — move both values to the MINI's
~/.harah/app/ per below, then DELETE the MacBook copies (mini-only rule).

## One-time registration (the original runbook, kept for a future re-key)

1. github.com → Settings → Developer settings → **GitHub Apps** → New GitHub App
   - **Name:** `harah-bot` (slug verified available 2026-08-23)
   - **Homepage:** `https://github.com/lxrbckl-labs/Project-Harah`
   - **Webhook:** UNCHECK "Active" (we poll; webhooks are a later upgrade)
   - **Repository permissions:** Contents **R/W** · Pull requests **R/W** ·
     Issues **R/W** · Checks **Read** · Metadata **Read** ·
     Dependabot alerts **Read**
   - **Where can it be installed:** Any account
2. After create: note the **App ID** (top of the app page), then
   **Generate a private key** — a `.pem` downloads.
3. **Install the app** (left sidebar → Install App) on BOTH `lxRbckl` and
   `lxrbckl-labs` → All repositories.
4. On the MINI (transfer the .pem by Screen Sharing/AirDrop — NEVER through
   a git repo):
   ```bash
   mkdir -p ~/.harah/app && chmod 700 ~/.harah/app
   echo <APP_ID> > ~/.harah/app/app-id
   mv <downloaded>.pem ~/.harah/app/private-key.pem
   chmod 600 ~/.harah/app/*
   bash ~/lxrbckl-dev/Project-Harah/skill/app/mint-token.sh lxrbckl-labs && echo OK
   ```
   `OK` = the whole chain works. Delete the pem from Downloads/anywhere else.

## What changes when credentials exist

- Mentions/summons replies and fix-pushes: authored by `harah-bot[bot]`.
- Grooming/resolver comments and merges: same.
- `@harah-bot` autocompletes in mention pickers once the app is installed.
- POLICY's authorship test upgrades from signature-based to login-based for
  post-app history (the signature stays as belt-and-suspenders).

## Security notes

- The .pem is the bot's whole identity: mini-only, 600, never in any repo,
  never in logs. Tokens are 1-hour installation tokens, cached 50 min in
  ~/.harah/app/ (700).
- Never grant the app Administration or Secrets permissions — its authority
  must stay narrower than POLICY, not wider.
