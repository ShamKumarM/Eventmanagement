-- Role selection RPC migration for the hosted Supabase project.
-- Run this in the Supabase SQL Editor after confirming profiles.role_selected exists.
-- This function is intended to be called only by the FastAPI backend using
-- SUPABASE_SERVICE_KEY. It atomically updates profiles and creates the matching
-- role-specific profile, preventing duplicate/concurrent role selection.

CREATE OR REPLACE FUNCTION public.select_initial_role(
    p_user_id uuid,
    p_role text,
    p_organisation_name text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_role_selected boolean;
BEGIN
    IF p_role NOT IN ('worker', 'employer') THEN
        RAISE EXCEPTION 'invalid_role';
    END IF;

    IF p_role = 'employer'
       AND (p_organisation_name IS NULL OR length(trim(p_organisation_name)) < 2) THEN
        RAISE EXCEPTION 'organisation_name_required';
    END IF;

    IF p_role = 'worker' AND p_organisation_name IS NOT NULL THEN
        RAISE EXCEPTION 'organisation_name_not_allowed_for_worker';
    END IF;

    SELECT role_selected
      INTO v_role_selected
      FROM public.profiles
     WHERE id = p_user_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'profile_not_found';
    END IF;

    IF v_role_selected THEN
        RAISE EXCEPTION 'role_already_selected';
    END IF;

    UPDATE public.profiles
       SET role = p_role,
           role_selected = TRUE,
           updated_at = now()
     WHERE id = p_user_id;

    IF p_role = 'worker' THEN
        INSERT INTO public.worker_profiles (user_id)
        VALUES (p_user_id)
        ON CONFLICT (user_id) DO NOTHING;
    ELSE
        INSERT INTO public.employer_profiles (user_id, organisation_name)
        VALUES (p_user_id, trim(p_organisation_name))
        ON CONFLICT (user_id) DO NOTHING;
    END IF;

    RETURN jsonb_build_object(
        'user_id', p_user_id,
        'role', p_role,
        'role_selected', TRUE
    );
END;
$function$;

-- Do not expose this privileged function to browser/user roles.
REVOKE ALL ON FUNCTION public.select_initial_role(uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.select_initial_role(uuid, text, text) FROM anon;
REVOKE ALL ON FUNCTION public.select_initial_role(uuid, text, text) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.select_initial_role(uuid, text, text) TO service_role;
