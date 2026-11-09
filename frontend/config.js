// Run `python -m recipehub.cli serve` to connect this website to the local knowledge base.
// Switch to "mock" only when demonstrating the synthetic UI fixtures.
// No private API keys belong in browser configuration.
window.RECIPEHUB_CONFIG = {
  mode: "api",
  apiBaseUrl: `${window.location.origin}/api/v1`,
  timeoutMs: 120000,
};
