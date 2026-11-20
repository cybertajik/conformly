import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { CatalogDemoApp } from "./catalog-demo/CatalogDemoApp";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root is missing");
}

const pathname = window.location.pathname;
const isCatalogDemoPath = pathname === "/catalog-demo" || pathname === "/catalog-demo/";

if (isCatalogDemoPath) {
  const isEnabled =
    import.meta.env.VITE_ENABLE_CATALOG_DEMO === "true" &&
    (import.meta.env.DEV ||
      import.meta.env.MODE === "development" ||
      import.meta.env.MODE === "test" ||
      import.meta.env.MODE === "local");

  if (isEnabled) {
    createRoot(root).render(
      <StrictMode>
        <CatalogDemoApp />
      </StrictMode>,
    );
  } else {
    createRoot(root).render(
      <StrictMode>
        <div style={{ padding: "2rem", fontFamily: "sans-serif", textAlign: "center", color: "#64748b" }}>
          <h2>Catalog Demo Unavailable</h2>
          <p>The synthetic catalog preview is not enabled in this environment.</p>
        </div>
      </StrictMode>,
    );
  }
} else {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
