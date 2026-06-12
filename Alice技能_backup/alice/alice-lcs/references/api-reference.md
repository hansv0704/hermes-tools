# LCS v5.3 API Reference

Base URL: `http://localhost:5001`

## Session

| Method | Endpoint | Body | Returns |
|:--|:--|:--|:--|
| POST | `/api/session/start` | `{"workdir": "..."}` | Session info + auto_workspace result |
| POST | `/api/session/stop` | — | `{"status":"ok"}` |
| GET | `/api/session/info` | — | `{active, workdir, started_at, tracked_count, workspace_count}` |

Session start automatically:
1. Adds workdir as workspace (if < 5000 files)
2. Returns `auto_workspace` field with result/error

## File Tracking

| Method | Endpoint | Body | Notes |
|:--|:--|:--|:--|
| POST | `/api/files/track` | `{"path":"...","content":"...","workdir":"?"}` | Manual push (rarely needed since v5.2) |
| POST | `/api/files/untrack` | `{"path":"..."}` | Remove from tracked list |
| GET | `/api/tracked` | — | Returns all tracked files with metadata |

## Workspaces (v5.3: persistent)

| Method | Endpoint | Body | Notes |
|:--|:--|:--|:--|
| POST | `/api/workspace/add` | `{"path":"...","name":"?"}` | Auto-saves to `lcs_workspaces.json` |
| POST | `/api/workspace/remove` | `{"path":"..."}` | Auto-removes from JSON |
| GET | `/api/workspace/list` | — | Returns all workspaces with file counts |

Default workspaces (loaded on startup):
- `Alice Legacy` — old Alice project root
- `Hermes Skills` — `%LOCALAPPDATA%\hermes\skills\alice`

## Data

| Method | Endpoint | Notes |
|:--|:--|:--|
| GET | `/api/tree` | Returns `{files, tracked, modified, workspaces, session}` |
| GET | `/api/read/<path>` | Read file content (memory-tracked first, then disk) |
| GET | `/api/diff/<path>` | Returns `{disk_content, history}` for diff comparison |
| GET | `/api/repl_logs` | Returns REPL terminal log entries |
| POST | `/api/repl_logs_push` | `{"msg":"..."}` — push log entry |
| POST | `/api/save` | `{"path":"...","content":"..."}` — save file to disk |
| GET | `/api/clear_notify/<path>` | Clear modification flag for path (or "all") |

## Self Review

| Method | Endpoint | Notes |
|:--|:--|:--|
| POST | `/api/self_review` | Scans: tracked files → workspaces → legacy legacy dirs |

Returns:
```json
{
  "status": "ok",
  "total": 2,
  "high": [...], "medium": [...], "low": [...],
  "files_scanned": 73,
  "structural_checks": true,
  "phase0": { "summary": {...}, "issues": [...] },
  "phase4": { "summary": {...}, "issues": [...] }
}
```

## Watchdog Behavior (v5.2+)

- Scans all workspaces + BASE_DIR every 5 seconds
- **New files** → flagged as `"new_file"` in modified
- **Content changes** → flagged as `"modified"` in modified
- **Syntax errors** → flagged as `"syntax_error: Line N"` in modified
- Auto-saves history version on each detected change (max 10 per file)
