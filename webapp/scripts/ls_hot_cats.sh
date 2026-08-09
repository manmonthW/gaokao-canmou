#!/bin/bash
B="/home/ekewang/projects/gaokao/ln/2026allmaterial/热门大学介绍"
for d in C9 E9 五院四系 两电一邮 国防七子; do
  echo "== $d =="
  ls "$B/$d" 2>&1
done
