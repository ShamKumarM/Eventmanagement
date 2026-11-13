# Socialism module (unified worker + employer social features)

This replaces the separate `/social` and `/employer-follow` APIs with one `/socialism` API.

## Role rules
- Workers can follow/unfollow other workers.
- Worker-to-worker chat is available only after both workers follow each other.
- Workers can follow/unfollow employers and view public employer cards and follower counts.
- Employers cannot follow workers or employers.
- Employers cannot send or receive messages through this module.
- There is no employer contact-request or private-contact-sharing feature in this module.
- Employer verification remains admin-controlled and is not affected by follower counts.

## Migration
Apply `011_socialism_module.sql` in Supabase SQL Editor after `009_worker_social.sql` and `010_employer_follow_and_contact_access.sql`.
It migrates accepted worker friendships into mutual follows, retains existing chat rows/messages and employer follows, then removes the retired friend-request/friendship and employer-contact-request tables.

## Routes
All routes require a bearer token and completed role selection as appropriate.

### Worker directory / worker follows (worker only)
| Method | Route | Purpose |
|---|---|---|
| GET | `/socialism/workers?search=<name>&limit=25&offset=0` | Search workers |
| POST | `/socialism/workers/{worker_id}/follow` | Follow a worker |
| DELETE | `/socialism/workers/{worker_id}/follow` | Unfollow a worker |
| GET | `/socialism/workers/me/following` | Workers you follow |
| GET | `/socialism/workers/me/followers` | Workers following you |

### Employer discovery / follows
| Method | Route | Purpose |
|---|---|---|
| GET | `/socialism/employers?search=<name>&verified_only=false` | Browse/search public employer cards |
| GET | `/socialism/employers/most-followed` | Employers ranked by follower count |
| GET | `/socialism/employers/{employer_id}` | Public employer profile |
| POST | `/socialism/employers/{employer_id}/follow` | Worker follows an employer |
| DELETE | `/socialism/employers/{employer_id}/follow` | Worker unfollows an employer |
| GET | `/socialism/employers/me/following` | Employers a worker follows |
| GET | `/socialism/employers/me/followers` | Employer views worker followers |

### Worker chat (worker only; mutual follow required)
| Method | Route | Purpose |
|---|---|---|
| GET | `/socialism/chats` | List chats |
| GET | `/socialism/chats/{worker_id}/messages` | Read messages |
| POST | `/socialism/chats/{worker_id}/messages` | Send text or share an active job |

Text message:
```json
{ "body": "Are you available for this event?" }
```

Share an active job:
```json
{ "job_id": "<job UUID>" }
```

A worker following another worker does not by itself enable chat. Both workers must follow each other. Unfollowing either direction immediately blocks subsequent chat reads and sends; existing chat history remains stored.
