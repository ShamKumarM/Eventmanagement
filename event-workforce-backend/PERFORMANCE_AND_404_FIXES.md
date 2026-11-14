# AbiHub backend performance and route compatibility update

## Changes in this update

1. Authentication now reuses the module-level Supabase client for token validation instead of creating a new client for every protected request. The access token is still explicitly validated on every request; no token-result cache was introduced.
2. Socialism worker directory now batches follow and pending-request lookups rather than issuing mutual-follow checks per worker.
3. Worker following/follower response relationship flags are batched.
4. Chat list reads latest messages from `worker_chat_latest_messages` in one query instead of one message query per chat.
5. Added root-level legacy aliases for:
   - `GET /employers/most-followed`
   - `GET /employers/me/following`
   - `GET /chats`
   Canonical routes remain under `/socialism/...`.
6. Added SQL migration `014_performance_indexes_and_chat_latest.sql` for supporting indexes and the latest-message view.

## Deployment

1. Extract this ZIP over your existing backend working copy (keep your `.env` file private; this archive does not include it).
2. In Supabase SQL Editor, run `014_performance_indexes_and_chat_latest.sql` once.
3. Commit and push to your deployment branch.
4. Wait for Render to deploy successfully.
5. Retest with Postman.

## Canonical Postman paths

- `GET {{base_url}}/socialism/employers/most-followed`
- `GET {{base_url}}/socialism/employers/me/following`
- `GET {{base_url}}/socialism/chats`

The legacy root paths are retained for older clients, but use canonical paths in new requests.

## Important measurement note

The ZIP has been syntax-checked, but it has not been benchmarked against your live Render/Supabase project. Compare response times after deployment. Render cold starts, Supabase region/network latency, database load, and query plans can still contribute to latency.

## Database schema note

The schema text supplied for review reports `job_categories.id` as `bigint` while `jobs.category_id` and `job_category_roles.category_id` are `integer`. PostgreSQL normally cannot create a foreign key between those different types. Your live database must be checked before any category-column type migration; this update deliberately does not alter those columns.
