import React from "react";
import { useApp, Brand, Icon, money } from "./shared.jsx";
export function Auth({ mode = "login" }) {
  const { s } = useApp();
  const register = mode === "register",
    p = s.plans.find((p) => p.id === s.selectedPlan) || s.plans[0];
  return (
    <div className="modal-body">
      <div className="modal-heading">
        <Brand />
        <h2>
          {register
            ? "Seu próximo play começa aqui."
            : "Que bom ter você de volta."}
        </h2>
        <p>
          {register
            ? "Crie sua conta e venha viver novas histórias."
            : "Entre para continuar de onde parou."}
        </p>
      </div>
      {register && p && (
        <div className="selected-plan">
          <strong>Plano {p.name}</strong>
          <span>
            {money(p.price)} / {p.days} dias
          </span>
        </div>
      )}
      <form id="auth-form" data-mode={mode}>
        {register && (
          <>
            <div className="field">
              <label htmlFor="auth-name">Seu nome</label>
              <input
                id="auth-name"
                name="name"
                placeholder="Como podemos chamar você?"
                autoComplete="name"
                required
                minLength="2"
                maxLength="100"
              />
            </div>
            <div className="field">
              <label htmlFor="auth-username">Nome de usuário</label>
              <input
                id="auth-username"
                name="username"
                placeholder="seu_usuario"
                autoComplete="username"
                required
                pattern="[a-zA-Z0-9_]{3,24}"
                maxLength="24"
              />
              <small>Seus amigos encontram você por este nome.</small>
            </div>
          </>
        )}
        <div className="field">
          <label htmlFor="auth-email">E-mail</label>
          <input
            id="auth-email"
            name="email"
            type="email"
            placeholder="voce@exemplo.com"
            autoComplete="email"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="auth-password">Senha</label>
          <input
            id="auth-password"
            name="password"
            type="password"
            placeholder={register ? "Pelo menos 10 caracteres" : "Sua senha"}
            autoComplete={register ? "new-password" : "current-password"}
            required
            minLength={register ? 10 : undefined}
            maxLength="128"
          />
        </div>
        {register && (
          <>
            <div className="signup-coupon">
              <label htmlFor="auth-coupon">
                Tem um cupom? <span>Opcional</span>
              </label>
              <div className="coupon-input-row">
                <input
                  id="auth-coupon"
                  name="coupon_code"
                  placeholder="Digite seu cupom"
                  maxLength="32"
                  autoComplete="off"
                  autoCapitalize="characters"
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-small"
                  data-action="validate-coupon"
                >
                  Aplicar
                </button>
              </div>
              <p id="coupon-feedback" role="status" aria-live="polite" />
            </div>
            <input type="hidden" name="plan_id" value={p?.id || ""} />
            <label className="check-field">
              <input type="checkbox" name="terms" required />
              <span>
                Li e aceito os{" "}
                <a href="/termos" className="red">
                  termos de uso
                </a>
                .
              </span>
            </label>
          </>
        )}
        <div className="form-error" role="alert" />
        <button className="btn btn-primary full-width" type="submit">
          {register ? "Criar conta e continuar" : "Entrar na minha conta"}{" "}
          <Icon name="arrow" />
        </button>
      </form>
      {register && (
        <p className="auth-terms">
          Com um cupom válido de teste grátis, o acesso é liberado no cadastro.
          <br />
          Sem cupom, você poderá assinar pelo checkout seguro do Mercado Pago.
        </p>
      )}
      <p className="auth-switch">
        {register ? (
          <>
            Já faz parte?{" "}
            <button className="text-button" data-action="login">
              Entre aqui
            </button>
          </>
        ) : (
          <>
            Ainda não tem conta?{" "}
            <button className="text-button" data-action="register">
              Comece agora
            </button>
          </>
        )}
      </p>
    </div>
  );
}
