#!/bin/bash
sudo -u postgres psql -d gaokao -c "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public' AND (column_name ILIKE '%intro%' OR column_name ILIKE '%profile%' OR column_name ILIKE '%desc%' OR column_name ILIKE '%honor%' OR column_name ILIKE '%tag%') ORDER BY table_name"
echo ===
sudo -u postgres psql -d gaokao -c "SELECT name, substring(introduction,1,200) FROM schools WHERE introduction LIKE '%酒%' LIMIT 5" 2>/dev/null
sudo -u postgres psql -d gaokao -c "SELECT name, substring(intro,1,200) FROM school_profiles WHERE intro LIKE '%酒%' LIMIT 5" 2>/dev/null
