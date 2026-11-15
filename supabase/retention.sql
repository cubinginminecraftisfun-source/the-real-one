-- REQUIRED before real customers: enable Supabase Cron (pg_cron) in the dashboard.
-- Then run this ONCE in SQL Editor. No external API key is used.
-- The schedule is UTC: 18:10 UTC = 03:10 Korea the next day.
-- Deletes booking personal data 30 days after the appointment, irrespective of status.
-- If you change this policy, also change the Korean consent notice in app.py.
select cron.schedule(
  'salon-daily-retention',
  '10 18 * * *',
  $job$
  delete from salon_private.bookings where starts_at < now()-interval '30 days';
  delete from salon_private.sessions where expires_at <= now();
  delete from salon_private.attempts where started_at < now()-interval '2 days';
  delete from salon_private.prices where day < (now() at time zone 'Asia/Seoul')::date-30;
  delete from salon_private.rules where end_date < (now() at time zone 'Asia/Seoul')::date-30;
  $job$
);
-- Verify job status in Integrations > Cron / Database > Cron (wording may vary).
-- Or run: select jobname, schedule, active from cron.job where jobname='salon-daily-retention';
-- Do not schedule it repeatedly. To remove: select cron.unschedule('salon-daily-retention');
