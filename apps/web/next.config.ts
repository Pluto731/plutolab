import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 多阶段构建用 standalone 输出
  output: "standalone",
  // monorepo 根目录 (相对 next.config 所在的 apps/web), 让 standalone 把根 node_modules 也打包
  outputFileTracingRoot: "../../",
};

export default nextConfig;
