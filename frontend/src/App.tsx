import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./lib/auth";
import { AppRoutes } from "./routes";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="relative min-h-screen overflow-hidden">
          <div className="app-glow pointer-events-none fixed inset-0" />
          <div className="app-grid pointer-events-none fixed inset-0" />
          <div className="relative">
            <AppRoutes />
          </div>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
