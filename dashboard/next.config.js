/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // optional: suppress some linting during build if it errors
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
}

module.exports = nextConfig
