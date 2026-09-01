-- Migration: Mask real user names with placeholder names
-- Date: 2026-08-31
-- Purpose: Replace the 10 real first names in users.display_name with obviously-fake
--          placeholder names ("John Doe" style) for shareable screenshots, keeping
--          each person's apparent gender.
--
--          users.username is the stable join key: load_multi_user_data.py looks users
--          up by `username == <directory slug>` and 003 backfills by
--          `WHERE username = 'tanmay'`. It is NOT changed here -- only display_name,
--          which is the only field the frontend ever renders.
--
-- Gender preserved:
--   male   -> tanmay, abhiraj, amit, nihal, prathamesh, sohan
--   female -> antara, ash, sam, snehal
--
-- Applies after: 006_analytics_functions.sql
-- Run: psql "<conn>" -v ON_ERROR_STOP=1 -f 007_mask_user_names.sql

BEGIN;

UPDATE users SET display_name = v.name
FROM (VALUES
    ('tanmay',     'John Doe'),
    ('abhiraj',    'John Smith'),
    ('amit',       'Richard Roe'),
    ('antara',     'Jane Doe'),
    ('ash',        'Mary Major'),
    ('nihal',      'John Stiles'),
    ('prathamesh', 'Richard Miles'),
    ('sam',        'Jane Roe'),
    ('snehal',     'Mary Minor'),
    ('sohan',      'John Poe')
) AS v(username, name)
WHERE users.username = v.username;

COMMIT;
