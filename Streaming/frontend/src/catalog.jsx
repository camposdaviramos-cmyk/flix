import React, { useMemo, useState } from "react";
import {
  useApp,
  Icon,
  Card,
  Channel,
  Empty,
  Action,
  PageHeading,
  ResumeCard,
} from "./shared.jsx";
export function Catalog() {
  const { s, path, helpers } = useApp();
  const [genre, setGenre] = useState(s.genre),
    [query, setQuery] = useState(s.query);
  const items = helpers.baseItems();
  const genres = ["Todos", ...new Set(items.map((i) => i.genre))];
  const labels = {
    "/catalogo": [
      "Explore seu próximo universo.",
      "Uma história para cada versão de você.",
    ],
    "/filmes": [
      "A noite pede um bom filme.",
      "Encontre aquela história que fica com você.",
    ],
    "/series": ["Só mais um episódio.", "Descubra sua próxima maratona."],
    "/tv": ["O mundo, ao vivo.", "Sua programação favorita, em um só lugar."],
    "/lista": [
      "Sua próxima maratona.",
      "Os títulos que você guardou para depois.",
    ],
  };
  const [title, subtitle] = helpers.collectionHeading() || labels[path];
  const filtered = useMemo(
    () =>
      items.filter(
        (i) =>
          (genre === "Todos" || i.genre === genre) &&
          `${i.title} ${i.genre}`
            .toLocaleLowerCase("pt-BR")
            .includes(query.toLocaleLowerCase("pt-BR")),
      ),
    [items, genre, query],
  );
  const continuing = [
    ...new Set(
      s.progress
        .filter((p) => p.position > 0 && p.position < p.duration - 10)
        .map((p) => p.content_id),
    ),
  ]
    .map((id) => s.items.find((i) => i.id === id))
    .filter(Boolean);
  return (
    <main id="main" className="page container" data-react-page="catalog">
      <div className="page-heading">
        <div>
          <div className="eyebrow red" style={{ marginBottom: 13 }}>
            {path === "/tv" ? (
              <>
                <span className="live-dot" /> TV AO VIVO
              </>
            ) : (
              "O EXTRAORDINÁRIO ESTÁ AQUI"
            )}
          </div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        {s.user && (
          <a className="btn btn-secondary btn-small" href="/lista">
            <Icon name="heart" /> Minha lista
          </a>
        )}
      </div>
      {!s.user?.subscribed && (
        <div className="notice">
          <Icon name="spark" />
          <span>
            Explore à vontade. <a href="/planos">Escolha seu plano</a> para
            começar a assistir.
          </span>
        </div>
      )}
      {path === "/catalogo" && continuing.length > 0 && (
        <section style={{ marginBottom: 35 }}>
          <div className="section-heading">
            <h2>Seu play continua</h2>
          </div>
          <div className="poster-row">
            {continuing.map((i) => (
              <Card key={i.id} item={i} />
            ))}
          </div>
        </section>
      )}
      <div className="catalog-toolbar">
        <div className="category-pills">
          {genres.map((g) => (
            <button
              key={g}
              className={"pill " + (genre === g ? "active" : "")}
              aria-pressed={genre === g}
              onClick={() => {
                s.genre = g;
                setGenre(g);
              }}
            >
              {g}
            </button>
          ))}
        </div>
        <label className="search-box">
          <Icon name="search" />
          <input
            id="catalog-search"
            placeholder="Busque uma história…"
            aria-label="Buscar no catálogo"
            value={query}
            onInput={(e) => e.stopPropagation()}
            onChange={(e) => {
              s.query = e.target.value;
              setQuery(e.target.value);
            }}
          />
        </label>
      </div>
      <div
        id="catalog-items"
        className={"catalog-grid " + (path === "/tv" ? "channels-grid" : "")}
      >
        {filtered.length ? (
          filtered.map((i) =>
            i.kind === "channel" ? (
              <Channel key={i.id} item={i} />
            ) : (
              <Card key={i.id} item={i} />
            ),
          )
        ) : (
          <Empty
            title={
              path === "/tv"
                ? "A programação está chegando."
                : path === "/lista"
                  ? "Guarde suas próximas histórias."
                  : "Nenhum título por aqui."
            }
            description={
              path === "/tv"
                ? "Os canais aparecerão aqui assim que forem adicionados."
                : path === "/lista"
                  ? "Toque em Minha lista nos detalhes de um título para salvar."
                  : "Experimente outro título ou categoria."
            }
          >
            {path === "/lista" && !s.user && (
              <Action action="login">Entrar</Action>
            )}
          </Empty>
        )}
      </div>
    </main>
  );
}
export function Continue() {
  const { s, helpers } = useApp();
  const items = helpers.unfinished();
  return (
    <main id="main" className="page container" data-react-page="continue">
      <PageHeading
        title="Continue assistindo"
        subtitle="Filmes e séries que você ainda não terminou."
      >
        <a href="/catalogo" className="btn btn-secondary btn-small">
          Explorar catálogo <Icon name="arrow" />
        </a>
      </PageHeading>
      {!s.user ? (
        <Empty
          title="Entre para continuar."
          description="Seu progresso acompanha sua conta."
        >
          <Action action="login">Entrar</Action>
        </Empty>
      ) : items.length ? (
        <div className="continue-grid">
          {items.map((i) => (
            <ResumeCard key={i.item.id} {...i} />
          ))}
        </div>
      ) : (
        <Empty
          title="Seu próximo play está esperando."
          description="Comece um filme ou série. Os títulos em andamento aparecerão aqui."
        >
          <a href="/catalogo" className="btn btn-primary">
            Explorar catálogo
          </a>
        </Empty>
      )}
    </main>
  );
}
export function History() {
  const { s } = useApp();
  const kind = new URLSearchParams(location.search).get("kind") || "all";
  const items = s.recentWatched
    .map((p) => s.items.find((i) => i.id === p.content_id))
    .filter((i) => i && (kind === "all" || i.kind === kind));
  return (
    <main id="main" className="page container" data-react-page="history">
      <PageHeading
        title="Assistidos recentemente"
        subtitle="Filmes, séries e canais que fizeram parte do seu último play."
      />
      <nav className="cm-tabs">
        {[
          ["all", "Todos"],
          ["movie", "Filmes"],
          ["series", "Séries"],
          ["channel", "TV"],
        ].map(([k, l]) => (
          <a
            key={k}
            className={kind === k ? "active" : ""}
            href={"/historico?kind=" + k}
          >
            {l}
          </a>
        ))}
      </nav>
      <div className="catalog-grid">
        {items.length ? (
          items.map((i) => <Card key={i.id} item={i} />)
        ) : (
          <p className="muted">Seu próximo play aparecerá aqui.</p>
        )}
      </div>
    </main>
  );
}
