import React, {useState} from "react";
import {SecuritySettings} from "./access.jsx";
import {
  useApp,
  AvatarImage,
  Icon,
  Action,
  Empty,
  PageHeading,
  money,
  date,
  dateTime,
} from "./shared.jsx";
export function Account() {
  const { s, orders = [] } = useApp();
  if (!s.user)
    return (
      <main id="main" className="page container" data-react-page="account">
        <Empty
          title="Seu universo está esperando."
          description="Entre para acompanhar seu plano, seus pagamentos e suas histórias."
        >
          <Action action="login">Entrar na minha conta</Action>
        </Empty>
      </main>
    );
  const u = s.user,
    p = s.plans.find((p) => p.id === u.plan_id);
  const labels = {
    approved: "Aprovado",
    pending: "Pendente",
    in_process: "Em análise",
    rejected: "Recusado",
    refunded: "Reembolsado",
    charged_back: "Contestado",
    cancelled: "Cancelado",
  };
  return (
    <main className="page container" id="main" data-react-page="account">
      <PageHeading
        title={"Seu espaço, " + u.name.split(" ")[0] + "."}
        subtitle="Gerencie sua conta e prepare o próximo play."
      >
        <Action
          action="logout"
          className="btn btn-secondary btn-small"
          icon="logout"
        >
          Sair da conta
        </Action>
      </PageHeading>
      {location.search.includes("payment=") && (
        <div className="notice">
          <Icon name="info" />
          <span>
            O acesso é atualizado após a confirmação do Mercado Pago. Se o
            pagamento estiver pendente, aguarde e atualize esta página.
          </span>
        </div>
      )}
      <section className="surface scanner-entry"><h2>Entrar na TV ou no computador</h2><p>Use este celular para escanear o QR Code da outra tela.</p><a className="btn btn-primary" href="/escanear">Escanear QR Code</a></section>
      <div className="account-grid">
        <section className="surface">
          <div className="profile-heading">
            <span className="avatar">
              <AvatarImage user={u}/>
            </span>
            <div>
              <h3>{u.name}</h3>
              <p>{u.email}</p>
            </div>
          </div>
          <AvatarSettings />
          <span className={"badge " + (u.subscribed ? "green" : "yellow")}>
            {u.role === "admin"
              ? "Administrador"
              : u.subscribed
                ? "Plano ativo"
                : "Aguardando assinatura"}
          </span>
          {s.modules?.community!==false && <p className="cm-account-link">
            <a className="btn btn-secondary btn-small" href="/carteira">
              🪙 Minha carteira
            </a>
            <a
              className="btn btn-secondary btn-small"
              href={"/comunidade/perfil/" + u.username}
            >
              <Icon name="user" /> Meu perfil na comunidade
            </a>
          </p>}
          <div className="account-sub">
            <h3>
              {u.role === "admin"
                ? "Acesso administrativo"
                : p?.name || "Escolha seu plano"}
            </h3>
            <p>
              {u.role === "admin"
                ? "Gerencie sua plataforma pelo painel."
                : u.subscribed
                  ? "Seu acesso está disponível até " +
                    dateTime(u.expires_at) +
                    "."
                  : "Finalize a assinatura para liberar filmes, séries e TV ao vivo."}
            </p>
            <a
              href={u.role === "admin" ? "/admin" : "/#planos"}
              className="btn btn-primary btn-small"
            >
              {u.role === "admin"
                ? "Abrir painel"
                : u.subscribed
                  ? "Renovar meu plano"
                  : "Escolher um plano"}{" "}
              <Icon name="arrow" />
            </a>
          </div>
        </section>
        <section className="surface">
          <h2>Segurança da conta</h2>
          <form id="password-form">
            <div className="field">
              <label htmlFor="current-password">Senha atual</label>
              <input
                id="current-password"
                name="current_password"
                type="password"
                required
                autoComplete="current-password"
              />
            </div>
            <div className="field">
              <label htmlFor="new-password">Nova senha</label>
              <input
                id="new-password"
                name="new_password"
                type="password"
                required
                minLength="10"
                maxLength="128"
                autoComplete="new-password"
              />
              <small>Use pelo menos 10 caracteres.</small>
            </div>
            <div className="form-error" role="alert" />
            <button className="btn btn-secondary btn-small" type="submit">
              <Icon name="lock" /> Atualizar senha
            </button>
          </form>
        </section>
        <SecuritySettings/>
        <section className="surface orders-section">
          <h2>Seus pagamentos</h2>
          {orders.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Plano</th>
                    <th>Data</th>
                    <th>Valor</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id}>
                      <td>{o.name || "Plano"}</td>
                      <td>{date(o.created_at)}</td>
                      <td>{money(o.amount)}</td>
                      <td>
                        <span
                          className={
                            "badge " +
                            (o.status === "approved"
                              ? "green"
                              : ["pending", "in_process"].includes(o.status)
                                ? "yellow"
                                : "red")
                          }
                        >
                          {labels[o.status] || o.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>
              Seus pagamentos aparecerão aqui depois que você iniciar uma
              assinatura.
            </p>
          )}
        </section>
      </div>
    </main>
  );
}
export function Legal() {
  const { s, path } = useApp();
  const privacy = path === "/privacidade";
  const paragraphs = privacy
    ? [
        [
          "",
          "Armazenamos os dados necessários para sua conta: nome, e-mail, senha protegida, plano, histórico de pagamentos, favoritos, progresso de reprodução e canais acessados recentemente.",
        ],
        [
          "Como usamos seus dados",
          "Essas informações permitem autenticar seu acesso, confirmar assinaturas e continuar os vídeos de onde você parou. Os dados de cartão são tratados diretamente pelo Mercado Pago e não ficam armazenados nesta plataforma.",
        ],
        [
          "Cookies e armazenamento",
          "Usamos um cookie essencial para manter sua sessão. O navegador pode guardar temporariamente o progresso de um vídeo para sincronizá-lo quando a conexão voltar.",
        ],
        [
          "Seus direitos",
          "Você pode solicitar acesso, correção ou exclusão dos seus dados entrando em contato com o responsável pela plataforma.",
        ],
      ]
    : [
        [
          "",
          "Ao usar a plataforma, você concorda com estas condições. O acesso ao conteúdo exige uma conta ativa e um plano válido.",
        ],
        [
          "Planos e pagamento",
          "Os planos oferecem acesso pelo período informado na contratação, contado após a confirmação do pagamento. Não há renovação automática. Preço, duração e limites aparecem antes da compra. Solicitações de cancelamento ou reembolso devem ser encaminhadas ao responsável pela plataforma, respeitados os direitos previstos na legislação aplicável.",
        ],
        [
          "Catálogo e reprodução",
          "A disponibilidade do catálogo e dos canais pode variar. Qualidade e compatibilidade de reprodução dependem da fonte, do dispositivo e da conexão. Títulos sinalizados como demonstração usam um vídeo de amostra, identificado no player.",
        ],
        [
          "Sua conta",
          "Mantenha sua senha segura. O número de sessões de acesso depende do plano contratado. Ao exceder esse limite, a sessão mais antiga será encerrada. O progresso é associado à conta.",
        ],
      ];
  return (
    <main className="page container legal" id="main" data-react-page="legal">
      <h1>{privacy ? "Sua privacidade importa." : "Termos de uso"}</h1>
      {paragraphs.map(([h, p], n) => (
        <React.Fragment key={n}>
          {h && <h2>{h}</h2>}
          <p>{p}</p>
        </React.Fragment>
      ))}
      <h2>Contato</h2>
      <p>
        {s.support_email ||
          "O endereço de atendimento será informado pelo responsável pela plataforma."}
      </p>
    </main>
  );
}

