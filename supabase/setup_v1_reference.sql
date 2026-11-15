-- Run ONCE in Supabase SQL Editor, on a NEW project. Never put real secrets in GitHub.
-- Server-only RPC: public/anon/authenticated users get no access to salon data or RPC.
create extension if not exists pgcrypto with schema extensions;
create schema if not exists salon_private;
revoke all on schema salon_private from public, anon, authenticated;

create table salon_private.settings (
 id boolean primary key default true check(id),
 password_hash text not null,
 must_change boolean not null default true,
 base_menu jsonb not null default '[{"label":"남성 커트","price":15000},{"label":"여성 커트","price":20000}]'
);
insert into salon_private.settings(id,password_hash)
values(true,extensions.crypt(encode(extensions.digest('1111','sha256'),'hex'),extensions.gen_salt('bf',10)));

create table salon_private.sessions (
 token_hash text primary key,
 kind text not null check(kind in ('customer','admin')),
 code char(2) unique,
 pin_hash text,
 created_at timestamptz not null default now(),
 expires_at timestamptz not null
);
create table salon_private.attempts (
 client_hash text primary key,
 started_at timestamptz not null default now(),
 failures integer not null default 0,
 creations integer not null default 0
);
create table salon_private.rules (
 id bigint generated always as identity primary key,
 start_date date not null,
 end_date date,
 weekdays integer[] not null,
 start_min integer not null check(start_min >= 0 and start_min < 1440),
 end_min integer not null check(end_min > start_min and end_min <= 1440),
 state text not null check(state in ('available','tentative','unavailable')),
 repeats boolean not null default false,
 check(end_date is null or end_date >= start_date)
);
create table salon_private.prices (
 day date primary key,
 menu jsonb not null
);
create table salon_private.bookings (
 id uuid primary key default gen_random_uuid(),
 customer_hash text not null,
 starts_at timestamptz not null,
 state text not null check(state in ('confirmed','pending','cancelled','rejected')),
 name text not null,
 comment text not null default '',
 service_label text not null,
 price integer not null check(price >= 0),
 created_at timestamptz not null default now()
);
create unique index one_active_booking_per_slot on salon_private.bookings(starts_at)
where state in ('confirmed','pending');
create index booking_owner on salon_private.bookings(customer_hash);
create index booking_calendar on salon_private.bookings(starts_at);

alter table salon_private.settings enable row level security;
alter table salon_private.sessions enable row level security;
alter table salon_private.attempts enable row level security;
alter table salon_private.rules enable row level security;
alter table salon_private.prices enable row level security;
alter table salon_private.bookings enable row level security;
revoke all on all tables in schema salon_private from public, anon, authenticated;
revoke all on all sequences in schema salon_private from public, anon, authenticated;

-- One RPC keeps authorization, time rules and booking transactions together.
-- All schedule-changing operations take the same transaction advisory lock.
create or replace function public.salon_api(action text, payload jsonb default '{}'::jsonb, token text default '')
returns jsonb language plpgsql security definer
set search_path = pg_catalog, salon_private, extensions
as $$
declare
 s salon_private.sessions%rowtype;
 cfg salon_private.settings%rowtype;
 a salon_private.attempts%rowtype;
 b salon_private.bookings%rowtype;
 v_token text; v_hash text; v_code text; v_pin text;
 v_client text; v_result jsonb; v_menu jsonb; v_item jsonb;
 v_day date; v_from date; v_until date; v_now date;
 v_slot timestamptz; v_min integer; v_state text; v_count integer;
 v_open integer; v_close integer; v_horizon integer;
 v_rule salon_private.rules%rowtype;
 v_name text; v_comment text;
