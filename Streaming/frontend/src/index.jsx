import React from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { AppContext, Header, Footer } from "./shared.jsx";
import { Home } from "./home.jsx";
import { Catalog, Continue, History } from "./catalog.jsx";
import { Title, Plans, Player } from "./details.jsx";
import { Account, Legal } from "./account.jsx";
import { Wallet, WalletPurchase } from "./wallet.jsx";
import { Auth } from "./auth.jsx";
const routes = [
  "/",
  "/catalogo",
  "/filmes",
  "/series",
  "/tv",
  "/lista",
  "/continuar",
  "/historico",
  "/planos",
  "/conta",
  "/carteira",
  "/termos",
  "/privacidade",
];
class ScreenBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    window.WorkTVBoot?.fail();
  }
  render() {
    if (this.state.failed)
      return (
        <main
          id="main"
          className="page container"
          role="alert"
          data-worktv-render-failed
        >
          <h1>WorkTV</h1>
          <p>Não foi possível carregar esta tela.</p>
          <button
            className="btn btn-primary"
            onClick={() => {
              if (window.WorkTVBoot) window.WorkTVBoot.retry();
              else location.reload();
            }}
          >
            Tentar novamente
          </button>
        </main>
      );
    return this.props.children;
  }
}
let chromeRoots = [];
let root = null,
  modal = null;
function Page({ path }) {
  if (path === "/") return <Home />;
  if (path.startsWith("/titulo/")) return <Title />;
  if (path === "/planos") return <Plans />;
  if (path === "/carteira") return <Wallet />;
  if (path === "/conta") return <Account />;
  if (path === "/termos" || path === "/privacidade") return <Legal />;
  if (path === "/continuar") return <Continue />;
  if (path === "/historico") return <History />;
  return <Catalog />;
}
window.WorkTVUI = {
  supports: (path) => routes.includes(path) || path.startsWith("/titulo/"),
  render(element, context) {
    root = createRoot(element, {
      onUncaughtError: () => window.WorkTVBoot?.fail(),
    });
    flushSync(() =>
      root.render(
        <AppContext.Provider value={context}>
          <ScreenBoundary>
            <Header />
            <Page path={context.path} />
            <Footer />
          </ScreenBoundary>
        </AppContext.Provider>,
      ),
    );
  },
  renderChrome(context) {
    document.querySelectorAll("[data-react-chrome]").forEach((element) => {
      const chrome = createRoot(element);
      chromeRoots.push(chrome);
      flushSync(() =>
        chrome.render(
          <AppContext.Provider value={context}>
            {element.dataset.reactChrome === "header" ? <Header /> : <Footer />}
          </AppContext.Provider>,
        ),
      );
    });
  },
  unmount() {
    chromeRoots.forEach((chrome) => flushSync(() => chrome.unmount()));
    chromeRoots = [];
    if (root) {
      flushSync(() => root.unmount());
      root = null;
    }
  },
  renderModal(element, context, type, props) {
    modal = createRoot(element);
    flushSync(() =>
      modal.render(
        <AppContext.Provider value={context}>
          {type === "auth" ? (
            <Auth {...props} />
          ) : type === "wallet" ? (
            <WalletPurchase {...props} />
          ) : (
            <Player {...props} />
          )}
        </AppContext.Provider>,
      ),
    );
  },
  unmountModal() {
    if (modal) {
      flushSync(() => modal.unmount());
      modal = null;
    }
  },
};
