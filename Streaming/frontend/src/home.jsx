import React, { useState } from "react";
import {
  useApp,
  Icon,
  Action,
  Card,
  Plan,
  MemberRow,
  ChannelStories,
  money,
} from "./shared.jsx";
const features = [
  [
    "devices",
    "Sua tela. Suas regras.",
    "Assista pelo navegador no computador, tablet ou celular. Sua próxima história vai com você.",
  ],
  [
    "clock",
    "Sua história não se perde.",
    "Deu uma pausa? Filmes e episódios voltam ao ponto em que você parou, em qualquer dispositivo.",
  ],
  [
    "spark",
    "Qualidade em cada cena.",
    "Uma experiência imersiva, com suporte a Full HD e 4K, conforme o conteúdo e a sua conexão.",
  ],
];
export function Home() {
  const { s } = useApp();
  return s.user ? <MemberHome /> : <GuestHome />;
}
function GuestHome() {
  const { s } = useApp();
  const [filter, setFilter] = useState("Em destaque");
  const items = s.items.filter(
    (i) =>
      i.kind !== "channel" &&
      (filter === "Em destaque" ||
        (filter === "Filmes" && i.kind === "movie") ||
        (filter === "Séries" && i.kind === "series") ||
        i.genre === filter),
  );
  const faq = [
    [
      "O que é a " + s.brand + "?",
      "Uma plataforma para reunir filmes, séries e canais de TV ao vivo. Navegue pelo catálogo, escolha seu plano e encontre sua próxima história.",
    ],
    [
      "Como funciona a assinatura?",
      "Escolha um plano, crie sua conta e finalize o pagamento no Mercado Pago. O acesso é liberado após a confirmação e fica disponível pelo período contratado. Você pode renovar quando quiser.",
    ],
    [
      "Posso assistir em quais dispositivos?",
      "Em computadores, tablets e celulares com navegador atualizado. A compatibilidade da TV depende do navegador e dos formatos de vídeo que ela suporta.",
    ],
    [
      "O vídeo continua de onde parei?",
      "Sim. O progresso é salvo por conta, filme e episódio durante a reprodução, ao pausar e ao sair. Ao voltar, você pode continuar ou recomeçar.",
    ],
    [
      "Como funciona a TV ao vivo?",
      "Os canais cadastrados no catálogo transmitem diretamente pelo player, com suporte a HLS e formatos compatíveis com seu navegador. A programação e a disponibilidade dependem de cada canal.",
    ],
    [
      "Preciso cancelar a renovação?",
      "Os planos são pré-pagos pelo período informado. Não há renovação automática nem cobrança adicional ao final. Seu histórico fica na conta para quando você voltar.",
    ],
  ];
  return (
    <main id="main" data-react-page="home">
      <section className="hero wt-hero">
        <div className="hero-art" />
        <div className="container hero-content">
          <div className="eyebrow">
            <i /> SEU PRÓXIMO UNIVERSO FAVORITO ESTÁ AQUI
          </div>
          <h1>
            Histórias que
            <br />
            ficam com <em>você.</em>
          </h1>
          <p className="hero-description">
            Filmes que surpreendem. Séries que viciam.
            <br />
            TV ao vivo que conecta. Tudo em um só lugar.
          </p>
          <div className="hero-buttons">
            <a href="#planos" className="btn btn-primary">
              Quero fazer parte <Icon name="arrow" />
            </a>
            <a href="/catalogo" className="btn btn-secondary">
              <Icon name="play" /> Explorar catálogo
            </a>
          </div>
          <div className="hero-note">
            <span>
              <Icon name="check" /> Sem fidelidade
            </span>
            <span>
              <Icon name="check" /> Planos a partir de{" "}
              {money(
                s.plans.length
                  ? Math.min(...s.plans.map((p) => p.price))
                  : 1990,
              )}
            </span>
          </div>
          <div className="hero-proof">
            <div className="people">
              <span>4K</span>
              <span>HD</span>
              <span>TV</span>
            </div>
            <div className="proof-copy">
              <div className="stars">✦ ✦ ✦ ✦ ✦</div>
              <strong>Uma experiência de cinema.</strong> Onde você estiver.
            </div>
          </div>
        </div>
        <div className="feature-caption">
          <span className="small-label">EM DESTAQUE NA {s.brand}</span>
          <h3>Além do Horizonte</h3>
          <p>FICÇÃO CIENTÍFICA · 2026 · 4K</p>
          <div className="caption-line" />
        </div>
        <div className="container hero-bottom">
          <a className="scroll-label" href="#descobrir">
            <Icon name="down" /> TEM MUITO MAIS PARA DESCOBRIR
          </a>
          <div className="hero-dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </div>
      </section>
      <div className="container">
        <div className="benefit-strip">
          {[
            [
              "film",
              "Um catálogo, infinitas emoções",
              "Filmes e séries para cada momento",
            ],
            ["tv", "Sua TV, sem limites", "Canais ao vivo em um só lugar"],
            ["devices", "A sua tela favorita", "Do celular para a tela grande"],
            ["clock", "O play continua", "Exatamente de onde você parou"],
          ].map(([i, t, sub]) => (
            <div key={i}>
              <Icon name={i} />
              <div>
                <strong>{t}</strong>
                <small>{sub}</small>
              </div>
            </div>
          ))}
        </div>
        <section className="section" id="descobrir">
          <div className="section-heading">
            <div>
              <div className="eyebrow">DÊ PLAY NA SUA PRÓXIMA OBSESSÃO</div>
              <h2>Difícil vai ser escolher.</h2>
            </div>
            <div className="heading-right">
              <a href="/catalogo">
                Ver todo o catálogo <Icon name="arrow" />
              </a>
              <div className="row-controls">
                <Action
                  className="icon-btn"
                  action="scroll-row"
                  data-direction="-1"
                  aria-label="Títulos anteriores"
                  icon="left"
                />
                <Action
                  className="icon-btn"
                  action="scroll-row"
                  data-direction="1"
                  aria-label="Próximos títulos"
                  icon="chevron"
                />
              </div>
            </div>
          </div>
          <div className="category-pills home-categories">
            {[
              "Em destaque",
              "Filmes",
              "Séries",
              "Ficção científica",
              "Ação",
              "Documentário",
            ].map((g) => (
              <button
                key={g}
                className={"pill " + (filter === g ? "active" : "")}
                aria-pressed={filter === g}
                onClick={() => setFilter(g)}
              >
                {g}
              </button>
            ))}
          </div>
          <div className="poster-row" id="home-posters">
            {items
              .slice(0, filter === "Em destaque" ? 8 : items.length)
              .map((i) => (
                <Card key={i.id} item={i} />
              ))}
          </div>
        </section>
        <section className="section live-section reveal">
          <div className="live-banner">
            <div>
              <span className="tag-live">
                <span className="live-dot" /> AGORA, AO VIVO
              </span>
              <h2>
                O mundo acontece.
                <br />
                <span>Você acompanha.</span>
              </h2>
              <p>
                Esporte, notícias, entretenimento e muito mais. A experiência da
                TV, com a liberdade do streaming.
              </p>
              <a className="btn btn-secondary btn-small" href="/tv">
                <Icon name="tv" /> Conhecer a TV ao vivo <Icon name="arrow" />
              </a>
            </div>
            <div className="channel-wall">
              {[
                ["tv", "PLAY", "ENTRETENIMENTO"],
                ["globe", "news", "INFORMAÇÃO"],
                ["film", "cinema", "HISTÓRIAS"],
                ["spark", "kids", "DIVERSÃO"],
                ["play", "sport", "EMOÇÃO"],
                ["globe", "nature", "DESCOBERTAS"],
              ].map(([i, n, c]) => (
                <div className="channel-tile" key={n}>
                  <Icon name={i} />
                  <div>
                    {n}
                    <small>{c}</small>
                  </div>
                </div>
              ))}
              <div className="channel-disclaimer">
                UM UNIVERSO DE POSSIBILIDADES NA SUA PROGRAMAÇÃO
              </div>
            </div>
          </div>
        </section>
        <section className="section device-section reveal">
          <div className="center-heading">
            <div className="eyebrow">FEITO PARA O SEU JEITO DE ASSISTIR</div>
            <h2>Seu sofá é só o começo.</h2>
            <p>
              Uma experiência pensada em cada detalhe. Você só precisa escolher
              o que assistir.
            </p>
          </div>
          <div className="feature-grid">
            {features.map(([i, t, p]) => (
              <article className="feature-box" key={i}>
                <div className="feature-icon">
                  <Icon name={i} />
                </div>
                <h3>{t}</h3>
                <p>{p}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="section plans-section reveal" id="planos">
          <div className="center-heading" style={{ textAlign: "center" }}>
            <div className="eyebrow">ESCOLHA SEU PRÓXIMO PLAY</div>
            <h2>Grandes histórias. Pequenos preços.</h2>
            <p>
              Escolha o plano que combina com você. Sem fidelidade, sem
              complicação.
            </p>
          </div>
          <div className="plan-grid">
            {s.plans.map((p) => (
              <Plan key={p.id} plan={p} />
            ))}
          </div>
          <p className="plans-footnote">
            <Icon name="shield" /> Pagamento seguro com Mercado Pago. Acesso
            pelo período contratado, sem renovação automática.
          </p>
        </section>
        <section className="section faq-section reveal" id="duvidas">
          <div className="center-heading">
            <div className="eyebrow">PODE PERGUNTAR</div>
            <h2>Antes do próximo episódio.</h2>
          </div>
          {faq.map(([q, a]) => (
            <details className="faq-item" key={q}>
              <summary>
                {q}
                <Icon name="plus" />
              </summary>
              <p>{a}</p>
            </details>
          ))}
        </section>
        <section className="cta-banner reveal">
          <div>
            <h2>
              A próxima grande história
              <br />
              começa com um play.
            </h2>
            <p>Seu lugar já está reservado. Vem para a {s.brand}.</p>
          </div>
          <a href="#planos" className="btn btn-primary">
            Encontrar meu plano <Icon name="arrow" />
          </a>
        </section>
      </div>
    </main>
  );
}
function MemberHome() {
  const { s, helpers } = useApp();
  const movies = s.items.filter((i) => i.kind === "movie"),
    series = s.items.filter((i) => i.kind === "series"),
    featured = s.items.filter((i) => i.featured && i.kind !== "channel"),
    heroes = featured.length
      ? featured
      : s.items.filter((i) => i.kind !== "channel"),
    hero = heroes[(s.heroIndex || 0) % Math.max(1, heroes.length)],
    continuing = helpers.unfinished(),
    channels = helpers.topItems("channel"),
    recent = s.recentChannels
      .map((p) =>
        s.items.find((i) => i.id === p.content_id && i.kind === "channel"),
      )
      .filter(Boolean);
  return (
    <main id="main" className="member-home" data-react-page="member-home">
      <section className="member-hero" aria-label="Em destaque">
        {hero && (
          <img
            className="member-hero-image"
            src={hero.backdrop || hero.poster || "/static/assets/hero.png"}
            alt=""
            fetchPriority="high"
          />
        )}
        <div className="member-hero-shade" />
        <div className="container member-hero-content">
          <p className="member-welcome">
            Olá, {s.user.name.split(" ")[0]}. Seu próximo play está aqui.
          </p>
          <div className="eyebrow red">
            {hero
              ? `${hero.kind === "series" ? "SÉRIE" : "FILME"} EM DESTAQUE`
              : "SEU UNIVERSO DE HISTÓRIAS"}
          </div>
          <h1>{hero?.title || "Escolha sua próxima história."}</h1>
          {hero ? (
            <>
              <div className="member-hero-meta">
                <span>{hero.year}</span>
                <span className="badge">{hero.rating}</span>
                <span>{hero.genre}</span>
              </div>
              <p className="member-hero-description">{hero.description}</p>
              <div className="member-hero-actions">
                <Action action="play" id={hero.id} icon="play">
                  Assistir agora
                </Action>
                <a
                  className="btn btn-secondary"
                  href={"/titulo/" + encodeURIComponent(hero.id)}
                >
                  <Icon name="info" /> Mais informações
                </a>
              </div>
            </>
          ) : (
            <a href="/catalogo" className="btn btn-primary">
              Explorar catálogo
            </a>
          )}
          <div className="member-hero-bottom">
            <a className="member-more" href="/catalogo?view=featured">
              Ver mais destaques <Icon name="arrow" />
            </a>
            {heroes.length > 1 && (
              <div className="member-hero-controls">
                <Action
                  action="hero-step"
                  className="icon-btn"
                  data-direction="-1"
                  aria-label="Destaque anterior"
                  icon="left"
                />
                <span>
                  {((s.heroIndex || 0) % heroes.length) + 1} / {heroes.length}
                </span>
                <Action
                  action="hero-step"
                  className="icon-btn"
                  data-direction="1"
                  aria-label="Próximo destaque"
                  icon="chevron"
                />
              </div>
            )}
          </div>
        </div>
      </section>
      <div className="container member-shelves">
        {!s.user.subscribed && (
          <div className="notice">
            <Icon name="spark" />
            <span>
              Escolha um plano para liberar seu próximo play.{" "}
              <a href="/planos">Ver planos</a>
            </span>
          </div>
        )}
        <MemberRow
          title="Assistidos recentemente"
          items={s.recentWatched
            .map((p) => s.items.find((i) => i.id === p.content_id))
            .filter((i) => i && i.kind !== "channel")}
          url="/historico"
          subtitle="Seus últimos filmes e séries, incluindo os que você já terminou."
        />
        <MemberRow
          title="Continue assistindo"
          items={continuing}
          url="/continuar"
          resume
          subtitle="Suas histórias, exatamente de onde você parou."
        />
        <ChannelStories
          title={recent.length ? "Seus canais recentes" : "Canais principais"}
          items={recent.length ? recent : channels}
          url={recent.length ? "/tv?view=recent" : "/tv"}
          subtitle="Toque para entrar ao vivo."
        />
        <MemberRow
          title="Filmes em destaque"
          items={movies.filter((i) => i.featured)}
          url="/filmes?view=featured"
        />
        <MemberRow
          title="Séries em destaque"
          items={series.filter((i) => i.featured)}
          url="/series?view=featured"
        />
        <MemberRow
          title="Top filmes"
          items={helpers.topItems("movie").slice(0, 10)}
          url="/filmes?view=top"
          ranked
          subtitle={
            movies.some((i) => i.viewers > 0)
              ? "Mais acessados pela comunidade."
              : "Nossa seleção para o seu próximo play."
          }
        />
        <MemberRow
          title="Top séries"
          items={helpers.topItems("series").slice(0, 10)}
          url="/series?view=top"
          ranked
          subtitle={
            series.some((i) => i.viewers > 0)
              ? "Mais acessadas pela comunidade."
              : "Nossa seleção para a sua próxima maratona."
          }
        />
        <MemberRow
          title="Novidades no catálogo"
          items={[...movies, ...series].sort(
            (a, b) => b.created_at - a.created_at,
          )}
          url="/catalogo?view=new"
        />
        <MemberRow
          title="Minha lista"
          items={s.items.filter(
            (i) => s.favorites.includes(i.id) && i.kind !== "channel",
          )}
          url="/lista"
          emptyMessage="Salve filmes e séries em Minha lista para encontrar suas próximas histórias aqui."
        />
        {recent.length > 0 && (
          <ChannelStories
            title="Canais principais"
            items={channels}
            url="/tv"
            subtitle="Sua programação em um toque."
          />
        )}
      </div>
    </main>
  );
}
