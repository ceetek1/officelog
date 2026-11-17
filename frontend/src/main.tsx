// Phones use the system font (SF Pro on iPhone, Roboto on Android), so the app feels native.
// The entrance TV keeps Atkinson Hyperlegible; it loads those fonts itself (pages/tv/Tv.tsx).
import "./styles/tokens.css";
import "./styles/base.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { SessionProvider } from "./session";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <App />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
