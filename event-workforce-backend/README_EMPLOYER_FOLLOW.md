# Employer discovery, follows, and contact access

Apply `010_employer_follow_and_contact_access.sql` after the profile, employer profile, and verification schema is installed. The migration creates follows, contact requests, a follower-count view, and database guards for account roles. These tables have RLS enabled and are accessed by FastAPI with the server-only service-role key.

All routes require a bearer token. Employer discovery requires a user who has completed role selection; follow and contact-request actions are worker-only; incoming requests, accept/reject/revoke, and follower lists are employer-only.

| Method | Route | Purpose |
|---|---|---|
| GET | `/employer-follow/employers?search=<name>&verified_only=false` | Search public employer cards |
| GET | `/employer-follow/employers/most-followed` | Rank employers by unique follower count |
| GET | `/employer-follow/employers/{employer_id}` | View a public employer card |
| POST | `/employer-follow/employers/{employer_id}/follow` | Follow an employer |
| DELETE | `/employer-follow/employers/{employer_id}/follow` | Unfollow; pending contact requests are cancelled |
| GET | `/employer-follow/employers/me/following` | List employers the worker follows |
| GET | `/employer-follow/employers/me/followers` | Employer's follower list; worker names/photos only |
| POST | `/employer-follow/employers/{employer_id}/contact-requests` | Ask a followed employer to share contact details |
| GET | `/employer-follow/contact-requests/mine` | Check the worker's request statuses |
| POST | `/employer-follow/contact-requests/{request_id}/cancel` | Cancel a pending request |
| GET | `/employer-follow/contact-requests/incoming` | Employer's incoming requests |
| POST | `/employer-follow/contact-requests/{request_id}/respond` | Employer accepts, rejects, or revokes access |
| GET | `/employer-follow/employers/{employer_id}/contact` | Read contact details after approval |

Contact request body (optional):

```json
{ "message": "I am interested in working with your team." }
```

Employer response body:

```json
{ "action": "accept" }
```

`action` may be `accept`, `reject`, or `revoke`. Following an employer does not reveal private details. Only an accepted request grants the worker access to the employer's phone, account email, contact person, and business address. A revoked request removes that access. Verification status comes only from admin review; follower count never grants or implies verification.