begin
 -- Single-chair defaults; see README before changing hours/horizon.
 -- Serialize reads too: session recovery cannot race booking ownership transfer.
 perform pg_advisory_xact_lock(820150001);
 v_open := 600;       -- 10:00 (minutes after midnight, Korea)
 v_close := 1200;     -- 20:00; last 30-minute booking at 19:30
 v_horizon := 90;     -- book up to 90 days in advance
 v_now := (now() at time zone 'Asia/Seoul')::date;
 select * into cfg from salon_private.settings where id;
 v_hash := encode(extensions.digest(coalesce(token,''),'sha256'),'hex');

 if action in ('create_session','login') then
   -- Auth/code generation share a lock to prevent collision races and lost counters.
   perform pg_advisory_xact_lock(820150001);
   delete from salon_private.sessions where expires_at <= now();
   delete from salon_private.attempts where started_at < now()-interval '2 days';
   v_client := coalesce(payload->>'client','');
   if length(v_client) <> 64 then return jsonb_build_object('error','접속 정보를 확인할 수 없습니다. 새로고침해 주세요.'); end if;
   insert into salon_private.attempts(client_hash) values(v_client) on conflict do nothing;
   select * into a from salon_private.attempts where client_hash=v_client;
   if a.started_at < now()-interval '15 minutes' then
     update salon_private.attempts set started_at=now(),failures=0,creations=0 where client_hash=v_client returning * into a;
   end if;
   if a.failures >= 8 then return jsonb_build_object('error','로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.'); end if;
   v_token := encode(extensions.gen_random_bytes(32),'hex');
   if action='create_session' then
     if a.creations >= 5 then return jsonb_build_object('error','코드 생성은 15분에 5번까지 가능합니다. 기존 코드를 이용해 주세요.'); end if;
     if (select count(*) from salon_private.sessions where kind='customer') >= 1296 then
       return jsonb_build_object('error','오늘의 접속 코드가 모두 사용 중입니다. 매장에 문의해 주세요.');
     end if;
     -- Choose uniformly from AVAILABLE codes, so a full namespace cannot loop forever.
     select chr(x)||chr(y) into v_code
     from unnest(string_to_array('0,1,2,3,4,5,6,7,8,9,A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z',',')) xx(t)
     cross join lateral (select ascii(xx.t) x) q
     cross join unnest(string_to_array('0,1,2,3,4,5,6,7,8,9,A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z',',')) yy(t)
     cross join lateral (select ascii(yy.t) y) r
     where not exists(select 1 from salon_private.sessions ss where ss.code=chr(x)||chr(y))
     order by extensions.gen_random_bytes(8) limit 1;
     v_pin := lpad(((get_byte(extensions.gen_random_bytes(4),0)*65536 + get_byte(extensions.gen_random_bytes(4),1)*256 + get_byte(extensions.gen_random_bytes(4),2)) % 1000000)::text,6,'0');
     insert into salon_private.sessions(token_hash,kind,code,pin_hash,expires_at)
     values(encode(extensions.digest(v_token,'sha256'),'hex'),'customer',v_code,extensions.crypt(v_pin,extensions.gen_salt('bf',8)),now()+interval '24 hours');
     update salon_private.attempts set creations=creations+1 where client_hash=v_client;
     return jsonb_build_object('token',v_token,'kind','customer','code',v_code,'pin',v_pin,'expires_at',now()+interval '24 hours');
   end if;
   v_code := upper(trim(payload->>'code'));
   if length(trim(payload->>'code'))=2 then
     select * into s from salon_private.sessions where code=v_code and kind='customer' and expires_at>now();
     if found and extensions.crypt(coalesce(payload->>'pin',''),s.pin_hash)=s.pin_hash then
       -- The high-entropy token is stable for 24 hours; never return it on code alone.
       -- Store encrypted recovery of token? No: instead return a new session token and
       -- transfer ownership to it, invalidating the old device (documented behavior).
       update salon_private.bookings set customer_hash=encode(extensions.digest(v_token,'sha256'),'hex') where customer_hash=s.token_hash;
       update salon_private.sessions set token_hash=encode(extensions.digest(v_token,'sha256'),'hex') where token_hash=s.token_hash;
       return jsonb_build_object('token',v_token,'kind','customer','code',s.code,'expires_at',s.expires_at);
     end if;
   elsif extensions.crypt(encode(extensions.digest(coalesce(payload->>'code',''),'sha256'),'hex'),cfg.password_hash)=cfg.password_hash then
     insert into salon_private.sessions(token_hash,kind,expires_at)
     values(encode(extensions.digest(v_token,'sha256'),'hex'),'admin',now()+interval '8 hours');
     return jsonb_build_object('token',v_token,'kind','admin','must_change',cfg.must_change,'expires_at',now()+interval '8 hours');
   end if;
   update salon_private.attempts set failures=failures+1 where client_hash=v_client;
   return jsonb_build_object('error','입력 정보가 일치하지 않거나 코드가 만료되었습니다.');
 end if;

 select * into s from salon_private.sessions where token_hash=v_hash and expires_at>now();
 if not found then return jsonb_build_object('error','접속이 만료되었습니다. 시작 화면에서 다시 접속해 주세요.','expired',true); end if;
 if action='session' then
   return jsonb_build_object('kind',s.kind,'code',s.code,'expires_at',s.expires_at,'must_change',case when s.kind='admin' then cfg.must_change else false end);
 end if;
 if action='logout' then
   if s.kind='admin' then delete from salon_private.sessions where token_hash=v_hash; end if;
   return jsonb_build_object('ok',true);
 end if;
 if action='change_password' and s.kind='admin' then
   if extensions.crypt(encode(extensions.digest(coalesce(payload->>'old',''),'sha256'),'hex'),cfg.password_hash)<>cfg.password_hash then
     return jsonb_build_object('error','현재 비밀번호가 맞지 않습니다.'); end if;
   if length(coalesce(payload->>'new',''))<8 or length(payload->>'new')>64 then
     return jsonb_build_object('error','새 비밀번호는 8~64자로 입력해 주세요.'); end if;
   update salon_private.settings set password_hash=extensions.crypt(encode(extensions.digest(payload->>'new','sha256'),'hex'),extensions.gen_salt('bf',10)),must_change=false where id;
   delete from salon_private.sessions where kind='admin' and token_hash<>v_hash;
   return jsonb_build_object('ok',true);
 end if;
 if s.kind='admin' and cfg.must_change then return jsonb_build_object('error','먼저 기본 관리자 비밀번호를 변경해 주세요.'); end if;

 if action='calendar' then
   v_from := (payload->>'from')::date;
   v_until := v_from+6;
   if v_from < v_now-7 or v_from > v_now+v_horizon then return jsonb_build_object('error','달력은 현재부터 90일 범위에서 확인해 주세요.'); end if;
   select jsonb_build_object(
     'rules',coalesce((select jsonb_agg(to_jsonb(r) order by r.id) from salon_private.rules r where r.start_date<=v_until and (r.end_date is null or r.end_date>=v_from)),'[]'::jsonb),
     'bookings',coalesce((select jsonb_agg(jsonb_build_object('starts_at',bb.starts_at,'state',bb.state)) from salon_private.bookings bb where bb.starts_at >= v_from::timestamp at time zone 'Asia/Seoul' and bb.starts_at < (v_until+1)::timestamp at time zone 'Asia/Seoul' and bb.state in ('confirmed','pending')),'[]'::jsonb),
     'open_min',v_open,'close_min',v_close,'server_now',now()
   ) into v_result;
   return v_result;
 end if;
 if action='prices' then
   v_day := (payload->>'day')::date;
   select menu into v_menu from salon_private.prices where day=v_day;
   return jsonb_build_object('menu',coalesce(v_menu,cfg.base_menu),'custom',v_menu is not null);
 end if;
 if action='my_bookings' then
   select coalesce(jsonb_agg(to_jsonb(bb) - 'customer_hash' order by bb.starts_at),'[]'::jsonb) into v_result from salon_private.bookings bb where bb.customer_hash=v_hash;
   return jsonb_build_object('bookings',v_result);
 end if;
 if action='admin_bookings' and s.kind='admin' then
   v_from := (payload->>'from')::date;
   select coalesce(jsonb_agg(to_jsonb(bb) - 'customer_hash' order by bb.starts_at),'[]'::jsonb) into v_result from salon_private.bookings bb where bb.starts_at >= v_from::timestamp at time zone 'Asia/Seoul' and bb.starts_at < (v_from+7)::timestamp at time zone 'Asia/Seoul';
   return jsonb_build_object('bookings',v_result);
 end if;

 -- All mutation paths below serialize. Unique index is a second safety net.
 perform pg_advisory_xact_lock(820150001);
 if action='book' and s.kind='customer' then
   v_slot := (payload->>'starts_at')::timestamptz;
   v_day := (v_slot at time zone 'Asia/Seoul')::date;
   v_min := extract(hour from v_slot at time zone 'Asia/Seoul')::int*60 + extract(minute from v_slot at time zone 'Asia/Seoul')::int;
   if v_slot <= now() or v_day>v_now+v_horizon or v_min<v_open or v_min+30>v_close or v_min%30<>0 or extract(second from v_slot)<>0 then
     return jsonb_build_object('error','예약할 수 없는 시간입니다.'); end if;
   if (select count(*) from salon_private.bookings where customer_hash=v_hash and state in ('confirmed','pending') and starts_at>now())>=3 then
     return jsonb_build_object('error','동시에 예약할 수 있는 일정은 최대 3개입니다.'); end if;
   v_state := 'available';
   select * into v_rule from salon_private.rules r
   where r.start_date<=v_day and (r.end_date is null or r.end_date>=v_day)
   and extract(isodow from v_day)::int=any(r.weekdays) and r.start_min<=v_min and r.end_min>v_min
   order by r.repeats asc,r.id desc limit 1;
   if found then v_state:=v_rule.state; end if;
   if v_state='unavailable' then return jsonb_build_object('error','방금 예약 불가로 변경되었습니다. 다른 시간을 선택해 주세요.'); end if;
   if exists(select 1 from salon_private.bookings where starts_at=v_slot and state in ('confirmed','pending')) then
     return jsonb_build_object('error','다른 고객님이 먼저 예약했습니다. 다른 시간을 선택해 주세요.'); end if;
   v_name := trim(coalesce(payload->>'name','')); v_comment:=trim(coalesce(payload->>'comment',''));
   if length(v_name)<1 or length(v_name)>30 or length(v_comment)>300 then return jsonb_build_object('error','이름은 1~30자, 요청사항은 300자 이내로 입력해 주세요.'); end if;
   if not coalesce((payload->>'consent')::boolean,false) then return jsonb_build_object('error','예약 정보 수집 안내에 동의해 주세요.'); end if;
   select menu into v_menu from salon_private.prices where day=v_day;
   v_menu:=coalesce(v_menu,cfg.base_menu);
   select item into v_item from jsonb_array_elements(v_menu) item where item->>'label'=payload->>'service_label' limit 1;
   if v_item is null or (v_item->>'price')::int <> (payload->>'expected_price')::int then return jsonb_build_object('error','가격표가 변경되었습니다. 창을 닫고 가격을 다시 확인해 주세요.'); end if;
   insert into salon_private.bookings(customer_hash,starts_at,state,name,comment,service_label,price)
   values(v_hash,v_slot,case when v_state='tentative' then 'pending' else 'confirmed' end,v_name,v_comment,v_item->>'label',(v_item->>'price')::int) returning * into b;
   return jsonb_build_object('ok',true,'state',b.state);
 end if;
 if action='cancel' then
   select * into b from salon_private.bookings where id=(payload->>'id')::uuid for update;
   if not found or (s.kind<>'admin' and b.customer_hash<>v_hash) then return jsonb_build_object('error','예약을 찾을 수 없습니다.'); end if;
   if b.starts_at<=now() then return jsonb_build_object('error','이미 지난 예약은 변경할 수 없습니다.'); end if;
   update salon_private.bookings set state='cancelled' where id=b.id;
   return jsonb_build_object('ok',true);
 end if;
 if action='decide' and s.kind='admin' then
   if payload->>'state' not in ('confirmed','rejected') then return jsonb_build_object('error','잘못된 처리입니다.'); end if;
   update salon_private.bookings set state=payload->>'state' where id=(payload->>'id')::uuid and state='pending' and starts_at>now();
   if not found then return jsonb_build_object('error','이미 처리되었거나 지난 예약입니다. 새로고침해 주세요.'); end if;
   return jsonb_build_object('ok',true);
 end if;
 if action='save_rule' and s.kind='admin' then
   v_from:=(payload->>'start_date')::date; v_until:=(payload->>'end_date')::date;
   if v_from is null or payload->>'state' not in ('available','tentative','unavailable') or (payload->>'start_min')::int<v_open or (payload->>'end_min')::int>v_close
   or (payload->>'start_min')::int%30<>0 or (payload->>'end_min')::int%30<>0 then return jsonb_build_object('error','영업시간 안에서 30분 단위로 설정해 주세요.'); end if;
   insert into salon_private.rules(start_date,end_date,weekdays,start_min,end_min,state,repeats)
   values(v_from,v_until,array(select jsonb_array_elements_text(payload->'weekdays')::int),(payload->>'start_min')::int,(payload->>'end_min')::int,payload->>'state',(payload->>'repeats')::boolean);
   return jsonb_build_object('ok',true);
 end if;
 if action='delete_rule' and s.kind='admin' then
   delete from salon_private.rules where id=(payload->>'id')::bigint;
   return jsonb_build_object('ok',true);
 end if;
 if action='save_prices' and s.kind='admin' then
   v_menu:=payload->'menu'; v_day:=(payload->>'day')::date;
   if jsonb_typeof(v_menu)<>'array' or jsonb_array_length(v_menu)<1 or jsonb_array_length(v_menu)>20 then return jsonb_build_object('error','가격 항목을 1~20개 입력해 주세요.'); end if;
   for v_item in select value from jsonb_array_elements(v_menu) loop
     if length(trim(coalesce(v_item->>'label','')))=0 or length(v_item->>'label')>30 or (v_item->>'price')::int<0 or (v_item->>'price')::int>10000000 then return jsonb_build_object('error','시술명과 올바른 가격을 입력해 주세요.'); end if;
   end loop;
   if (select count(distinct value->>'label') from jsonb_array_elements(v_menu))<>jsonb_array_length(v_menu) then return jsonb_build_object('error','시술 이름은 서로 다르게 입력해 주세요.'); end if;
   if coalesce((payload->>'default')::boolean,false) then update salon_private.settings set base_menu=v_menu where id; end if;
   insert into salon_private.prices(day,menu) values(v_day,v_menu) on conflict(day) do update set menu=excluded.menu;
   return jsonb_build_object('ok',true);
 end if;
 if action='reset_prices' and s.kind='admin' then
   delete from salon_private.prices where day=(payload->>'day')::date;
   return jsonb_build_object('ok',true);
 end if;
 return jsonb_build_object('error','이 작업을 수행할 권한이 없습니다.');
end;
$$;
revoke all on function public.salon_api(text,jsonb,text) from public, anon, authenticated;
grant execute on function public.salon_api(text,jsonb,text) to service_role;

-- SECURITY CHECK: these should both return false.
select has_function_privilege('anon','public.salon_api(text,jsonb,text)','execute') as anon_can_execute,
       has_function_privilege('authenticated','public.salon_api(text,jsonb,text)','execute') as authenticated_can_execute;
