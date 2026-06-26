// Hardcoded version constant. Kept in lockstep with the `version` field in
// package.json by the .github/workflows/bump_ts_sdk_version.yaml workflow,
// which rewrites this whole file on every bump. Do not edit by hand.
//
// Lives as a constant — rather than being read from package.json at runtime —
// so the source compiles cleanly to both CJS and ESM without needing
// `__dirname` (CJS-only) or `import.meta.url` (ESM-only).
export const packageVersion = '0.16.0';
