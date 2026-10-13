# Local Email AI Agent

This is a CLI-only Gmail assistant for Windows 10/11. It uses Gmail's OAuth 2.0
desktop flow, a local Ollama model, SQLite, and a small fixed action allowlist.
It does not request or store a Gmail password and it never executes arbitrary
PowerShell, CMD, Python, or shell commands.

## Quick start (PowerShell)

```powershell
cd "C:\path\to\email-agent"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
New-Item -ItemType Directory -Force workspace, drafts
python main.py --check-config
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` directly, or change
the policy only for the current process with
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

If `python` is also not recognized, install Python 3.10 or newer from
https://www.python.org/downloads/windows/ and select **Add python.exe to PATH**
during installation. You can also run the installed interpreter directly, for
example:

```powershell
& "C:\Users\<YourUser>\AppData\Local\Programs\Python\Python313\python.exe" -m venv .venv
```

## Gmail OAuth setup

1. Open Google Cloud Console and create/select a project.
2. Enable **Gmail API**.
3. Configure the OAuth consent screen. For Workspace accounts, an administrator
   may need to approve the app or mark it trusted.
4. Create OAuth credentials for a **Desktop app**, download the JSON, and save it
   as `credentials.json` in this project directory.
5. Add exact approved addresses under `allowed_senders` in `config.yaml`, separated
   by commas. For example:

   ```yaml
   allowed_senders: "alice@example.com, bob@example.com, team@example.org"
   ```

   A YAML list is also accepted, but comma-separated text is the recommended format.
6. Run `python main.py --test-gmail`. A browser opens for the independent OAuth
   flow on first use; the refresh token is stored locally in `token.json`.

The `gmail.modify` scope is used because the agent reads messages and sends replies.
Protect `credentials.json` and `token.json`, do not commit them, and revoke access
from the Google Account security page when retiring the agent. Some Workspace
administrators restrict OAuth scopes or require verification/approval.

## Ollama

Install Ollama from its official Windows distribution, then:

```powershell
ollama pull qwen2.5:3b
ollama list
python main.py --test-ollama
```

The endpoint, model, context, timeout, and output limit are configurable in
`config.yaml`. Start Ollama before the agent; if it starts slowly, the agent will
log a recoverable error and retry on the next polling cycle.

## Running

```powershell
python main.py --once
python main.py
python main.py --check-config
python main.py --test-gmail
python main.py --test-ollama
python main.py --status
```

Automatic replies are disabled by default. In that mode, replies are written to
`drafts\` for inspection. Test with an address you control, inspect logs and
drafts, then set `agent.auto_reply: true`. The sender is always the original
allowlisted sender; email text cannot select a different recipient.

## Supported tasks and limits

The model can classify `reply`, `research`, `create_file`, and `computer`.
Research uses a bounded DuckDuckGo HTML search and includes source URLs in the
model-generated summary. Web and email content are untrusted data and are never
treated as security instructions.

Files support Markdown, text, CSV, and JSON and are written only under `workspace`.
Names, size, overwrite behavior, and JSON/CSV content are validated. Computer
actions are only `list_workspace`, `create_daily_note`, and `disk_usage`.

## Tests

```powershell
python -m pytest -q
```

Tests mock or isolate integrations and do not send mail or require Ollama.

## Windows Task Scheduler

Create a task with **At log on** trigger, running as your standard Windows user:

- Program: `C:\path\to\email-agent\.venv\Scripts\python.exe`
- Arguments: `C:\path\to\email-agent\main.py`
- Start in: `C:\path\to\email-agent`

Do not run it as Administrator or hide it. Verify it in Task Scheduler and inspect
`agent.log`. Stop it with **End** in Task Scheduler or Ctrl+C in the terminal.
Make sure Ollama is configured to start with Windows, or allow the agent's polling
retry to wait until it is ready.

## Troubleshooting and limitations

- OAuth errors usually require checking the consent screen, Workspace admin policy,
  credential type, and deleting an intentionally stale `token.json` before retrying.
- `Ollama model is not installed` means `ollama pull` has not completed or the model
  name differs from `config.yaml`.
- Gmail/network/rate-limit failures are logged and retried. If a send transport error
  occurs, the agent checks Sent mail first and records `replied` when it can reconcile
  the message; otherwise it records `send_uncertain`. Do not blindly resend an
  uncertain send.
- A local model can misunderstand requests. Keep auto-reply disabled while validating.
- No claim is made that a research snippet verifies a fact; summaries report source
  links and uncertainty.
- The first version does not attach generated files to email; files remain local in
  the workspace.
