-- PlutoLab — Postgres 初始化脚本
-- 由 docker-entrypoint-initdb.d 在首次启动时自动执行（容器空 data 目录时）。
-- 后续修改本文件不会重跑，需要 docker compose down -v 清空 volume 才会重新初始化。

-- pgvector 扩展（向量相似度搜索，用于 Phase 4 RAG）
CREATE EXTENSION IF NOT EXISTS vector;

-- 加密扩展（用于 gen_random_uuid() / crypt() 等）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 全文搜索辅助（unaccent: 去重音符号；pg_trgm: 模糊搜索 / 相似度）
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 时区
SET TIMEZONE = 'Asia/Shanghai';

-- 输出验证（首次启动日志里能看到）
DO $$
BEGIN
  RAISE NOTICE '✅ PlutoLab Postgres initialized';
  RAISE NOTICE '   - vector: %', (SELECT extversion FROM pg_extension WHERE extname='vector');
  RAISE NOTICE '   - pgcrypto: %', (SELECT extversion FROM pg_extension WHERE extname='pgcrypto');
  RAISE NOTICE '   - unaccent: %', (SELECT extversion FROM pg_extension WHERE extname='unaccent');
  RAISE NOTICE '   - pg_trgm: %', (SELECT extversion FROM pg_extension WHERE extname='pg_trgm');
END $$;
