-- OPTIONAL DATABASE SMOKE TEST: run AFTER setup.sql in a NEW EMPTY TEST project only.
-- Uses the INITIAL admin password 1111. Never run against your live customer database.
-- Everything below is rolled back, including the temporary admin password change.
-- Successful result: NOTICE 'PASS: database smoke checks completed' and no ERROR.
-- If your SQL editor stops on an error, run ROLLBACK; before trying anything else.
begin;
do $$
declare
 admin_result jsonb;
 customer_result jsonb;
 customer_two jsonb;
 result jsonb;
 cal jsonb;
 bookings jsonb;
 owner_token text;
 admin_token text;
 test_day date := (now() at time zone 'Asia/Seoul')::date + 2;
 test_slot timestamptz;
 booking_id text;
begin
 if exists(select 1 from salon_private.bookings) then
   raise exception 'Use an EMPTY TEST project, not a live booking database.';
 end if;
 if has_function_privilege('anon','public.salon_api(text,jsonb,text)','execute')
 or has_function_privilege('authenticated','public.salon_api(text,jsonb,text)','execute') then
   raise exception 'SECURITY: public role can execute RPC';
 end if;
 admin_result := public.salon_api('login',jsonb_build_object('client',repeat('a',64),'code','1111'),'');
 if admin_result->>'kind' is distinct from 'admin' then
   raise exception 'Admin initial login failed: %',admin_result;
 end if;
 admin_token := admin_result->>'token';
 result := public.salon_api('calendar',jsonb_build_object('from',test_day),admin_token);
 if result ? 'error' then raise exception 'Admin is still blocked by forced password change: %',result; end if;
 result := public.salon_api('change_password',jsonb_build_object('old','1111','new','Test-Only-Passphrase-2030'),admin_token);
 if result->>'ok' is distinct from 'true' then raise exception 'Password change failed: %',result; end if;
 customer_result := public.salon_api('create_session',jsonb_build_object('client',repeat('b',64)),'');
 customer_two := public.salon_api('create_session',jsonb_build_object('client',repeat('c',64)),'');
 owner_token := customer_result->>'token';
 if owner_token is null or length(customer_result->>'code')<>2 then
   raise exception 'Customer session creation failed';
 end if;
 if customer_result ? 'pin' then raise exception 'V2 must not return a recovery PIN'; end if;
 if customer_result->>'code'=customer_two->>'code' then raise exception 'Code collision'; end if;
 result := public.salon_api('save_rule',jsonb_build_object('start_date',test_day,'end_date',test_day,
   'weekdays',jsonb_build_array(extract(isodow from test_day)::int),'start_min',600,'end_min',630,
   'state','available','repeats',false),admin_token);
 if result->>'ok' is distinct from 'true' then raise exception 'Rule failed: %',result; end if;
 test_slot := (test_day::timestamp + interval '10 hours') at time zone 'Asia/Seoul';
 result := public.salon_api('book',jsonb_build_object('starts_at',test_slot,'ends_at',test_slot+interval '45 minutes','name','테스트 고객',
   'comment','PRIVATE_TEST_COMMENT','service_label','남성 커트','expected_price',15000,'consent',true),owner_token);
 if result->>'state' is distinct from 'confirmed' then raise exception 'Booking failed: %',result; end if;
 result := public.salon_api('book',jsonb_build_object('starts_at',test_slot+interval '5 minutes','ends_at',test_slot+interval '35 minutes','name','다른 고객',
   'comment','','service_label','남성 커트','expected_price',15000,'consent',true),customer_two->>'token');
 if not (result ? 'error') then raise exception 'Duplicate booking was allowed'; end if;
 cal := public.salon_api('calendar',jsonb_build_object('from',test_day),customer_two->>'token');
 if cal::text like '%PRIVATE_TEST_COMMENT%' or cal::text like '%테스트 고객%' then
   raise exception 'Personal data leaked in calendar';
 end if;
 bookings := public.salon_api('my_bookings','{}'::jsonb,owner_token);
 booking_id := bookings->'bookings'->0->>'id';
 if booking_id is null then raise exception 'Owner cannot retrieve booking'; end if;
 result := public.salon_api('cancel',jsonb_build_object('id',booking_id),customer_two->>'token');
 if not (result ? 'error') then raise exception 'Other customer could cancel owner booking'; end if;
 result := public.salon_api('admin_bookings',jsonb_build_object('from',test_day),customer_two->>'token');
 if not (result ? 'error') then raise exception 'Customer could read admin bookings'; end if;
 result := public.salon_api('cancel',jsonb_build_object('id',booking_id),owner_token);
 if result->>'ok' is distinct from 'true' then raise exception 'Owner cancellation failed'; end if;
 result := public.salon_api('login',jsonb_build_object('client',repeat('b',64),
   'code',customer_result->>'code'),'');
 if result->>'kind' is distinct from 'customer' then raise exception 'Code recovery failed'; end if;
 result := public.salon_api('session','{}'::jsonb,owner_token);
 if result->>'expired' is distinct from 'true' then raise exception 'Old device was not invalidated'; end if;
 -- Weekly recurring price and a one-date exception must be independent.
 result := public.salon_api('save_prices',jsonb_build_object('day',test_day,'repeats',true,
   'frequency','weekly','menu',jsonb_build_array(jsonb_build_object('label','테스트 커트','price',17000))),admin_token);
 if result->>'ok' is distinct from 'true' then raise exception 'Recurring price save failed: %',result; end if;
 result := public.salon_api('save_prices',jsonb_build_object('day',test_day,'repeats',false,
   'menu',jsonb_build_array(jsonb_build_object('label','특별 커트','price',19000))),admin_token);
 result := public.salon_api('prices',jsonb_build_object('day',test_day),admin_token);
 if (result->'menu'->0->>'price')::int is distinct from 19000 then raise exception 'Date override failed'; end if;
 result := public.salon_api('prices',jsonb_build_object('day',test_day+7),admin_token);
 if (result->'menu'->0->>'price')::int is distinct from 17000 then raise exception 'Weekly price changed by one-date override'; end if;
 raise notice 'PASS: database smoke checks completed (transaction will roll back)';
end;
$$;
rollback;
