/* Native motion engine: one scheduled frame, lifecycle cleanup, spring physics,
   scroll choreography and a depth-aware Canvas field. No animation CDN required. */
(() => {
  'use strict';

  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  const clamp = (n, a = 0, b = 1) => Math.min(b, Math.max(a, n));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smoothstep = n => n * n * (3 - 2 * n);
  const select = (s, root = document) => root.querySelector(s);
  const selectAll = (s, root = document) => [...root.querySelectorAll(s)];
  const ease = 'cubic-bezier(.16,1,.3,1)';
  let engine = null, introPlayed = false, paused = false, chromeReady = false;
  try { paused = localStorage.getItem('vyra-motion-paused') === 'true'; } catch (_) {}
  const reduced = () => media.matches || paused;

  function createChrome() {
    if (chromeReady) return;
    chromeReady = true;
    const progress = document.createElement('div');
    progress.className = 'vx-progress';
    progress.setAttribute('aria-hidden', 'true');
    const cursor = document.createElement('div');
    cursor.className = 'vx-cursor';
    cursor.setAttribute('aria-hidden', 'true');
    const toggle = document.createElement('button');
    toggle.className = 'vx-motion-toggle';
    toggle.type = 'button';
    toggle.innerHTML = '<span class="vx-motion-bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="vx-motion-label"></span>';
    toggle.addEventListener('click', () => {
      paused = !paused;
      try { localStorage.setItem('vyra-motion-paused', String(paused)); } catch (_) {}
      updatePreference();
    });
    document.body.append(progress, cursor, toggle);
    updatePreference();
    media.addEventListener('change', updatePreference);
    document.addEventListener('visibilitychange', () => {
      document.documentElement.classList.toggle('vx-hidden-tab', document.hidden);
      if (document.hidden) engine?.sleep(); else engine?.wake();
    });
    addEventListener('pagehide', () => engine?.sleep());
    addEventListener('pageshow', () => engine?.wake());
  }

  function updatePreference() {
    document.documentElement.classList.toggle('vx-paused', reduced());
    const toggle = select('.vx-motion-toggle');
    if (toggle) {
      toggle.setAttribute('aria-pressed', String(paused));
      toggle.setAttribute('aria-label', paused ? 'Ativar animações' : 'Pausar animações');
      select('.vx-motion-label', toggle).textContent = paused ? 'MOVIMENTO PAUSADO' : 'MOVIMENTO ATIVO';
    }
    engine?.preferenceChanged();
  }

  function storyMarkup() {
    const playIcon = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7Z"/></svg>';
    const scenes = [
      { title: 'Além do Horizonte', type: 'FILMES', sub: 'Cada cena, uma nova emoção.', img: '/static/assets/hero.png' },
      { title: 'Cidade Neon', type: 'SÉRIES', sub: 'Seu próximo universo favorito.', img: '/static/assets/neon.jpg' },
      { title: 'O mundo. Agora.', type: 'TV AO VIVO', sub: 'Conecte-se ao que acontece.', img: '/static/assets/orbita.jpg' }
    ];
    return `<section class="vx-story" aria-label="Explore filmes, séries e TV ao vivo">
      <div class="vx-story-pin">
        <div class="vx-story-aurora" aria-hidden="true"></div><div class="vx-story-orbit" aria-hidden="true"></div>
        <div class="vx-story-heading"><div class="eyebrow"><i></i> NÃO É SÓ ASSISTIR. É SENTIR.</div><h2>Um play.<br><span>Infinitos universos.</span></h2><p>Continue rolando. Sua próxima história está ganhando vida.</p></div>
        <div class="vx-stage" aria-hidden="true">
          <div class="vx-stage-floor"></div>
          ${scenes.map((s, i) => `<div class="vx-scene-card ${i === 0 ? 'vx-active' : ''}" data-vx-scene="${i}"><img src="${s.img}" alt="" loading="lazy"><div class="vx-scene-top"><b>V</b><span>${s.type}</span></div><div class="vx-scene-title"><h3>${s.title}</h3><small>${s.sub}</small></div><span class="vx-scene-play">${playIcon}</span></div>`).join('')}
        </div>
        <div class="vx-story-controls"><div class="vx-scene-tabs" role="tablist" aria-label="Escolher universo">
          <button class="vx-scene-tab" type="button" role="tab" id="vx-tab-0" aria-controls="vx-scene-description" aria-selected="true" data-vx-tab="0">${playIcon} Filmes</button>
          <button class="vx-scene-tab" type="button" role="tab" id="vx-tab-1" aria-controls="vx-scene-description" aria-selected="false" tabindex="-1" data-vx-tab="1">${playIcon} Séries</button>
          <button class="vx-scene-tab" type="button" role="tab" id="vx-tab-2" aria-controls="vx-scene-description" aria-selected="false" tabindex="-1" data-vx-tab="2"><span class="live-dot"></span> Ao vivo</button>
        </div><div id="vx-scene-description" role="tabpanel" aria-labelledby="vx-tab-0"><a class="vx-scene-link" href="/filmes"><span>Explorar filmes</span><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg></a></div></div>
        <div class="vx-story-bottom"><span>TRÊS UNIVERSOS. UMA EXPERIÊNCIA.</span><div class="vx-story-track" aria-hidden="true"><span></span></div><div class="vx-story-counter" aria-hidden="true"><strong>01</strong> / 03</div></div>
      </div>
    </section>`;
  }

  function deviceMarkup() {
    const screen = (name, stamp) => `<div class="vx-device-screen"><div class="vx-device-image"></div><span class="vx-device-brand">V<span>•</span></span><div class="vx-device-caption"><small>CONTINUE SUA HISTÓRIA</small><strong>Além do Horizonte</strong><div class="vx-device-progress"><span></span><i></i></div><span class="vx-device-time">00:42 <span>/ ${stamp}</span></span></div><span class="vx-device-play" aria-hidden="true">▶</span></div>`;
    return `<div class="vx-device-lab" data-screen="desktop" aria-label="Demonstração visual da experiência em diferentes telas">
      <div class="vx-device-scene" aria-hidden="true">
        <div class="vx-device-glow"></div><div class="vx-device-grid"></div>
        <svg class="vx-device-connections" viewBox="0 0 1000 360" fill="none"><path d="M210 215C270 330 470 340 540 180S710 90 805 195"/><path d="M210 215C270 330 470 340 540 180S710 90 805 195"/></svg>
        <div class="vx-device vx-device-desktop">${screen('Computador', '02:18')}<div class="vx-monitor-neck"></div><div class="vx-monitor-foot"></div></div>
        <div class="vx-device vx-device-tablet">${screen('Tablet', '02:18')}</div>
        <div class="vx-device vx-device-phone">${screen('Celular', '02:18')}<span class="vx-phone-camera"></span></div>
        <div class="vx-device-sync"><span class="vx-sync-dot"></span> SUA HISTÓRIA, SEM INTERRUPÇÕES</div>
      </div>
      <div class="vx-device-options" role="group" aria-label="Explorar telas">
        <button type="button" data-vx-device="desktop" aria-pressed="true">Computador</button><button type="button" data-vx-device="tablet" aria-pressed="false">Tablet</button><button type="button" data-vx-device="phone" aria-pressed="false">Celular</button>
      </div><p class="vx-device-hint">Toque em uma tela e leve sua história com você. <span>Prévia visual.</span></p>
    </div>`;
  }

  class MotionEngine {
    constructor(root) {
      this.root = root;
      this.abort = new AbortController();
      this.signal = this.abort.signal;
      this.animations = new Set();
      this.springs = new Map();
      this.pointer = { x: 0, y: 0, sx: 0, sy: 0, clientX: 0, clientY: 0, present: false };
      this.frameId = 0;
      this.lastFrame = 0;
      this.scroll = scrollY;
      this.smoothScroll = scrollY;
      this.layoutDirty = true;
      this.alive = true;
      this.stagePosition = 0;
      this.stageTarget = 0;
      this.sceneIndex = -1;
      this.manualScene = null;
      this.lastDragTime = -1000;
      this.inertia = null;
      this.touchGesture = null;
      this.touchPulse = null;
      this.introTime = performance.now();
      this.cursor = select('.vx-cursor');
      this.hero = select('.hero', root);
      this.heroArt = select('.hero-art', root);
      this.heroCopy = select('.hero-content', root);
      this.caption = select('.feature-caption', root);
      this.header = select('.header', root);
      if (this.hero) this.buildHome();
      this.bind();
      this.registerContent(root);
      this.measure();
      this.drawStage(true);
      this.animateEntrance();
      this.wake();
      document.fonts?.ready.then(() => { if (this.alive) { this.layoutDirty = true; this.wake(); } });
    }

    on(el, type, fn, options = {}) { el.addEventListener(type, fn, { ...options, signal: this.signal }); }

    animate(el, frames, options = {}) {
      if (!el || reduced() || !this.alive) return null;
      const animation = el.animate(frames, { duration: 850, easing: ease, fill: 'both', ...options });
      this.animations.add(animation);
      animation.finished.then(() => { animation.cancel(); this.animations.delete(animation); }, () => this.animations.delete(animation));
      return animation;
    }

    buildHome() {
      const atmosphere = document.createElement('div');
      atmosphere.className = 'vx-atmosphere';
      atmosphere.setAttribute('aria-hidden', 'true');
      atmosphere.innerHTML = '<div class="vx-orbit"></div><div class="vx-beam"></div><canvas class="vx-starfield"></canvas>';
      this.hero.prepend(atmosphere);
      this.hero.insertAdjacentHTML('beforeend', '<div class="vx-hero-line" aria-hidden="true"></div><div class="vx-coordinate" aria-hidden="true"><span>VYRA ORIGINAL EXPERIENCE</span><strong>01 — ∞</strong></div><div class="vx-orbital-label" aria-hidden="true">ALÉM DO SEU UNIVERSO</div><div class="vx-explore-cue" aria-hidden="true"><i class="vx-mouse"></i><span>EXPLORE. SINTA. DÊ PLAY.</span></div>');
      this.canvas = select('canvas', atmosphere);
      this.ctx = this.canvas.getContext('2d', { alpha: true });
      this.particles = Array.from({ length: innerWidth < 650 ? 54 : 140 }, (_, i) => ({
        x: Math.random(), y: Math.random(), z: .2 + Math.random() * .8,
        radius: .45 + Math.random() * 1.5, speed: .07 + Math.random() * .2,
        phase: Math.random() * Math.PI * 2, red: i % 5 === 0
      }));
      const strip = select('.benefit-strip', this.root);
      const words = ['SINTA CADA CENA', 'VIVA CADA HISTÓRIA', 'EXPLORE NOVOS UNIVERSOS', 'DÊ PLAY NO EXTRAORDINÁRIO'];
      const group = words.map(w => `<span>${w}</span><i>✦</i>`).join('');
      strip?.insertAdjacentHTML('afterend', `<div class="vx-ticker" aria-hidden="true"><div class="vx-ticker-track"><div class="vx-ticker-group">${group}</div><div class="vx-ticker-group">${group}</div></div></div>`);
      select('#descobrir', this.root)?.insertAdjacentHTML('afterend', storyMarkup());
      this.story = select('.vx-story', this.root);
      this.storyPin = select('.vx-story-pin', this.root);
      this.stage = select('.vx-stage', this.root);
      this.sceneCards = selectAll('.vx-scene-card', this.root);
      this.sceneTabs = selectAll('.vx-scene-tab', this.root);
      this.sceneTabs.forEach(tab => {
        this.on(tab, 'click', () => this.chooseScene(Number(tab.dataset.vxTab), true));
        this.on(tab, 'keydown', event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const old = Number(tab.dataset.vxTab);
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (old + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
          this.chooseScene(next, true);
          this.sceneTabs[next].focus();
        });
      });
      select('.device-section .center-heading', this.root)?.insertAdjacentHTML('afterend', deviceMarkup());
      this.deviceLab = select('.vx-device-lab', this.root);
      selectAll('[data-vx-device]', this.root).forEach(button => this.on(button, 'click', () => {
        this.chooseDevice(button.dataset.vxDevice);
        this.ripple(button, { detail: 0 });
      }));
      selectAll('.vx-device', this.root).forEach(device => this.on(device, 'click', () => {
        if (performance.now() - this.lastDragTime < 200) return;
        this.chooseDevice(device.classList.contains('vx-device-phone') ? 'phone' : device.classList.contains('vx-device-tablet') ? 'tablet' : 'desktop');
      }));
      if (!finePointer.matches) {
        select('.vx-story-heading>p', this.root).textContent = 'Role para explorar. Deslize as cenas para escolher.';
        select('.vx-device-hint', this.root).innerHTML = 'Toque nas telas ou deslize para trocar. <span>Prévia visual.</span>';
      }
    }

    chooseDevice(name) {
      if (!this.deviceLab) return;
      this.deviceLab.dataset.screen = name;
      selectAll('[data-vx-device]', this.deviceLab).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.vxDevice === name)));
      this.animate(select('.vx-device-sync', this.deviceLab), [
        { opacity: .2, transform: 'translateX(-50%) translateY(8px)' },
        { opacity: 1, transform: 'translateX(-50%) translateY(0)' }
      ], { duration: 650 });
    }

    bind() {
      this.on(window, 'scroll', () => { this.scroll = scrollY; this.wake(); }, { passive: true });
      this.on(window, 'resize', () => { this.layoutDirty = true; this.wake(); }, { passive: true });
      this.on(document, 'pointermove', e => this.pointerMove(e), { passive: true });
      this.on(document, 'pointerout', e => {
        if (e.pointerType === 'touch') return;
        if (!e.relatedTarget) { this.pointer.present = false; this.pointer.x = this.pointer.y = 0; }
        for (const [el, spring] of this.springs) if (!el.contains(e.relatedTarget)) this.resetSpring(spring);
        this.wake();
      }, { passive: true });
      this.on(this.root, 'pointerdown', e => this.pointerDown(e), { passive: true });
      this.on(document, 'pointerup', e => this.pointerUp(e), { passive: true });
      this.on(document, 'pointercancel', e => this.pointerUp(e), { passive: true });
      this.on(document, 'click', e => {
        if (performance.now() - this.lastDragTime < 180 && e.target.closest('.poster-row,.vx-stage,.vx-device-scene')) {
          e.preventDefault(); e.stopImmediatePropagation();
        }
      }, { capture: true });
      this.on(this.root, 'click', e => {
        const target = e.target.closest('.btn,.pill,.vx-scene-tab,.icon-btn');
        if (target && !target.disabled) this.ripple(target, e);
      });
      this.on(this.root, 'toggle', e => {
        if (e.target.matches('.faq-item')) { this.layoutDirty = true; this.wake(); }
      }, { capture: true });
      this.resizeObserver = new ResizeObserver(() => { this.layoutDirty = true; this.wake(); });
      this.resizeObserver.observe(this.root);
      this.mutationObserver = new MutationObserver(records => {
        const additions = records.flatMap(r => [...r.addedNodes]).filter(n => n.nodeType === 1 && !n.matches('.vx-ripple,.vx-word,.vx-glare'));
        for (const node of additions) {
          if (node.matches('.movie-card,.channel-card,.plan-card,.stat-card,.quick-action,tr') || node.querySelector('.movie-card,.channel-card,.plan-card')) this.registerContent(node);
        }
        if (additions.length) { this.layoutDirty = true; this.wake(); }
      });
      this.mutationObserver.observe(this.root, { childList: true, subtree: true });
      this.revealObserver = new IntersectionObserver(entries => {
        for (const { target, isIntersecting } of entries) {
          if (!isIntersecting) continue;
          this.revealObserver.unobserve(target);
          const delay = Math.min(Number(target.dataset.vxDelay) || 0, 420);
          this.animate(target, [
            { opacity: 0, transform: 'perspective(1000px) translate3d(0,55px,0) rotateX(9deg)', filter: 'blur(5px)' },
            { opacity: 1, transform: 'perspective(1000px) translate3d(0,0,0) rotateX(0)', filter: 'blur(0)' }
          ], { duration: 1100, delay });
          target.classList.remove('vx-pending');
          if (target.matches('.stat-card')) this.animateCounter(target);
        }
      }, { threshold: .08, rootMargin: '0px 0px -25px 0px' });
    }

    registerContent(root) {
      const selectors = '.section-heading,.center-heading,.feature-box,.plan-card,.live-banner,.cta-banner,.movie-card,.channel-card,.benefit-strip>div,.stat-card,.quick-action,.table-panel,.page-heading,.admin-title,.vx-device-lab';
      const nodes = [...(root.matches?.(selectors) ? [root] : []), ...selectAll(selectors, root)];
      nodes.forEach((node, i) => {
        if (node.dataset.vxReveal) return;
        node.dataset.vxReveal = 'true';
        node.classList.add('vx-reveal-item');
        const siblings = [...node.parentElement.children];
        node.dataset.vxDelay = String(Math.min(siblings.indexOf(node) * 85, 340));
        if (!reduced()) node.classList.add('vx-pending');
        this.revealObserver?.observe(node);
      });
      selectAll('.poster-button', root).forEach(button => {
        if (select('.vx-glare', button)) return;
        const glare = document.createElement('span');
        glare.className = 'vx-glare'; glare.setAttribute('aria-hidden', 'true');
        button.append(glare);
      });
    }

    animateCounter(card) {
      if (reduced()) return;
      const el = select('strong', card), final = el?.textContent || '';
      if (!/^\d+$/.test(final) || +final === 0) return;
      const count = Number(final), start = performance.now();
      const step = now => {
        if (!this.alive || reduced()) { el.textContent = final; return; }
        const t = clamp((now - start) / 1000);
        el.textContent = Math.round(count * (1 - Math.pow(1 - t, 3)));
        if (t < 1) this.counterFrames.add(requestAnimationFrame(step));
      };
      this.counterFrames ??= new Set();
      this.counterFrames.add(requestAnimationFrame(step));
    }

    splitHeading(heading) {
      if (!heading || heading.dataset.vxSplit) return [];
      heading.dataset.vxSplit = 'true';
      heading.setAttribute('aria-label', heading.innerText.replace(/\s+/g, ' ').trim());
      const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
      const texts = []; while (walker.nextNode()) texts.push(walker.currentNode);
      for (const text of texts) {
        const fragment = document.createDocumentFragment();
        for (const word of text.textContent.match(/\S+\s*|\s+/g) || []) {
          const span = document.createElement('span');
          span.className = 'vx-word'; span.textContent = word; span.setAttribute('aria-hidden', 'true');
          fragment.append(span);
        }
        text.replaceWith(fragment);
      }
      return selectAll('.vx-word', heading);
    }

    animateEntrance() {
      if (reduced()) return;
      this.animate(select('.header', this.root), [{ opacity: 0, transform: 'translateY(-24px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 1100, delay: 150 });
      if (this.hero) {
        const words = this.splitHeading(select('h1', this.hero));
        words.forEach((word, i) => this.animate(word, [
          { opacity: 0, transform: 'translate3d(0,100%,0) rotateX(-65deg) rotateZ(3deg)', filter: 'blur(12px)' },
          { opacity: 1, transform: 'translate3d(0,0,0) rotateX(0) rotateZ(0)', filter: 'blur(0)' }
        ], { duration: 1300, delay: 280 + i * 95 }));
        ['.hero .eyebrow', '.hero-description', '.hero-buttons', '.hero-note', '.hero-proof', '.feature-caption', '.vx-coordinate'].forEach((s, i) => this.animate(select(s, this.root), [
          { opacity: 0, transform: 'translateY(28px)', filter: 'blur(4px)' },
          { opacity: 1, transform: 'translateY(0)', filter: 'blur(0)' }
        ], { duration: 1200, delay: 350 + i * 100 }));
        if (!introPlayed && scrollY < 100) { introPlayed = true; this.aperture(); }
      } else {
        this.animate(select('#main', this.root), [{ opacity: 0, transform: 'translateY(20px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 750 });
      }
    }

    aperture() {
      const overlay = document.createElement('div');
      overlay.className = 'vx-intro'; overlay.setAttribute('aria-hidden', 'true');
      overlay.innerHTML = '<div></div><div></div><i></i>';
      document.body.append(overlay);
      const parts = [...overlay.children];
      const animations = [
        parts[0].animate([{ transform: 'translateY(0)' }, { transform: 'translateY(-102%)' }], { duration: 1100, easing: ease, fill: 'forwards' }),
        parts[1].animate([{ transform: 'translateY(0)' }, { transform: 'translateY(102%)' }], { duration: 1100, easing: ease, fill: 'forwards' }),
        parts[2].animate([{ scale: '0 1', opacity: 1 }, { scale: '1 1', opacity: .8, offset: .3 }, { scale: '1 1', opacity: 0 }], { duration: 800, easing: ease, fill: 'forwards' })
      ];
      Promise.all(animations.map(a => a.finished.catch(() => {}))).then(() => overlay.remove());
      this.introOverlay = overlay;
    }

    measure() {
      this.width = innerWidth; this.height = innerHeight;
      this.documentHeight = Math.max(1, document.documentElement.scrollHeight - this.height);
      if (this.hero) {
        this.heroHeight = this.hero.offsetHeight;
        this.dpr = Math.min(devicePixelRatio || 1, this.width < 650 ? 1.4 : 1.7);
        if (this.canvas) {
          const w = Math.round(this.width * this.dpr), h = Math.round(this.heroHeight * this.dpr);
          if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h; }
        }
      }
      if (this.story) {
        this.storyTop = this.story.getBoundingClientRect().top + scrollY;
        this.storyHeight = this.story.offsetHeight;
        this.pinHeight = this.storyPin.offsetHeight;
      }
      this.layoutDirty = false;
      this.springs.forEach(s => { s.bounds = null; });
    }

    springFor(el, type) {
      if (!this.springs.has(el)) {
        this.springs.set(el, { el, type, bounds: el.getBoundingClientRect(), active: true,
          current: { x: 0, y: 0, rx: 0, ry: 0, scale: 1 }, velocity: { x: 0, y: 0, rx: 0, ry: 0, scale: 0 }, target: { x: 0, y: 0, rx: 0, ry: 0, scale: 1 } });
      }
      return this.springs.get(el);
    }

    resetSpring(s) {
      s.active = false; s.bounds = null;
      Object.assign(s.target, { x: 0, y: 0, rx: 0, ry: 0, scale: 1 });
      s.el.style.setProperty('--vx-glare', '0');
    }

    pointerMove(event) {
      if (event.pointerType === 'touch') { this.touchMove(event); return; }
      if (reduced()) return;
      const p = this.pointer;
      p.present = true; p.clientX = event.clientX; p.clientY = event.clientY;
      p.x = (event.clientX / this.width - .5) * 2;
      p.y = (event.clientY / this.height - .5) * 2;
      if (this.drag && event.pointerId === this.drag.id) {
        const d = this.drag, delta = event.clientX - d.startX;
        if (Math.abs(delta) > 7 && !d.active) {
          d.active = true; d.row.classList.add('vx-dragging');
          d.row.setPointerCapture?.(d.id);
        }
        if (d.active) {
          const now = performance.now();
          d.velocity = (d.lastX - event.clientX) / Math.max(1, now - d.lastTime) * 16.67;
          d.row.scrollLeft = d.startScroll - delta;
          d.lastX = event.clientX; d.lastTime = now;
        }
      }
      const el = event.target instanceof Element ? event.target : null;
      const card = el?.closest('.poster-button,.plan-card,.feature-box,.channel-card,.stat-card,.quick-action');
      const magnet = el?.closest('.btn,.icon-btn,.vx-scene-tab');
      if (!this.drag?.active) {
        for (const [target, type] of [[card, 'card'], [magnet, 'magnet']]) {
          if (!target || target.disabled || !this.root.contains(target)) continue;
          const spring = this.springFor(target, type);
          const r = spring.bounds || (spring.bounds = target.getBoundingClientRect());
          const x = clamp((event.clientX - r.left) / r.width, 0, 1), y = clamp((event.clientY - r.top) / r.height, 0, 1);
          spring.active = true;
          const poster = target.matches('.poster-button');
          Object.assign(spring.target, type === 'magnet'
            ? { x: (x - .5) * 17, y: (y - .5) * 13, rx: 0, ry: 0, scale: 1.035 }
            : { x: 0, y: poster ? -8 : -4, rx: (.5 - y) * (poster ? 17 : 6), ry: (x - .5) * (poster ? 21 : 7), scale: poster ? 1.035 : 1.012 });
          target.style.setProperty('--vx-light-x', `${(x * 100).toFixed(1)}%`);
          target.style.setProperty('--vx-light-y', `${(y * 100).toFixed(1)}%`);
          target.style.setProperty('--vx-glare', '1');
        }
      }
      const live = el?.closest('.live-banner');
      if (live) {
        const r = live.getBoundingClientRect();
        live.style.setProperty('--vx-light-x', `${(event.clientX - r.left) / r.width * 100}%`);
        live.style.setProperty('--vx-light-y', `${(event.clientY - r.top) / r.height * 100}%`);
      }
      this.cursor?.classList.toggle('vx-over', !!el?.closest('a,button,summary'));
      this.cursor?.classList.toggle('vx-drag', !!el?.closest('.poster-row') && !el?.closest('.poster-button'));
      this.wake();
    }

    pointerDown(event) {
      if (event.pointerType === 'touch') { this.touchStart(event); return; }
      if (reduced() || event.pointerType !== 'mouse' || event.button !== 0) return;
      const row = event.target.closest('.poster-row');
      if (!row) return;
      this.inertia = null;
      this.drag = { id: event.pointerId, row, startX: event.clientX, startScroll: row.scrollLeft, lastX: event.clientX, lastTime: performance.now(), velocity: 0, active: false };
    }

    pointerUp(event) {
      if (event.pointerType === 'touch') { this.touchEnd(event); return; }
      const d = this.drag;
      if (!d || d.id !== event.pointerId) return;
      if (d.active) {
        this.lastDragTime = performance.now();
        if (d.row.hasPointerCapture?.(d.id)) d.row.releasePointerCapture(d.id);
        this.inertia = { row: d.row, velocity: performance.now() - d.lastTime > 90 ? 0 : clamp(d.velocity, -45, 45) };
      }
      this.drag = null;
      this.wake();
    }

    touchStart(event) {
      if (this.touchGesture) return; // Let the browser own multitouch/pinch zoom.
      const target = event.target instanceof Element ? event.target : null;
      const scene = target?.closest('.vx-stage,.vx-device-scene');
      const card = target?.closest('.poster-button,.plan-card,.feature-box,.channel-card');
      const button = target?.closest('.btn,.pill,.vx-scene-tab,.vx-device-options button,.icon-btn');
      this.touchGesture = { id: event.pointerId, startX: event.clientX, startY: event.clientY,
        x: event.clientX, y: event.clientY, scene, card, axis: null,
        initialScene: this.stagePosition, device: this.deviceLab?.dataset.screen };
      if (reduced()) return;
      if (card) {
        const s = this.springFor(card, 'card'), r = card.getBoundingClientRect();
        Object.assign(s.target, { scale: .975, x: 0, y: 0, rx: (0.5 - (event.clientY-r.top)/r.height)*10, ry: ((event.clientX-r.left)/r.width-.5)*12 });
        card.style.setProperty('--vx-glare', '1');
        card.style.setProperty('--vx-light-x', `${(event.clientX-r.left)/r.width*100}%`);
        card.style.setProperty('--vx-light-y', `${(event.clientY-r.top)/r.height*100}%`);
      }
      if (button) this.ripple(button, { detail: 1, clientX: event.clientX, clientY: event.clientY });
      if (target?.closest('.hero') && !target.closest('a,button')) {
        this.pointer.x = (event.clientX / this.width - .5) * 2;
        this.pointer.y = (event.clientY / this.height - .5) * 2;
        this.touchPulse = { x: event.clientX, y: event.clientY + this.scroll, start: performance.now() };
      }
      this.wake();
    }

    touchMove(event) {
      const gesture = this.touchGesture;
      if (!gesture || gesture.id !== event.pointerId) return;
      gesture.x = event.clientX; gesture.y = event.clientY;
      const dx = gesture.x - gesture.startX, dy = gesture.y - gesture.startY;
      if (!gesture.axis && Math.hypot(dx, dy) > 9) gesture.axis = Math.abs(dx) > Math.abs(dy) * 1.2 ? 'x' : 'y';
      if (gesture.axis === 'y') {
        if (gesture.card && this.springs.has(gesture.card)) this.resetSpring(this.springs.get(gesture.card));
        return;
      }
      if (gesture.axis === 'x' && gesture.scene?.matches('.vx-stage')) {
        this.manualScene = { index: clamp(gesture.initialScene - dx / 220, 0, 2), scroll: this.scroll };
        this.stageTarget = this.manualScene.index;
        if (reduced()) { this.stagePosition = this.stageTarget; this.drawStage(true); }
      }
      this.wake();
    }

    touchEnd(event) {
      const gesture = this.touchGesture;
      if (!gesture || gesture.id !== event.pointerId) return;
      const dx = gesture.x - gesture.startX;
      if (gesture.scene && gesture.axis === 'x' && event.type !== 'pointercancel') {
        this.lastDragTime = performance.now();
        if (gesture.scene.matches('.vx-stage')) {
          const index = Math.abs(dx) > 35 ? Math.round(gesture.initialScene) + (dx < 0 ? 1 : -1) : Math.round(gesture.initialScene);
          this.chooseScene(clamp(index, 0, 2), true);
        } else {
          const names = ['desktop','tablet','phone'], initial = names.indexOf(gesture.device);
          this.chooseDevice(names[clamp(initial + (Math.abs(dx) > 35 ? dx < 0 ? 1 : -1 : 0), 0, 2)]);
        }
      } else if (gesture.scene?.matches('.vx-stage') && gesture.axis === 'x') {
        this.chooseScene(Math.round(gesture.initialScene), true);
      }
      if (gesture.card && this.springs.has(gesture.card)) this.resetSpring(this.springs.get(gesture.card));
      this.touchGesture = null;
      this.pointer.x = this.pointer.y = 0;
      this.wake();
    }

    ripple(el, event) {
      if (reduced()) return;
      const rect = el.getBoundingClientRect(), ripple = document.createElement('span');
      const diameter = Math.max(rect.width, rect.height) * 2;
      ripple.className = 'vx-ripple'; ripple.setAttribute('aria-hidden', 'true');
      Object.assign(ripple.style, { left: `${event.detail ? event.clientX - rect.left : rect.width / 2}px`, top: `${event.detail ? event.clientY - rect.top : rect.height / 2}px`, width: `${diameter}px`, height: `${diameter}px` });
      el.append(ripple);
      ripple.animate([{ scale: '.02', opacity: .8 }, { scale: '1', opacity: 0 }], { duration: 750, easing: 'cubic-bezier(.2,.6,.3,1)' }).finished.then(() => ripple.remove(), () => ripple.remove());
    }

    chooseScene(index, manual = false) {
      if (!this.story) return;
      if (manual) this.manualScene = { index, scroll: this.scroll };
      this.stageTarget = index;
      this.setSceneContent(index);
      if (reduced()) { this.stagePosition = index; this.drawStage(true); }
      this.wake();
    }

    setSceneContent(index) {
      if (index === this.sceneIndex) return;
      this.sceneIndex = index;
      const themes = [
        { color: '#f43e58', text: 'Explorar filmes', href: '/filmes' },
        { color: '#a272ef', text: 'Encontrar minha próxima série', href: '/series' },
        { color: '#e65067', text: 'Descobrir a TV ao vivo', href: '/tv' }
      ];
      const theme = themes[index];
      this.story.style.setProperty('--vx-stage-accent', theme.color);
      this.sceneTabs.forEach((tab, i) => { tab.setAttribute('aria-selected', String(i === index)); tab.tabIndex = i === index ? 0 : -1; });
      this.sceneCards.forEach((card, i) => card.classList.toggle('vx-active', i === index));
      const panel = select('#vx-scene-description', this.story), link = select('.vx-scene-link', this.story);
      panel.setAttribute('aria-labelledby', `vx-tab-${index}`);
      link.href = theme.href; select('span', link).textContent = theme.text;
      select('.vx-story-counter strong', this.story).textContent = `0${index + 1}`;
      this.animate(panel, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 500 });
    }

    drawStage(force = false) {
      if (!this.story) return;
      const mobile = this.width < 650;
      const progress = clamp((this.scroll - this.storyTop + this.height * .26) / Math.max(1, this.storyHeight - this.pinHeight + this.height * .15));
      if (this.manualScene && Math.abs(this.scroll - this.manualScene.scroll) > this.height * .2) this.manualScene = null;
      if (this.manualScene) this.stageTarget = this.manualScene.index;
      else if (!reduced()) this.stageTarget = smoothstep(clamp((progress - .13) / .74)) * 2;
      this.setSceneContent(Math.round(this.stageTarget));
      if (force || reduced()) this.stagePosition = this.stageTarget;
      this.story.style.setProperty('--vx-story-progress', String(Math.max(.06, progress)));
      const spread = mobile ? 178 : this.width < 1000 ? 245 : 295;
      const px = reduced() ? 0 : this.pointer.sx * (mobile ? 0 : 10);
      const py = reduced() ? 0 : this.pointer.sy * (mobile ? 0 : 5);
      for (let i = 0; i < this.sceneCards.length; i++) {
        const distance = i - this.stagePosition, abs = Math.abs(distance);
        const x = distance * spread + px;
        const z = -abs * (mobile ? 145 : 200);
        const y = abs * 12 + py;
        const rotate = clamp(distance * -29, -47, 47);
        const scale = 1 - Math.min(abs, 2) * .08;
        const card = this.sceneCards[i];
        card.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,${z.toFixed(2)}px) rotateY(${rotate.toFixed(2)}deg) rotateZ(${(distance * 2).toFixed(2)}deg) scale(${scale.toFixed(3)})`;
        card.style.opacity = String(clamp(1 - abs * .28, .2, 1));
        card.style.zIndex = String(10 - Math.round(abs * 3));
      }
    }

    drawParticles(now, delta) {
      if (!this.ctx || this.scroll > this.heroHeight + 50) return;
      const ctx = this.ctx, w = this.width, h = this.heroHeight;
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const px = this.pointer.clientX, py = this.pointer.clientY + this.scroll;
      let connections = 0;
      for (const p of this.particles) {
        p.y -= p.speed * delta / h;
        if (p.y < -.04) { p.y = 1.04; p.x = Math.random(); }
        const drift = Math.sin(now * .00018 + p.phase) * 12;
        let x = p.x * w + this.pointer.sx * p.z * -29 + drift;
        let y = p.y * h + this.pointer.sy * p.z * -18 + this.smoothScroll * p.z * .16;
        if (this.touchPulse) {
          const age = (now - this.touchPulse.start) / 1000;
          const tx = x - this.touchPulse.x, ty = y - this.touchPulse.y, dist = Math.hypot(tx, ty);
          const wave = Math.exp(-Math.pow((dist - age * 240) / 65, 2)) * Math.max(0, 1 - age / 1.8) * 35;
          if (dist > 1) { x += tx / dist * wave; y += ty / dist * wave; }
        }
        const dx = x - px, dy = y - py, distance = Math.hypot(dx, dy);
        if (this.pointer.present && distance < 160 && distance > 1) {
          const push = (1 - distance / 160) * 20 * p.z;
          x += dx / distance * push; y += dy / distance * push;
          if (connections++ < 12 && distance < 105) {
            ctx.strokeStyle = `rgba(255,115,137,${(.12 * (1 - distance / 105)).toFixed(3)})`;
            ctx.lineWidth = .6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(px, py); ctx.stroke();
          }
        }
        const twinkle = .35 + .45 * (Math.sin(now * .0007 + p.phase) * .5 + .5);
        ctx.fillStyle = p.red ? `rgba(255,94,120,${twinkle * p.z})` : `rgba(255,227,211,${twinkle * p.z * .7})`;
        ctx.beginPath(); ctx.arc(x, y, p.radius * p.z, 0, Math.PI * 2); ctx.fill();
        if (p.red && p.z > .7) {
          ctx.strokeStyle = `rgba(255,102,131,${twinkle * .15})`;
          ctx.lineWidth = .65; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - this.pointer.sx * 4, y + 9 * p.z); ctx.stroke();
        }
      }
      if (this.touchPulse) {
        const age = (now - this.touchPulse.start) / 1000;
        if (age > 1.8) this.touchPulse = null;
        else {
          ctx.strokeStyle = `rgba(255,131,154,${.24 * (1-age/1.8)})`;
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(this.touchPulse.x, this.touchPulse.y, age*240+5, 0, Math.PI*2); ctx.stroke();
        }
      }
    }

    tick(now) {
      this.frameId = 0;
      if (!this.alive || document.hidden) return;
      if (this.layoutDirty) this.measure();
      const delta = clamp((now - (this.lastFrame || now - 16.67)) / 16.67, .3, 2);
      this.lastFrame = now;
      document.documentElement.style.setProperty('--vx-page-progress', String(clamp(this.scroll / this.documentHeight)));
      document.documentElement.classList.toggle('vx-scrolled', this.scroll > 38);
      if (reduced()) { this.drawStage(true); return; }
      const smooth = 1 - Math.pow(.9, delta);
      this.pointer.sx = lerp(this.pointer.sx, this.pointer.x, smooth);
      this.pointer.sy = lerp(this.pointer.sy, this.pointer.y, smooth);
      this.smoothScroll = lerp(this.smoothScroll, this.scroll, 1 - Math.pow(.84, delta));
      const heroVisible = this.hero && this.scroll < this.heroHeight + 50;
      const storyVisible = this.story && this.scroll + this.height > this.storyTop && this.scroll < this.storyTop + this.storyHeight;
      if (heroVisible) {
        const scrollProgress = clamp(this.smoothScroll / this.heroHeight);
        const intro = 1 - Math.pow(1 - clamp((now - this.introTime) / 2200), 4);
        const x = this.pointer.sx * -21;
        const y = this.pointer.sy * -13 + this.smoothScroll * .22;
        this.heroArt.style.setProperty('--vx-hx', `${x.toFixed(2)}px`);
        this.heroArt.style.setProperty('--vx-hy', `${y.toFixed(2)}px`);
        this.heroArt.style.setProperty('--vx-hscale', (1.045 + (1 - intro) * .13 + scrollProgress * .12).toFixed(4));
        this.heroCopy.style.setProperty('--vx-copy-x', `${(this.pointer.sx * 6).toFixed(2)}px`);
        this.heroCopy.style.setProperty('--vx-copy-y', `${(this.pointer.sy * 4 + this.smoothScroll * -.08).toFixed(2)}px`);
        this.caption.style.setProperty('--vx-caption-x', `${(this.pointer.sx * -12).toFixed(2)}px`);
        this.caption.style.setProperty('--vx-caption-y', `${(this.pointer.sy * -8 - this.smoothScroll * .1).toFixed(2)}px`);
        this.drawParticles(now, delta);
      }
      if (storyVisible || Math.abs(this.stagePosition - this.stageTarget) > .001) {
        this.stagePosition = lerp(this.stagePosition, this.stageTarget, 1 - Math.pow(.88, delta));
        this.drawStage();
      }
      let springsActive = false;
      for (const [el, s] of this.springs) {
        if (!el.isConnected) { this.springs.delete(el); continue; }
        let unsettled = false;
        for (const k of ['x','y','rx','ry','scale']) {
          const acceleration = (s.target[k] - s.current[k]) * .105;
          s.velocity[k] = (s.velocity[k] + acceleration * delta) * Math.pow(.69, delta);
          s.current[k] += s.velocity[k] * delta;
          if (Math.abs(s.target[k] - s.current[k]) > .003 || Math.abs(s.velocity[k]) > .003) unsettled = true;
        }
        const c = s.current;
        el.style.transform = `perspective(850px) translate3d(${c.x.toFixed(3)}px,${c.y.toFixed(3)}px,0) rotateX(${c.rx.toFixed(3)}deg) rotateY(${c.ry.toFixed(3)}deg) scale(${c.scale.toFixed(4)})`;
        springsActive ||= unsettled;
        if (!unsettled && !s.active) { el.style.removeProperty('transform'); this.springs.delete(el); }
      }
      if (this.inertia) {
        const m = this.inertia, before = m.row.scrollLeft;
        m.row.scrollLeft += m.velocity * delta; m.velocity *= Math.pow(.935, delta);
        if (Math.abs(m.velocity) < .3 || Math.abs(before - m.row.scrollLeft) < .2) { m.row.classList.remove('vx-dragging'); this.inertia = null; }
      }
      let cursorMoving = false;
      if (this.cursor && finePointer.matches) {
        this.cursorX ??= this.pointer.clientX; this.cursorY ??= this.pointer.clientY;
        this.cursorX = lerp(this.cursorX, this.pointer.clientX, 1 - Math.pow(.77, delta));
        this.cursorY = lerp(this.cursorY, this.pointer.clientY, 1 - Math.pow(.77, delta));
        this.cursor.style.opacity = this.pointer.present && !select('dialog[open]') ? '1' : '0';
        this.cursor.style.transform = `translate3d(${this.cursorX.toFixed(2)}px,${this.cursorY.toFixed(2)}px,0) translate(-50%,-50%)`;
        cursorMoving = Math.abs(this.cursorX - this.pointer.clientX) + Math.abs(this.cursorY - this.pointer.clientY) > .2;
      }
      const moving = Math.abs(this.smoothScroll - this.scroll) > .1 || Math.abs(this.stagePosition - this.stageTarget) > .002 || Math.abs(this.pointer.sx - this.pointer.x) > .002;
      if (heroVisible || springsActive || cursorMoving || moving || this.inertia) this.wake();
    }

    preferenceChanged() {
      this.animations.forEach(a => a.cancel()); this.animations.clear();
      selectAll('.vx-pending', this.root).forEach(el => el.classList.remove('vx-pending'));
      this.springs.forEach(s => { s.el.style.removeProperty('transform'); s.el.style.setProperty('--vx-glare', '0'); });
      this.springs.clear();
      this.introOverlay?.remove();
      if (this.drag) this.drag.row.classList.remove('vx-dragging');
      if (this.inertia) this.inertia.row.classList.remove('vx-dragging');
      this.drag = this.inertia = null;
      this.touchGesture = this.touchPulse = null;
      this.pointer.x = this.pointer.y = this.pointer.sx = this.pointer.sy = 0;
      this.layoutDirty = true;
      this.wake();
    }

    wake() { if (!this.frameId && this.alive && !document.hidden) this.frameId = requestAnimationFrame(t => this.tick(t)); }
    sleep() { cancelAnimationFrame(this.frameId); this.frameId = 0; this.lastFrame = 0; }
    destroy() {
      this.alive = false; this.sleep(); this.abort.abort();
      this.resizeObserver?.disconnect(); this.mutationObserver?.disconnect(); this.revealObserver?.disconnect();
      this.animations.forEach(a => a.cancel()); this.animations.clear();
      this.counterFrames?.forEach(id => cancelAnimationFrame(id));
      this.springs.forEach(s => s.el.style.removeProperty('transform')); this.springs.clear();
      this.introOverlay?.remove();
      if (this.cursor) this.cursor.style.opacity = '0';
    }
  }

  function mount() {
    createChrome();
    document.documentElement.classList.add('vx-enabled');
    engine?.destroy();
    const community = location.pathname.startsWith('/comunidade') || location.pathname.startsWith('/admin');
    document.documentElement.classList.toggle('cm-active',community);
    if(community){engine=null;return;}
    engine = new MotionEngine(select('#app'));
  }

  function transition() {
    if (reduced() || location.pathname.startsWith('/comunidade') || location.pathname.startsWith('/admin')) return { finish() {} };
    const overlay = document.createElement('div');
    overlay.className = 'vx-transition'; overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML = '<div class="vx-transition-panel"></div>';
    document.body.append(overlay);
    const panel = overlay.firstElementChild;
    const watchdog = setTimeout(() => overlay.remove(), 3500);
    const enter = panel.animate([{ transform: 'translateX(-102%) skewX(-5deg)' }, { transform: 'translateX(0) skewX(0)' }], { duration: 300, easing: 'cubic-bezier(.7,0,.2,1)', fill: 'forwards' });
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      enter.finished.catch(() => {}).then(() => {
        if (reduced()) { clearTimeout(watchdog); overlay.remove(); return; }
        const out = panel.animate([{ transform: 'translateX(0) skewX(0)' }, { transform: 'translateX(104%) skewX(-5deg)' }], { duration: 600, easing: ease, fill: 'forwards' });
        out.finished.catch(() => {}).then(() => { clearTimeout(watchdog); overlay.remove(); });
      });
    };
    // Even a failed/hung request must never leave an overlay covering the interface.
    setTimeout(finish, 2500);
    return { finish };
  }

  window.VyraMotion = {
    mount,
    unmount() { engine?.destroy(); engine = null; },
    transition,
    getStatus() { return { mounted: !!engine, paused: reduced(), animationCount: engine?.animations.size || 0, springCount: engine?.springs.size || 0, frameScheduled: !!engine?.frameId, scene: engine?.sceneIndex ?? -1, particles: engine?.particles?.length || 0 }; }
  };
  document.addEventListener('DOMContentLoaded', () => {
    createChrome();
    if (select('#app #main') && !engine) mount();
  });
})();
