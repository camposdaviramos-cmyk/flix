import React, { createContext, useContext, useEffect, useRef, useState } from "react";
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
export const money = (n) =>
  (Number(n) / 100).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
export const date = (n) =>
  n ? new Date(n * 1000).toLocaleDateString("pt-BR") : "—";
export const dateTime = (n) =>
  n
    ? new Date(n * 1000).toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
export const timecode = (n) => {
  const s = Math.floor(n || 0);
  return `${s >= 3600 ? Math.floor(s / 3600) + ":" : ""}${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};
export function Icon({ name, className = "" }) {
  const { icons } = useApp();
  return (
    <svg className={"icon " + className} viewBox="0 0 24 24" aria-hidden="true">
      <path d={icons[name] || icons.play} />
    </svg>
  );
}
export function Brand() {
  const { s } = useApp();
  return (
    <a className="brand" href="/" aria-label={s.brand + " início"}>
      <img className="brand-logo" src="/static/assets/worktv-logo-official-v1.png" width="1956" height="804" alt="WorkTV" />
    </a>
  );
}
export function Action({
  action,
  id,
  episode,
  icon,
  children,
  className = "btn btn-primary",
  ...props
}) {
  return (
    <button
      type="button"
      className={className}
      data-action={action}
      data-id={id}
      data-episode={episode}
      {...props}
    >
      {icon && <Icon name={icon} />} {children}
    </button>
  );
}
export function AvatarImage({user}) {
  const [failed,setFailed]=useState(false);
  useEffect(()=>setFailed(false),[user.avatar]);
  return user.avatar&&!failed?<img src={user.avatar} alt="" onError={()=>setFailed(true)}/>:String(user.name||'?')[0].toUpperCase();
}
export function Header() {
  const { s, path } = useApp();
  const tv = !!window.WorkTVPlatform?.tv;
  const menu=useRef(null);
  useEffect(()=>{
    const outside=e=>{if(menu.current&&!menu.current.contains(e.target))menu.current.open=false;};
    const escape=e=>{if(e.key==='Escape'&&menu.current?.open){menu.current.open=false;menu.current.querySelector('summary')?.focus();}};
    document.addEventListener('click',outside);document.addEventListener('keydown',escape);
    return ()=>{document.removeEventListener('click',outside);document.removeEventListener('keydown',escape);};
  },[]);
  return (
    <header className="header">
      <div className="container header-inner">
        <Brand />
        <nav aria-label="Menu principal" id="main-nav">
          {[
            ["/", "Início"],
            ["/filmes", "Filmes"],
            ["/series", "Séries"],
            ...(s.modules?.community!==false?[["/comunidade", "Comunidade"]]:[]),
            [
              "/tv",
              <>
                <span className="live-dot" /> TV ao vivo
              </>,
            ],
            [s.user ? "/planos" : "/#planos", "Planos"],
            ...(s.user ? [["/lista", "Minha lista"]] : []),
          ].map(([url, label]) => (
            <a key={url} href={url} className={path === url ? "active" : ""}>
              {label}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          <a
            className="text-button"
            href="/catalogo"
            aria-label="Buscar no catálogo"
          >
            <Icon name="search" />
          </a>
          {s.user ? (
            <>
              {s.modules?.community!==false && <>
              {tv && (
                <button
                  className="text-button"
                  data-hub="chat"
                  aria-label="Abrir conversas"
                >
                  Conversas
                </button>
              )}
              <button
                className="text-button fh-header-bell"
                data-hub="notices"
                aria-label="Notificações"
              >
                <Icon name="bell" />
                <b data-fh-notices hidden />
              </button>
              <button
                className="text-button fj-nav"
                data-jump="friends"
                aria-label="WorkTV Juntos e amigos"
              >
                <Icon name="users" />
                <span>WorkTV Juntos</span>
              </button>
              </>}
              <details ref={menu} className="fs-user-menu wt-account-menu">
                <summary className="avatar" aria-label="Menu da conta">
                  <AvatarImage user={s.user}/>
                </summary>
                <div onClick={e=>{if(e.target.closest("a,button")&&menu.current)menu.current.open=false;}}>
                  {s.modules?.community!==false && <a href={"/comunidade/perfil/" + s.user.username}>
                    <Icon name="user" /> Meu perfil
                  </a>}
                  <a href="/escanear"><Icon name="camera" /> Escanear QR Code</a>
                  <a href="/perfis"><Icon name="users" /> Trocar perfil</a>
                  <a href="/conta">
                    <Icon name="settings" /> Configurações
                  </a>
                  {s.modules?.community!==false && <button data-hub="preferences">
                    <Icon name="bell" /> Preferências
                  </button>}
                  <Action action="logout" className="text-button" icon="logout">
                    Sair
                  </Action>
                </div>
              </details>
              {s.user.role === "admin" && (
                <a href="/admin" className="btn btn-secondary btn-small">
                  Painel admin
                </a>
              )}
            </>
          ) : (
            <>
              <Action action="login" className="text-button">
                Entrar
              </Action>
              <a className="btn btn-primary btn-small" href="/#planos">
                Assinar agora <Icon name="arrow" />
              </a>
            </>
          )}
          <Action
            action="menu"
            className="icon-btn mobile-toggle"
            aria-label="Abrir menu"
            aria-expanded="false"
            icon="menu"
          />
        </div>
      </div>
    </header>
  );
}
export function Footer() {
  const { s } = useApp();
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-top">
          <div>
            <Brand />
            <p className="footer-tagline">
              Um universo de histórias. O seu próximo play.
            </p>
          </div>
          <div className="footer-links">
            <a href="/catalogo">Explorar catálogo</a>
            <a href={s.user ? "/planos" : "/#planos"}>Planos</a>
            {!s.user && <a href="/#duvidas">Dúvidas</a>}
            <a href="/termos">Termos de uso</a>
            <a href="/privacidade">Privacidade</a>
            <button className="text-button" data-tv-mode>
              {window.WorkTVPlatform?.tv ? "Sair do modo TV" : "Modo TV"}
            </button>
            <button className="text-button" data-pwa-install>
              Instalar WorkTV
            </button>
          </div>
        </div>
        <div className="footer-bottom">
          <span>
            © {new Date().getFullYear()} {s.brand}. Todos os direitos
            reservados.
          </span>
          <span>
            Feito para quem ama boas histórias. <Icon name="heart" />
          </span>
        </div>
      </div>
    </footer>
  );
}
export function Empty({ title, description, children }) {
  return (
    <div className="empty-state">
      <Icon name="film" />
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function PageHeading({ title, subtitle, children }) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
export function Card({ item }) {
  const { s } = useApp();
  const p = s.progress.find((p) => p.content_id === item.id);
  return (
    <article className="movie-card">
      <button
        className="poster-button"
        data-action="details"
        data-id={item.id}
        aria-label={"Ver " + item.title}
      >
        <img
          src={item.poster || "/static/assets/hero.png"}
          alt=""
          loading="lazy"
        />
        <span className="poster-type">
          <b>W</b>{" "}
          {item.kind === "series"
            ? "SÉRIE"
            : item.kind === "channel"
              ? "TV AO VIVO"
              : "FILME"}
        </span>
        {!!item.featured && <span className="poster-badge">EM DESTAQUE</span>}
        <span className="poster-title">
          {item.title}
          <small>UMA NOVA HISTÓRIA ESPERA POR VOCÊ</small>
        </span>
        <span className="poster-hover">
          <span>
            <Icon name="play" />
          </span>
        </span>
      </button>
      <div className="card-info">
        <h3>{item.title}</h3>
        <span>{item.rating}</span>
      </div>
      <p className="card-meta">
        {item.genre} <span>·</span> {item.year}
      </p>
      {p && (
        <div
          className="progress-track"
          title={timecode(p.position) + " assistidos"}
        >
          <span
            style={{
              width:
                Math.min(100, (p.position / (p.duration || 1)) * 100) + "%",
            }}
          />
        </div>
      )}
    </article>
  );
}
export function Channel({ item }) {
  return (
    <button className="channel-card" data-action="play" data-id={item.id}>
      <span className="tag-live">
        <span className="live-dot" /> AO VIVO
      </span>
      {item.poster && <img src={item.poster} alt="" loading="lazy" />}
      <h3>{item.title}</h3>
      <p>
        {item.genre} <Icon name="arrow" />
      </p>
    </button>
  );
}
export function Plan({ plan: p }) {
  return (
    <article className={"plan-card " + (p.featured ? "featured" : "")}>
      {!!p.featured && (
        <div className="plan-ribbon">A ESCOLHA DOS MARATONISTAS</div>
      )}
      <div className="plan-top">
        <h3>{p.name}</h3>
        <span className="quality-tag">{p.quality}</span>
      </div>
      <div className="plan-price">
        <strong>{money(p.price)}</strong>
        <small>/{p.days === 30 ? "mês" : p.days + " dias"}</small>
      </div>
      <p className="plan-caption">Seu entretenimento, no seu ritmo.</p>
      <ul>
        {p.features.map((f) => (
          <li key={f}>
            <Icon name="check" />
            {f}
          </li>
        ))}
      </ul>
      <Action
        action="subscribe"
        id={p.id}
        className={"btn " + (p.featured ? "btn-primary" : "btn-secondary")}
      >
        Escolher {p.name} <Icon name="arrow" />
      </Action>
    </article>
  );
}
export function ResumeCard({ item, progress: p }) {
  const ep = item.episodes.find((e) => e.id === p.episode_id),
    percent = Math.max(
      0,
      Math.min(100, (p.position / (p.duration || 1)) * 100),
    );
  return (
    <article className="resume-card">
      <button
        className="resume-image"
        data-action="play"
        data-id={item.id}
        data-episode={p.episode_id}
        aria-label={`Continuar ${item.title} em ${timecode(p.position)}`}
      >
        <img
          src={item.backdrop || item.poster || "/static/assets/hero.png"}
          alt=""
          loading="lazy"
        />
        <span className="resume-play">
          <Icon name="play" />
        </span>
        <span className="resume-time">
          {timecode(p.duration - p.position)} restantes
        </span>
      </button>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={"Progresso em " + item.title}
        aria-valuenow={Math.round(percent)}
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <span style={{ width: percent + "%" }} />
      </div>
      <div className="resume-copy">
        <a href={"/titulo/" + encodeURIComponent(item.id)}>{item.title}</a>
        <p>{ep ? `T${ep.season} · E${ep.number} — ${ep.title}` : item.genre}</p>
      </div>
    </article>
  );
}
export function MemberRow({
  title,
  items,
  url,
  ranked = false,
  resume = false,
  subtitle = "",
  emptyMessage = "",
}) {
  const id =
    "react-row-" +
    url.replace(/[^a-z0-9]/gi, "-") +
    "-" +
    (ranked ? "rank" : "plain");
  return (
    <section className="member-section">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <a className="member-more" href={url}>
          Ver mais <Icon name="arrow" />
        </a>
      </div>
      {items.length ? (
        <div className="member-row-wrap">
          <Action
            action="member-scroll"
            className="icon-btn member-row-arrow prev"
            data-row={id}
            data-direction="-1"
            aria-label={"Voltar em " + title}
            icon="left"
          />
          <div
            className={
              "poster-row member-row " +
              (resume ? "resume-row " : "") +
              (ranked ? "ranked-row" : "")
            }
            id={id}
          >
            {items.slice(0, 12).map((i, n) =>
              resume ? (
                <ResumeCard key={i.item.id} {...i} />
              ) : ranked ? (
                <div className="ranked-card" key={i.id}>
                  <span
                    className="rank-number"
                    aria-label={"Posição " + (n + 1)}
                  >
                    {n + 1}
                  </span>
                  <Card item={i} />
                </div>
              ) : (
                <Card key={i.id} item={i} />
              ),
            )}
          </div>
          <Action
            action="member-scroll"
            className="icon-btn member-row-arrow next"
            data-row={id}
            data-direction="1"
            aria-label={"Avançar em " + title}
            icon="chevron"
          />
        </div>
      ) : (
        <div className="member-empty">
          {emptyMessage ||
            (resume
              ? "Seu próximo play aparece aqui. Comece um filme ou episódio e volte para continuar de onde parou."
              : "Novos títulos aparecerão aqui quando forem publicados.")}
        </div>
      )}
    </section>
  );
}
export function ChannelStories({ title, items, url, subtitle }) {
  return (
    <section className="member-section channel-stories-section">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <a className="member-more" href={url}>
          Ver mais <Icon name="arrow" />
        </a>
      </div>
      {items.length ? (
        <div className="channel-stories">
          {items.slice(0, 16).map((i) => (
            <button
              key={i.id}
              className="channel-story"
              data-action="play"
              data-id={i.id}
              aria-label={"Assistir " + i.title + " ao vivo"}
            >
              <span className="story-ring">
                <span className="story-image">
                  {i.poster ? (
                    <img src={i.poster} alt="" loading="lazy" />
                  ) : (
                    <Icon name="tv" />
                  )}
                </span>
                <span className="story-live">AO VIVO</span>
              </span>
              <strong>{i.title}</strong>
              <small>{i.genre}</small>
            </button>
          ))}
        </div>
      ) : (
        <div className="member-empty">
          Os canais aparecerão aqui assim que forem publicados.
        </div>
      )}
    </section>
  );
}
