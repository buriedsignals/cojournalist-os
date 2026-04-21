// CLI version string. The release workflow (.github/workflows/cli-release.yml)
// rewrites this line with `sed` before `deno compile`, so tagged releases
// report their real version while local dev builds stay "dev".
export const VERSION = "dev";
