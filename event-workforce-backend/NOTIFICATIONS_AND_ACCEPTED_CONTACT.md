# Gigscart Notifications and Accepted-Application Contact

## Supabase migration
Run `015_notifications.sql` in the SQL editor of the Supabase project used by this backend. It creates the private `notifications` table and service-role-only access.

## Backend behaviour
- When an employer changes an application status to `selected`, the worker receives an `application_accepted` notification.
- When a worker connection request is accepted (including the reciprocal-request shortcut), the requester receives a `connection_request_accepted` notification.
- `GET /applications/mine` includes `employer_contact` only when that worker's application status is `selected`. Contact data comes from the employer's shared profile phone and Supabase Auth email. Pending, shortlisted, rejected and withdrawn applications return `employer_contact: null`.
- Notifications endpoints:
  - `GET /notifications?limit=30&offset=0` — newest first, includes `unread_count`.
  - `POST /notifications/{notification_id}/read` — mark one notification read.
  - `POST /notifications/read-all` — mark all current user's notifications read.
- Every notification read/update is scoped to the authenticated user's ID. The notifications table has RLS enabled and no client-role grants; all access goes through authenticated backend routes using the service-role client.

## Flutter behaviour
- Worker Home has a notification bell beside the chat icon. A red dot indicates unread notifications.
- The bell opens the notifications inbox; tapping an unread notification marks it read.
- Accepted applications show a **View employer contact** button on My Applications. The contact sheet displays the employer mobile and email and offers phone/email launch actions.
- The worker-facing status label for backend status `selected` remains **Accepted**.

## Notes
This is an in-app notification inbox. It does not send operating-system push notifications; Firebase Cloud Messaging/APNs device-token delivery is a separate integration.
