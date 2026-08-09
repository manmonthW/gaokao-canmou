#!/bin/bash
# 核对未匹配院校在 schools 表中的真实名称（更名/噪声）
sudo -u postgres psql -d gaokao -c "
SELECT name FROM schools WHERE name LIKE '%宁波大学%' OR name LIKE '%体育%'
  OR name LIKE '%对外%' OR name LIKE '%中医%' OR name LIKE '%蚌埠%'
  OR name LIKE '%水利水电%' OR name LIKE '%南京医科%' OR name LIKE '%南京中医药%'
  OR name LIKE '%徐州医科%' OR name LIKE '%贵州师范%' OR name LIKE '%广州医科%'
  OR name LIKE '%福建中医药%' OR name LIKE '%音乐学院%' OR name LIKE '%西安美术%'
  OR name LIKE '%广西艺术%' OR name LIKE '%甘肃中医药%' OR name LIKE '%华北电力%'
ORDER BY name"
