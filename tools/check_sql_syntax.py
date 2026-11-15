"""Offline parser check only; run supabase/verify.sql in a NEW test project for DB checks."""
from pathlib import Path
from pglast import parse_sql, parse_plpgsql

ROOT = Path(__file__).resolve().parents[1]
for filename in ('setup.sql', 'retention.sql', 'verify.sql'):
    text = (ROOT / 'supabase' / filename).read_text(encoding='utf-8')
    statements = parse_sql(text)
    print(f'{filename}: {len(statements)} SQL statements parsed')
    if filename == 'setup.sql':
        start = text.index('create or replace function public.salon_api')
        end = text.index('$$;', start) + 3
        parse_plpgsql(text[start:end])
        print('salon_api: PL/pgSQL syntax parsed')
print('PASS: syntax only, not execution or production security certification')
