import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Don't let `next dev` write AGENTS.md / CLAUDE.md into the project folder.
  agentRules: false,
};

export default nextConfig;
