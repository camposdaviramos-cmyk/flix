import React, { useState } from "react";
import {
  useApp,
  Icon,
  Action,
  Empty,
  Plan,
  PageHeading,
  timecode,
} from "./shared.jsx";
function Description({ item }) {
  if (!item.id.startsWith("demo-")) return <p>{item.description}</p>;
  const text = item.description || "",
    summary = text.split("\n\n")[0],
    credit = text.match(/^Créditos: (.+)$/m)?.[1] || "",
    source = text.match(/^Fonte: (https:\/\/\S+)$/m)?.[1],
    license = text.match(/^Licença: (https:\/\/\S+)$/m)?.[1];
  return (
    <>
      <p>{summary}</p>
      <aside className="media-credits">
        <span className="demo-label">Conteúdo de demonstração</span>
        <p>{credit}</p>
        <div>
          {source && (
            <a href={source} target="_blank" rel="noopener noreferrer">
              Fonte original <Icon name="link" />
            </a>
          )}
          {license && (
            <a href={license} target="_blank" rel="noopener noreferrer">
              Licença e condições <Icon name="link" />
            </a>
          )}
        </div>
      </aside>
    </>
  );
}
function Favorite({ id }) {
  const { s, actions } = useApp();
  const [saved, setSaved] = useState(s.favorites.includes(id)),
    [busy, setBusy] = useState(false);
  return (
    <button
      className="btn btn-secondary"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          const value = await actions.favorite(id);
          if (value !== null) setSaved(value);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Icon name={saved ? "check" : "plus"} />{" "}
      {saved ? "Na minha lista" : "Minha lista"}
    </button>
  );
}
export function DetailBody({ item, heading = "h1" }) {
  const { s } = useApp();
  const p = s.progress.find((p) => p.content_id === item.id),
    Heading = heading;
  return (
    <>
      <div className="detail-cover">
        <img
          src={item.backdrop || item.poster || "/static/assets/hero.png"}
          alt=""
        />
      </div>
      <div className="detail-body">
        <div className="eyebrow red" style={{ marginBottom: 12 }}>
          {item.kind === "series"
            ? "SÉRIE"
            : item.kind === "channel"
              ? "TV AO VIVO"
              : "FILME"}{" "}
          · {s.brand}
        </div>
        <Heading>{item.title}</Heading>
        <div className="detail-meta">
          <span>{item.year}</span>
          <span className="badge">{item.rating}</span>
          <span>{item.duration}</span>
          <span>{item.genre}</span>
        </div>
        <Description item={item} />
        <div className="detail-actions">
          <Action
            action="play"
            id={item.id}
            episode={p?.episode_id || ""}
            icon="play"
          >
            {p ? "Continuar · " + timecode(p.position) : "Assistir agora"}
          </Action>
          <Action action="share" id={item.id} className="btn btn-secondary">
            Compartilhar
          </Action>
          <Favorite id={item.id} />
        </div>
        {!!item.sample && (
          <span className="demo-label">
            Título de demonstração · reprodução de amostra: Sintel
          </span>
        )}
        {item.kind === "series" && (
          <div className="episode-list">
            <h3>Episódios</h3>
            {item.episodes.length ? (
              item.episodes.map((e) => {
                const ep = s.progress.find((p) => p.episode_id === e.id);
                return (
                  <button
                    key={e.id}
                    className="episode"
                    data-action="play"
                    data-id={item.id}
                    data-episode={e.id}
                  >
                    <span className="episode-number">{e.number}</span>
                    <div className="episode-copy">
                      <strong>{e.title}</strong>
                      <small>
                        Temporada {e.season} · Episódio {e.number} ·{" "}
                        {e.duration}
                        {ep
                          ? " · " + timecode(ep.position) + " assistidos"
                          : ""}
                      </small>
                      {ep && (
                        <div className="progress-track">
                          <span
                            style={{
                              width:
                                Math.min(
                                  100,
                                  (ep.position / (ep.duration || 1)) * 100,
                                ) + "%",
                            }}
                          />
                        </div>
                      )}
                    </div>
                    <Icon name="play" />
                  </button>
                );
              })
            ) : (
              <p className="muted small">
                Os episódios estarão disponíveis em breve.
              </p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
export function Title() {
  const { s, path } = useApp();
  const item = s.items.find((i) => i.id === decodeURIComponent(path.slice(8)));
  return (
    <main id="main" className="page container" data-react-page="title">
      {item ? (
        <article className="surface">
          <DetailBody item={item} />
        </article>
      ) : (
        <Empty title="Título indisponível">
          <a href="/catalogo">Explorar catálogo</a>
        </Empty>
      )}
    </main>
  );
}
export function Plans() {
  const { s } = useApp();
  return (
    <main className="page container" id="main" data-react-page="plans">
      <PageHeading
        title="Escolha seu próximo play."
        subtitle="Encontre o plano que combina com você."
      />
      <section className="section" id="planos">
        <div className="plan-grid">
          {s.plans.map((p) => (
            <Plan key={p.id} plan={p} />
          ))}
        </div>
      </section>
    </main>
  );
}
export function Player({ item, ep, next, result }) {
  return (
    <>
      <div className="player-head">
        <h2>{item.title}</h2>
        <p>
          {ep
            ? `T${ep.season}:E${ep.number} · ${ep.title}`
            : item.kind === "channel"
              ? "TV ao vivo"
              : item.genre}
          {item.id.startsWith("demo-")
            ? " · Demonstração — fonte e créditos nos detalhes"
            : result.sample
              ? " · Vídeo de demonstração: Sintel (Blender Foundation)"
              : ""}
        </p>
      </div>
      {result.position > 0 && !result.live && (
        <div className="resume-banner">
          <span>Continuando em {timecode(result.position)}</span>
          <Action action="restart" className="btn btn-secondary">
            Começar do início
          </Action>
        </div>
      )}
      <div className="video-wrap">
        <video
          id="video-player"
          controls
          playsInline
          preload="metadata"
          crossOrigin="anonymous"
        />
      </div>
      <div className="player-footer">
        <span>
          <Icon name={result.live ? "tv" : "clock"} />{" "}
          {result.live
            ? "Você está acompanhando ao vivo."
            : "Seu progresso é salvo automaticamente."}
        </span>
        {next && (
          <Action
            action="play"
            id={item.id}
            episode={next.id}
            className="btn btn-secondary btn-small"
          >
            Próximo episódio <Icon name="arrow" />
          </Action>
        )}
      </div>
      <div className="player-status" role="status" />
    </>
  );
}
