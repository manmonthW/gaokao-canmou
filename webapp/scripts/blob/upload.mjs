// 把 prepare_assets.py 产出的 staging 目录上传到 Vercel Blob，并写出后端用的清单。
//
// 用法（在 webapp/scripts/blob 下）：
//   npm ci
//   BLOB_READ_WRITE_TOKEN=... node upload.mjs <staging 目录> ../../backend/asset-manifest.json
//
// - 路径固定为 gaokao-assets/<相对路径>，不加随机后缀；重复执行会覆盖同名文件（幂等）。
// - 清单里已有且大小一致的文件跳过，只传新增/变化的。加 --force 全部重传。
// - token 只从环境变量读，不打印。
import { put } from '@vercel/blob';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const PREFIX = 'gaokao-assets';
const CONCURRENCY = 6;
const MULTIPART_BYTES = 20 * 1024 * 1024;

const TYPES = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.pdf': 'application/pdf' };

async function walk(dir, base = dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full, base)));
    else if (entry.isFile()) out.push(path.relative(base, full).split(path.sep).join('/'));
  }
  return out.sort();
}

async function main() {
  const args = process.argv.slice(2).filter((a) => a !== '--force');
  const force = process.argv.includes('--force');
  const [stagingDir, manifestPath] = args;
  if (!stagingDir || !manifestPath) {
    console.error('用法: node upload.mjs <staging 目录> <清单输出路径> [--force]');
    process.exit(2);
  }
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    console.error('缺少环境变量 BLOB_READ_WRITE_TOKEN（Vercel 项目 → Storage → Blob → .env.local）');
    process.exit(2);
  }

  const manifest = existsSync(manifestPath) ? JSON.parse(await readFile(manifestPath, 'utf8')) : {};
  const files = await walk(stagingDir);
  const todo = [];
  for (const key of files) {
    const { size } = await stat(path.join(stagingDir, key));
    if (!force && manifest[key]?.size === size) continue;
    todo.push({ key, size });
  }
  console.log(`共 ${files.length} 个文件，需上传 ${todo.length} 个`);

  let done = 0;
  const failures = [];
  async function worker() {
    while (todo.length) {
      const { key, size } = todo.shift();
      try {
        const body = await readFile(path.join(stagingDir, key));
        const blob = await put(`${PREFIX}/${key}`, body, {
          access: 'public',
          addRandomSuffix: false,
          allowOverwrite: true,
          contentType: TYPES[path.extname(key).toLowerCase()] ?? 'application/octet-stream',
          cacheControlMaxAge: 60 * 60 * 24 * 30,
          multipart: size > MULTIPART_BYTES,
        });
        manifest[key] = { url: blob.url, size };
        done += 1;
        if (done % 25 === 0) console.log(`  已上传 ${done}`);
      } catch (err) {
        failures.push(key);
        console.error(`  失败 ${key}: ${err.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  // 清单只保留 staging 里仍存在的文件
  const keep = new Set(files);
  const out = Object.fromEntries(Object.entries(manifest).filter(([k]) => keep.has(k)).sort());
  await writeFile(manifestPath, JSON.stringify(out, null, 1) + '\n', 'utf8');
  console.log(`完成：上传 ${done}，失败 ${failures.length}，清单 ${Object.keys(out).length} 条 → ${manifestPath}`);
  if (failures.length) process.exit(1);
}

main();
