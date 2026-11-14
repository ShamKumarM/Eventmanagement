# AbiHub fixes — 14 Nov 2026

## Apply database migration
Run `013_tamil_nadu_localities.sql` in Supabase SQL Editor. It removes legacy placeholder areas whose name equals their district and inserts curated locality options under the correct Tamil Nadu district. This is an initial curated list, not a complete official gazetteer of every village/ward.

## Backend
No Python endpoint contract changed. The existing `/locations/states`, `/locations/districts?state_id=...`, and `/locations/areas?district_id=...` endpoints already query the correct `location_*` tables and return numeric IDs.

## Flutter
- Gate now reads canonical `/profile/me` so employer role-specific fields are present when checking mandatory completion.
- Contact person is optional for employer completion, consistent with profile form/backend.
- After mandatory save, the app fetches `/profile/me` and navigates directly to `/app`, rather than routing back through a potentially stale gate response.
- Saved legacy area values that equal the district name are no longer inserted as fake area options.
- Social directory loading is resilient: each directory/requests/chats request fails independently; one temporary API failure no longer replaces the whole Community page with the generic unavailable screen. Existing directory data is retained during transient failures.
