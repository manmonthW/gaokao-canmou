#!/usr/bin/env bash
export PGPASSWORD=gaokao123
psql -h localhost -U gaokao -d gaokao -c "SELECT year, category, subject, batch, count(*) FROM admission_scores GROUP BY 1,2,3,4 ORDER BY 1,2,3,4 LIMIT 40;"
