#!/bin/bash
sudo -u postgres psql -d gaokao -c "SELECT sf.filename, sr.year, count(*) AS rows FROM subject_requirements sr JOIN source_files sf ON sf.id=sr.src_id GROUP BY 1,2 ORDER BY 1"
echo ===
sudo -u postgres psql -d gaokao -c "SELECT * FROM subject_requirements LIMIT 3"
