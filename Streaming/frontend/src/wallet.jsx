import React, { useEffect, useState } from "react";
import { useApp, Action, Icon, money, dateTime } from "./shared.jsx";
const Coin = ({ small = false }) => (
  <span className={"fw-coin" + (small ? " small" : "")}>
    f<span>•</span>
  </span>
);
export function Wallet() {
  const { s, actions } = useApp(),
    [data, setData] = useState(null),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (!s.user) return;
    (async () => {
      const query = new URLSearchParams(location.search),
        payment = query.get("payment_id") || query.get("collection_id");
      if (payment) {
        try {
          const value = await actions.request("/payments/sync", {
            method: "POST",
            body: { payment_id: payment },
          });
          if (active)
            setNotice(
              value.status === "approved"
                ? "Pagamento confirmado. Confira seu saldo."
                : "Pagamento em processamento. O saldo será atualizado após a confirmação.",
            );
        } catch (e) {
          if (active) setNotice(e.message);
        }
      } else if (query.has("payment"))
        setNotice("Seu saldo será atualizado após a confirmação do pagamento.");
      try {
        const value = await actions.request("/wallet");
        if (active) setData(value);
      } catch (e) {
        if (active) setError(e.message);
      }
    })();
    return () => {
      active = false;
    };
  }, [s.user?.id]);
  if (!s.user)
    return (
      <main className="page container" id="main" data-react-page="wallet">
        <h1>Sua carteira WorkTV</h1>
        <p>Entre para acompanhar suas moedas.</p>
        <Action action="login">Entrar</Action>
      </main>
    );
  return (
    <main id="main" className="page container fw-page" data-react-page="wallet">
      <a className="cm-back" href="/comunidade">
        <Icon name="left" /> Comunidade
      </a>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SUA CARTEIRA</span>
          <h1>
            Pequenos gestos.
            <br />
            Grandes conexões.
          </h1>
          <p>Presenteie a turma e participe dos jogos da comunidade.</p>
        </div>
      </div>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Carregando sua carteira…</p>}
      {data && (
        <>
          <section className="fw-balance">
            <Coin />
            <div>
              <small>SEU SALDO</small>
              <strong>
                {data.balance.toLocaleString("pt-BR")} <span>moedas</span>
              </strong>
              <p>Use em presentes e jogos com entrada em moedas.</p>
            </div>
          </section>
          {data.balance < 0 && (
            <p className="notice">
              Uma compra foi estornada após o uso das moedas. Regularize o saldo
              para voltar a enviar presentes e entrar em jogos pagos.
            </p>
          )}
          <h2>Adicionar moedas</h2>
          <div className="fw-packages">
            {data.packages.map((pack) => (
              <article key={pack.id}>
                <Coin small />
                <strong>{pack.coins.toLocaleString("pt-BR")}</strong>
                <small>{pack.name}</small>
                <button
                  className="btn btn-primary"
                  onClick={() => actions.walletPurchase(pack)}
                >
                  {money(pack.price)}
                </button>
                <span>Pagamento pelo Mercado Pago</span>
              </article>
            ))}
            {!data.packages.length && (
              <p className="muted">
                Os pacotes serão disponibilizados pelo administrador.
              </p>
            )}
          </div>
          <p className="fw-note">
            Moedas são créditos virtuais da comunidade. Os presentes aparecem no
            perfil de quem recebe. Não são transferíveis como dinheiro nem
            oferecem saque.
          </p>
          <section className="surface fw-history">
            <h2>Movimentações</h2>
            {data.ledger.map((item) => (
              <div key={item.id}>
                <span>
                  <strong>{item.reason}</strong>
                  <small>{dateTime(item.created_at)}</small>
                </span>
                <b className={item.amount > 0 ? "positive" : ""}>
                  {item.amount > 0 ? "+" : ""}
                  {item.amount.toLocaleString("pt-BR")}
                </b>
              </div>
            ))}
            {!data.ledger.length && <p>Sua próxima interação começa aqui.</p>}
          </section>
        </>
      )}
    </main>
  );
}
export function WalletPurchase({ pack }) {
  const { actions } = useApp(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function checkout() {
    setBusy(true);
    setError("");
    try {
      const value = await actions.request("/checkout", {
        method: "POST",
        body: {
          package_id: pack.id,
          confirm_price: pack.price,
          confirm_coins: pack.coins,
        },
      });
      location.assign(value.url);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <div className="modal-body fw-purchase">
      <Coin />
      <h2>{pack.coins.toLocaleString("pt-BR")} moedas</h2>
      <p>
        {pack.name} · <strong>{money(pack.price)}</strong>
      </p>
      <p>
        Você será direcionado ao Mercado Pago. O saldo é liberado após a
        confirmação do pagamento.
      </p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <button className="btn btn-primary" disabled={busy} onClick={checkout}>
        {busy ? "Preparando pagamento…" : "Continuar para o pagamento"}
      </button>
    </div>
  );
}