function AvatarSettings(){
  const {s,actions}=useApp();const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[preview,setPreview]=useState('');
  async function choose(e){
    const file=e.target.files?.[0];e.target.value='';if(!file)return;
    setMessage('');setPreview('');
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>8*1024*1024){setMessage('Escolha uma imagem JPG, PNG ou WebP de até 8 MB.');return;}
    setBusy(true);const url=URL.createObjectURL(file);
    try{const image=new Image();image.src=url;await image.decode();const size=Math.min(image.naturalWidth,image.naturalHeight);if(!size)throw Error('Imagem inválida.');
      const canvas=document.createElement('canvas');canvas.width=canvas.height=256;const ctx=canvas.getContext('2d');ctx.drawImage(image,(image.naturalWidth-size)/2,(image.naturalHeight-size)/2,size,size,0,0,256,256);setPreview(canvas.toDataURL('image/png'));
    }catch(_){setMessage('Não foi possível abrir essa imagem. Escolha outra foto.');}finally{URL.revokeObjectURL(url);setBusy(false);}
  }
  async function save(remove=false){setBusy(true);setMessage('');try{
    await actions.request('/account/avatar',{method:remove?'DELETE':'PUT',body:remove?{}:{avatar:preview}});setPreview('');await actions.refreshState();await actions.navigate('/conta');
  }catch(e){setMessage(e.message);}finally{setBusy(false);}}
  return <section className="account-avatar-editor" aria-label="Alterar avatar"><h3>Foto da conta</h3><p>Altere seu avatar aqui, mesmo com a comunidade desativada.</p>
    <label htmlFor="account-avatar-file">Escolher foto</label><input id="account-avatar-file" type="file" accept="image/png,image/jpeg,image/webp" onChange={choose} disabled={busy}/>
    <p>JPG, PNG ou WebP, até 8 MB. A imagem será recortada ao centro.</p>
    {preview&&<div className="avatar-preview"><img src={preview} alt="Prévia do novo avatar"/><button type="button" className="btn btn-primary btn-small" disabled={busy} onClick={()=>save()}>Salvar avatar</button><button type="button" className="text-button" disabled={busy} onClick={()=>setPreview('')}>Cancelar</button></div>}
    {s.user.avatar&&<button type="button" className="text-button" disabled={busy} onClick={()=>save(true)}>Remover foto</button>}
    {busy&&<p role="status">Processando foto…</p>}{message&&<p role="alert">{message}</p>}
  </section>;
}
