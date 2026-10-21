-- Neon 上的角色与权限（由 import.sh 以 Neon 库 owner 身份执行，非超级用户也可运行）。
-- psql 变量：ro_password / rw_password（由 import.sh 传入，不写进文件）
--
--   gaokao_web_ro   只读分析库：public schema 下所有表 SELECT，无写权限 → GAOKAO_DSN
--   gaokao_app_rw   可写库：只拥有 app schema（用户、Agent 任务、限流），看不到也改不了分析表 → APP_DB_URL
--
-- 两个角色互相隔离：ro 没有 app schema 的 USAGE，读不到用户密码哈希；rw 对 public 只有 USAGE。
-- 可重复执行。

SELECT format('CREATE ROLE gaokao_web_ro LOGIN PASSWORD %L', :'ro_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_web_ro') \gexec
SELECT format('ALTER ROLE gaokao_web_ro PASSWORD %L', :'ro_password') \gexec

SELECT format('CREATE ROLE gaokao_app_rw LOGIN PASSWORD %L', :'rw_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_app_rw') \gexec
SELECT format('ALTER ROLE gaokao_app_rw PASSWORD %L', :'rw_password') \gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO gaokao_web_ro, gaokao_app_rw', current_database()) \gexec

-- 只读角色：分析表（对应 migrations/0000_role.sql + 0003_grants.sql）
GRANT USAGE ON SCHEMA public TO gaokao_web_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gaokao_web_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO gaokao_web_ro;
ALTER ROLE gaokao_web_ro SET default_transaction_read_only = on;

-- 可写角色：自己的 schema，表由应用首次访问时自动创建（user_db / jobs / rate_limit）
-- Neon owner 不是超级用户，需先成为该角色成员才能把 schema 授权给它
GRANT gaokao_app_rw TO CURRENT_USER;
CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION gaokao_app_rw;
REVOKE ALL ON SCHEMA app FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM gaokao_app_rw;
ALTER ROLE gaokao_app_rw SET search_path = app;
