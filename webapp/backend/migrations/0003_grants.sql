-- Phase 0 权限修正：为只读角色补齐 SELECT（含未来由 gaokao 拥有者新建的表）
-- 执行方式：以 gaokao 拥有者角色运行
--   PGPASSWORD=gaokao123 psql -U gaokao -h localhost -d gaokao -f 0003_grants.sql
-- 说明：0000_role.sql 由 postgres 超级用户执行，其 DEFAULT PRIVILEGES 仅对
--       postgres 新建对象生效；ETL/迁移实际由 gaokao 执行建表，故此处由 gaokao
--       再对自身新建对象设置默认授权，确保新增表自动对只读角色可见。
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gaokao_web_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO gaokao_web_ro;
