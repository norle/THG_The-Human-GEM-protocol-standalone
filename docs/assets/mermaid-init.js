// Mermaid is loaded as a runtime asset so documentation builds stay offline.
document.addEventListener("DOMContentLoaded", () => {
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: true, securityLevel: "strict" });
  }
});
