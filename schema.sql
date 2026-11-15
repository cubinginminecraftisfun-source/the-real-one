-- Run ONCE in Supabase > SQL Editor on a NEW project.
-- Application uses a server-only PostgreSQL connection, not the browser Data API.
create extension if not exists btree_gist;

create table if not exists public.salon_settings (
 id integer primary key check (id=1), password_hash text not null,
 must_change boolean not null default true, auth_version integer not null default 1
);
create table if not exists public.salon_sessions (
 id uuid primary key, code text not null check (code ~ '^[A-Z0-9]{2}$'),
 secret_hash text not null, created_at timestamptz not null default now(), expires_at timestamptz not null
);
-- Only the current allocation of each short reference is stored here.
create table if not exists public.salon_codes (
 code text primary key, session_id uuid not null references public.salon_sessions(id), expires_at timestamptz not null
);
create table if not exists public.salon_admin_sessions (
 token_hash text primary key, auth_version integer not null, expires_at timestamptz not null
);
create table if not exists public.salon_login_limits (
 bucket text primary key, failures integer not null default 0,
 window_start timestamptz not null default now(), blocked_until timestamptz
);
create table if not exists public.salon_rules (
 id bigint generated always as identity primary key,
 start_date date not null, end_date date,
 weekdays integer[] not null, start_minute integer not null, end_minute integer not null,
 status text not null check (status in ('available','maybe','unavailable')),
 check (end_date is null or end_date >= start_date),
 check (start_minute >= 0 and end_minute <= 1440 and end_minute > start_minute),
 check (start_minute % 30 = 0 and end_minute % 30 = 0)
);
create table if not exists public.salon_prices (
 day date primary key, items jsonb not null check (jsonb_typeof(items)='array')
);
create table if not exists public.salon_bookings (
 id uuid primary key, session_id uuid not null references public.salon_sessions(id),
 starts_at timestamptz not null, ends_at timestamptz not null,
 customer_name text not null, phone text not null, comment text not null default '',
 service text not null, price integer not null check(price>=0),
 state text not null default 'confirmed' check (state in ('confirmed','cancelled')),
 created_at timestamptz not null default now(), check(ends_at>starts_at),
 constraint salon_no_double_booking exclude using gist
 (tstzrange(starts_at, ends_at, '[)') with &&) where (state = 'confirmed')
);
create index if not exists salon_bookings_session on public.salon_bookings(session_id);
create index if not exists salon_bookings_time on public.salon_bookings(starts_at);

-- Defense in depth: deny all browser/anonymous Data API access.
-- The server connection (postgres owner) performs authorization in db.py.
do $$
declare t text;
begin
 foreach t in array array['salon_settings','salon_sessions','salon_codes','salon_admin_sessions',
 'salon_login_limits','salon_rules','salon_prices','salon_bookings'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on table public.%I from anon, authenticated',t);
 end loop;
end $$;
-- No public read policies: even the public calendar is sanitized by the server.
