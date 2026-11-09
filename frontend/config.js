// Use "api" after Person 3 implements docs/frontend-api-contract.md.
// No private API keys belong in browser configuration.
window.RECIPEHUB_CONFIG = {
  mode: "mock",
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  timeoutMs: 15000,
};
