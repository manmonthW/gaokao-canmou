-- Phase 0 配置安全整改：创建网站只读角色
-- 执行方式：以 postgres 超级用户运行
--   sudo -u postgres psql -d gaokao -f 0000_role.sql
-- 该角色仅拥有 CONNECT / USAGE / SELECT 权限，供 Web 后端只读访问，
-- 不持有写权限，与 ETL 使用的 gaokao 拥有者角色分离。
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gaokao_web_ro') THEN
    CREATE ROLE gaokao_web_ro LOGIN PASSWORD 'gk_web_ro_9f3a2c';
  END IF;
END $$;

GRANT CONNECT ON DATABASE gaokao TO gaokao_web_ro;
GRANT USAGE ON SCHEMA public TO gaokao_web_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO gaokao_web_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO gaokao_web_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO gaokao_web_ro;
