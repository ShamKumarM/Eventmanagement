# Worker connections and chat

Apply `009_worker_social.sql` after the existing `profiles` and `jobs` tables are installed. It creates worker friend requests, accepted connections, direct chats, chat messages, and the request-response RPC. Keep using the service-role key only on the FastAPI server; the migration enables RLS without adding client policies.

All routes require a bearer token for a worker account with `role_selected = true`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/social/workers?search=<name>&limit=25&offset=0` | Find workers by name, without exposing contact details |
| POST | `/social/friend-requests` | Send a request with `{ "recipient_id": "<worker UUID>" }` |
| GET | `/social/friend-requests?folder=incoming` | List pending incoming requests; `folder=outgoing` lists sent requests |
| POST | `/social/friend-requests/{request_id}/respond` | Accept/reject an incoming request or cancel your outgoing request |
| GET | `/social/friends` | List accepted worker connections |
| DELETE | `/social/friends/{worker_id}` | Remove a connection; the chat history remains stored |
| GET | `/social/chats?limit=25&offset=0` | List direct chats with accepted connections |
| GET | `/social/chats/{worker_id}/messages?limit=50&before=<ISO timestamp>` | Read a chat, oldest first within the selected page |
| POST | `/social/chats/{worker_id}/messages` | Send text or share an active job |

Text message:

```json
{ "body": "Are you available for this event?" }
```

Share a job card:

```json
{ "job_id": "<job UUID>" }
```

Only accepted connections can read or send chat messages. Job sharing is limited to open jobs whose event date is today or later. The message keeps a safe job snapshot, so the shared card can still be displayed if the job is later removed.

## Mobile integration

This checkout contains the FastAPI backend but not the Flutter source tree. The API is registered in `app/main.py`; the mobile screens and navigation still need to be added in the Flutter project.
