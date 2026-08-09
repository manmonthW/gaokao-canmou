#!/usr/bin/env bash
sudo -u postgres psql -d gaokao -c "SELECT year, category, subject, batch, stage, status FROM admission_publication_status ORDER BY year, batch, stage"
