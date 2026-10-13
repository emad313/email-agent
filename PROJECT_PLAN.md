# Project Plan: Local Email AI Agent

## Goal

Build a runnable Windows-friendly Python CLI that polls Gmail through OAuth, processes
messages only from an exact configured sender allowlist, uses a local Ollama model for
structured task classification, performs only explicitly implemented safe actions, and
optionally drafts or sends replies.

## Architecture

- `main.py`: CLI entry point, diagnostics, one-shot polling, and continuous polling.
- `config.py`: YAML configuration loading, defaults, validation, and safe path handling.
- `gmail_client.py`: Gmail OAuth desktop flow, message retrieval/parsing, threading, drafts,
  replies, and recoverable API error handling.
- `ollama_client.py`: local Ollama health/model checks, bounded generation, and JSON parsing.
- `agent.py`: sender authorization, task validation, orchestration, reply/draft decisions,
  duplicate prevention, and explicit processing states.
- `prompts.py`: system and task-classification prompt templates treating email as untrusted data.
- `research.py`: bounded DuckDuckGo-based public research and source collection.
- `safe_actions.py`: fixed allowlisted Python actions confined to `workspace/`.
- `storage.py`: SQLite schema, message uniqueness, state transitions, action logs, and
  uncertain-send reconciliation data.
- `README.md`: setup, OAuth, Ollama, operation, Windows Task Scheduler, security, and
  troubleshooting instructions.

## Security decisions

1. Use Gmail OAuth 2.0 Desktop credentials; never request or store a Gmail password.
2. Compare normalized parsed `From` addresses by exact equality against `allowed_senders`.
3. Keep sender authorization separate from task/action permissions.
4. Treat email, attachments, web results, and model output as untrusted data.
5. Validate model JSON and reject unknown actions, fields, formats, paths, and destinations.
6. Do not expose arbitrary shell execution; computer actions map to fixed Python functions.
7. Confine generated files and safe actions to the configured workspace.
8. Use SQLite uniqueness and explicit states to prevent duplicate processing and replies.
9. Keep automatic replies disabled by default and save inspectable drafts instead.
10. Avoid logging message bodies, credentials, tokens, or unnecessary personal data.

## Implementation phases

1. **Configuration and persistence**
   - Add example YAML configuration and validated settings.
   - Implement SQLite schema and state/action APIs.
2. **External integrations**
   - Implement Gmail OAuth/API wrapper and safe message parsing/sending.
   - Implement Ollama HTTP client and strict response validation.
   - Implement bounded web research.
3. **Agent workflow**
   - Add exact sender filtering, duplicate checks, task routing, safe action execution,
     file generation, draft creation, optional reply sending, and error recovery.
4. **CLI and operations**
   - Add `--once`, continuous mode, `--check-config`, `--test-gmail`,
     `--test-ollama`, and `--status`.
   - Add console/file logging and clean shutdown.
5. **Documentation and tests**
   - Document Windows setup, OAuth, Ollama, Task Scheduler, safe auto-reply rollout,
     troubleshooting, limitations, and credential protection.
   - Add offline unit tests for configuration, sender matching, safe actions, storage,
     and model/task validation.
6. **Verification**
   - Run syntax compilation and the complete offline test suite.
   - Review imports, dependency names, configuration keys, path confinement, and Gmail
     API request/thread behavior.

## Acceptance checks

- Only exact allowlisted senders can trigger processing.
- Gmail OAuth works without storing a password.
- `--once` performs one bounded cycle; continuous mode recovers from transient errors.
- Model output is validated before any task or action runs.
- Files are created only under `workspace/`, with safe names and no silent overwrite.
- Computer actions are limited to the fixed Python allowlist.
- Processed-message state persists across restarts and prevents duplicate replies.
- Automatic replies are opt-in; disabled mode produces local drafts.
- Diagnostics do not send replies or execute email-requested tasks.
- Tests use mocks and do not require live Gmail or Ollama services.
