import { Route, Switch } from "wouter";

import GalaxyPage from "./pages/Galaxy";
import IndexPage from "./pages/Index";
import LoginPage from "./pages/Login";
import ShaderPage from "./pages/Shader";
import Y2KPage from "./pages/Y2K";

export default function App() {
  return (
    <Switch>
      <Route path="/" component={IndexPage} />
      <Route path="/galaxy" component={GalaxyPage} />
      <Route path="/shader" component={ShaderPage} />
      <Route path="/y2k" component={Y2KPage} />
      <Route path="/login" component={LoginPage} />
      <Route>
        <NotFound />
      </Route>
    </Switch>
  );
}

function NotFound() {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
      }}
    >
      <h1 style={{ fontSize: 80 }}>404</h1>
      <a href="/" style={{ opacity: 0.6 }}>
        回 lab 入口 →
      </a>
    </div>
  );
}
