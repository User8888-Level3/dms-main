/* ═══════════════════════════════════════════════════════════════════════════
   HARV BALU — portfolio front-end behaviour.
   1. Scroll + mouse parallax on landing collage tiles (data-speed).
   2. Ignition reveals via IntersectionObserver (.tile / .ph / .station).
   3. Meridian ink — the survey line draws itself as the visitor descends.
   4. Lightbox v2 — the viewing instrument: frame counter, epoch caption,
      direction-aware crossfade travel, swipe, click zones, arrow keys.
   5. ABOUT overlay open/close (+ deep link via #about).
   Vanilla ES2020, no frameworks, no build step. Honours
   prefers-reduced-motion throughout (paired CSS in static/style.css).
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const doc = document;
  const root = doc.documentElement;
  const mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const mqWide = window.matchMedia('(min-width: 641px)'); // collage is stacked flow below this

  const onMqChange = (mq, fn) => {
    if (typeof mq.addEventListener === 'function') mq.addEventListener('change', fn);
    else if (typeof mq.addListener === 'function') mq.addListener(fn); // older Safari
  };

  /* ─── year stamps (footers) ────────────────────────────────────────────── */

  doc.querySelectorAll('[data-year]').forEach((el) => {
    el.textContent = String(new Date().getFullYear());
  });

  /* ─── ignition reveals ─────────────────────────────────────────────────── */

  const risers = Array.from(doc.querySelectorAll('.tile, .ph, .station'));
  if (risers.length) {
    const reveal = (el, delayMs) => {
      const img = el.querySelector('img'); // tiles/frames animate their img
      if (delayMs) {
        el.style.transitionDelay = delayMs + 'ms';
        if (img) img.style.transitionDelay = delayMs + 'ms';
        // clear the delay once the entrance is done so hovers stay snappy
        window.setTimeout(() => {
          el.style.transitionDelay = '';
          if (img) img.style.transitionDelay = '';
        }, 1300 + delayMs);
      }
      el.classList.add('is-in');
    };

    if (mqReduce.matches || !('IntersectionObserver' in window)) {
      risers.forEach((el) => el.classList.add('is-in'));
    } else {
      let seen = 0;
      const io = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          reveal(entry.target, (seen++ % 10) * 45);
          io.unobserve(entry.target);
        }
      }, { rootMargin: '0px 0px -6% 0px', threshold: 0.08 });
      risers.forEach((el) => io.observe(el));
    }
  }

  /* ─── meridian ink — the line draws with the descent ───────────────────── */

  const ink = doc.querySelector('.meridian-ink');
  const meridian = doc.querySelector('.meridian');
  if (ink && meridian && !mqReduce.matches) {
    let inkQueued = false;
    const paintInk = () => {
      inkQueued = false;
      const r = meridian.getBoundingClientRect();
      const vh = window.innerHeight;
      // progress of the viewport's lower third through the meridian's box
      const p = (vh * 0.72 - r.top) / r.height;
      const clamped = Math.max(0, Math.min(1, p));
      ink.style.transform = 'scaleY(' + clamped.toFixed(4) + ')';
    };
    const queueInk = () => {
      if (!inkQueued) { inkQueued = true; window.requestAnimationFrame(paintInk); }
    };
    window.addEventListener('scroll', queueInk, { passive: true });
    window.addEventListener('resize', queueInk, { passive: true });
    paintInk();
  }

  /* ─── parallax (landing collage) ───────────────────────────────────────── */

  const tiles = Array.from(doc.querySelectorAll('.tile[data-speed]'));
  if (tiles.length) {
    const speeds = tiles.map((t) => {
      const v = parseFloat(t.getAttribute('data-speed'));
      return Number.isFinite(v) ? v : 0.1;
    });
    let mouseX = 0;
    let mouseY = 0;
    let queued = false;
    let bound = false;

    const paint = () => {
      queued = false;
      const sy = window.scrollY || 0;
      for (let i = 0; i < tiles.length; i++) {
        const s = speeds[i];
        const x = mouseX * s * 46;
        const y = sy * s * 0.6 + mouseY * s * 34;
        tiles[i].style.transform =
          'translate3d(' + x.toFixed(2) + 'px,' + y.toFixed(2) + 'px,0)';
      }
    };
    const queue = () => {
      if (!queued) {
        queued = true;
        window.requestAnimationFrame(paint);
      }
    };
    const onScroll = () => queue();
    const onMouse = (e) => {
      mouseX = e.clientX / window.innerWidth - 0.5;
      mouseY = e.clientY / window.innerHeight - 0.5;
      queue();
    };

    const rebind = () => {
      const want = mqWide.matches && !mqReduce.matches;
      if (want && !bound) {
        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('mousemove', onMouse, { passive: true });
        bound = true;
        queue();
      } else if (!want && bound) {
        window.removeEventListener('scroll', onScroll);
        window.removeEventListener('mousemove', onMouse);
        bound = false;
        mouseX = 0;
        mouseY = 0;
        tiles.forEach((t) => { t.style.transform = ''; });
      }
    };
    rebind();
    onMqChange(mqWide, rebind);
    onMqChange(mqReduce, rebind);
  }

  /* ─── ABOUT overlay ────────────────────────────────────────────────────── */

  const about = doc.getElementById('about');
  if (about && about.hasAttribute('hidden')) {
    const plus = doc.querySelector('[data-about-toggle]');
    let lastFocus = null;

    const openAbout = () => {
      lastFocus = doc.activeElement;
      about.hidden = false;
      root.classList.add('about-open');
      if (plus) plus.setAttribute('aria-expanded', 'true');
      const closer = about.querySelector('[data-about-close]');
      if (closer) closer.focus();
    };
    const closeAbout = () => {
      about.hidden = true;
      root.classList.remove('about-open');
      if (plus) plus.setAttribute('aria-expanded', 'false');
      if (window.location.hash === '#about') {
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
      }
      if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    };

    doc.querySelectorAll('[data-about-open]').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        openAbout();
      });
    });
    doc.querySelectorAll('[data-about-close]').forEach((el) => {
      el.addEventListener('click', () => {
        if (el.tagName === 'BUTTON') closeAbout();
        else root.classList.remove('about-open');
      });
    });
    if (plus) {
      plus.addEventListener('click', () => {
        if (about.hidden) openAbout();
        else closeAbout();
      });
    }
    doc.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !about.hidden) closeAbout();
    });
    if (window.location.hash === '#about') openAbout();
  }

  /* ─── lightbox v2 — the viewing instrument ─────────────────────────────── */

  const items = Array.from(doc.querySelectorAll('a.ph'));
  if (items.length) {
    const SWAP_MS = 560;               // matches .lb-img transition in CSS
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const pad3 = (n) => String(n).padStart(3, '0');
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const epochOf = (a) => {
      const iso = (a.getAttribute('data-taken') || '').slice(0, 10);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return '';
      const m = parseInt(iso.slice(5, 7), 10);
      return iso.slice(0, 4) + ' · ' + (MONTHS[m - 1] || '') + ' ' +
             String(parseInt(iso.slice(8, 10), 10));
    };
    /* icons are drawn, one stroke system — never font glyphs */
    const icon = (d, w, h) => {
      const s = doc.createElementNS(SVG_NS, 'svg');
      s.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      s.setAttribute('width', String(w));
      s.setAttribute('height', String(h));
      s.setAttribute('aria-hidden', 'true');
      const p = doc.createElementNS(SVG_NS, 'path');
      p.setAttribute('d', d);
      p.setAttribute('fill', 'none');
      p.setAttribute('stroke', 'currentColor');
      p.setAttribute('stroke-width', '1.4');
      s.appendChild(p);
      return s;
    };

    let lb = null;
    let imgs = null;        // [imgA, imgB] — alternate for crossfade travel
    let live = 0;           // index into imgs of the visible frame
    let lbEpoch = null;
    let lbNote = null;
    let lbCount = null;
    let lbClose = null;
    let lbPrev = null;
    let lbNext = null;
    let zonePrev = null;
    let zoneNext = null;
    let idx = -1;
    let opener = null;
    let swapTimer = 0;

    const build = () => {
      lb = doc.createElement('div');
      lb.className = 'lb';
      lb.hidden = true;
      lb.setAttribute('role', 'dialog');
      lb.setAttribute('aria-modal', 'true');
      lb.setAttribute('aria-label', 'Photo viewer');

      lbCount = doc.createElement('div');
      lbCount.className = 'lb-count';
      lbCount.setAttribute('aria-live', 'polite');

      lbClose = doc.createElement('button');
      lbClose.type = 'button';
      lbClose.className = 'lb-btn lb-close';
      lbClose.setAttribute('aria-label', 'Close viewer');
      lbClose.appendChild(icon('M2 2l14 14M16 2L2 16', 18, 18));

      lbPrev = doc.createElement('button');
      lbPrev.type = 'button';
      lbPrev.className = 'lb-btn lb-prev';
      lbPrev.setAttribute('aria-label', 'Previous photo');
      lbPrev.appendChild(icon('M12 2L3 14l9 12', 15, 28));

      lbNext = doc.createElement('button');
      lbNext.type = 'button';
      lbNext.className = 'lb-btn lb-next';
      lbNext.setAttribute('aria-label', 'Next photo');
      lbNext.appendChild(icon('M3 2l9 12-9 12', 15, 28));

      zonePrev = doc.createElement('button');
      zonePrev.type = 'button';
      zonePrev.className = 'lb-zone lb-zone--prev';
      zonePrev.setAttribute('aria-hidden', 'true');
      zonePrev.tabIndex = -1;

      zoneNext = doc.createElement('button');
      zoneNext.type = 'button';
      zoneNext.className = 'lb-zone lb-zone--next';
      zoneNext.setAttribute('aria-hidden', 'true');
      zoneNext.tabIndex = -1;

      const stage = doc.createElement('figure');
      stage.className = 'lb-stage';

      const frame = doc.createElement('div');
      frame.className = 'lb-frame';

      imgs = [doc.createElement('img'), doc.createElement('img')];
      imgs.forEach((im) => {
        im.className = 'lb-img';
        im.alt = '';
        im.decoding = 'async';
        frame.appendChild(im);
      });

      const lbCap = doc.createElement('figcaption');
      lbCap.className = 'lb-cap';
      lbEpoch = doc.createElement('span');
      lbEpoch.className = 'lb-epoch';
      lbCap.appendChild(lbEpoch);

      lbNote = doc.createElement('div');
      lbNote.className = 'lb-note';
      lbNote.hidden = true;

      stage.append(frame, lbCap, lbNote);
      lb.append(lbCount, lbClose, lbPrev, lbNext, zonePrev, zoneNext, stage);
      doc.body.appendChild(lb);

      lbClose.addEventListener('click', close);
      lbPrev.addEventListener('click', () => show(idx - 1, -1));
      lbNext.addEventListener('click', () => show(idx + 1, 1));
      zonePrev.addEventListener('click', () => show(idx - 1, -1));
      zoneNext.addEventListener('click', () => show(idx + 1, 1));
      lb.addEventListener('click', (e) => {
        if (e.target === lb) close(); // the dark itself closes
      });

      /* swipe travel */
      let px = 0, py = 0, pid = -1;
      lb.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'mouse') return;
        pid = e.pointerId; px = e.clientX; py = e.clientY;
      }, { passive: true });
      lb.addEventListener('pointerup', (e) => {
        if (e.pointerId !== pid) return;
        pid = -1;
        const dx = e.clientX - px;
        const dy = e.clientY - py;
        if (Math.abs(dx) > 44 && Math.abs(dx) > Math.abs(dy) * 1.4) {
          if (dx < 0) show(idx + 1, 1);
          else show(idx - 1, -1);
        }
      }, { passive: true });
    };

    /* Direction-aware travel: the incoming frame slides from the direction of
       movement while the outgoing one falls away — both layers, transform +
       opacity only. dir: 1 = next, -1 = prev, 0 = first reveal. */
    const show = (i, dir) => {
      idx = (i + items.length) % items.length;
      const a = items[idx];
      const kind = a.getAttribute('data-kind') || 'image';
      const sha1 = a.getAttribute('data-sha1') || '';

      const out = imgs[live];
      live = 1 - live;
      const inc = imgs[live];

      window.clearTimeout(swapTimer);
      inc.className = 'lb-img';           // reset travel classes
      inc.src = a.href;

      if (mqReduce.matches) {
        // static promise: instant swap, no travel, outgoing gone at once
        inc.classList.add('is-on');
        out.className = 'lb-img';
        out.removeAttribute('src');
      } else {
        if (dir === 1) inc.classList.add('from-next');
        else if (dir === -1) inc.classList.add('from-prev');

        // Commit the travel origin with a forced reflow, then ease on — no
        // requestAnimationFrame: rAF starves in throttled/background contexts
        // and would leave the swap stuck on the outgoing frame. The from-*
        // class is REMOVED as is-on lands: those rules sit later in the
        // cascade and would otherwise pin the frame 34px off-center forever.
        void inc.offsetWidth;
        inc.classList.remove('from-next', 'from-prev');
        inc.classList.add('is-on');
        out.classList.remove('is-on');
        out.classList.add(dir === -1 ? 'to-prev' : 'to-next');
        swapTimer = window.setTimeout(() => {
          out.className = 'lb-img';
          out.removeAttribute('src');
        }, SWAP_MS);
      }

      lbEpoch.textContent = epochOf(a);
      while (lbCount.firstChild) lbCount.removeChild(lbCount.firstChild);
      lbCount.appendChild(doc.createTextNode(pad3(idx + 1) + ' '));
      const total = doc.createElement('span');
      total.className = 'lb-total';
      total.textContent = '/ ' + pad3(items.length);
      lbCount.appendChild(total);

      while (lbNote.firstChild) lbNote.removeChild(lbNote.firstChild);
      if (kind === 'video') {
        lbNote.hidden = false;
        lbNote.appendChild(doc.createTextNode('Video — '));
        if (/^[0-9a-f]{40}$/.test(sha1)) {
          const dl = doc.createElement('a');
          dl.href = '/media/orig/' + sha1;
          dl.textContent = 'download the original';
          lbNote.appendChild(dl);
          lbNote.appendChild(doc.createTextNode(' to play.'));
        } else {
          lbNote.appendChild(doc.createTextNode('download the original to play.'));
        }
      } else {
        lbNote.hidden = true;
      }

      const single = items.length < 2;
      lbPrev.hidden = single;
      lbNext.hidden = single;
      zonePrev.hidden = single;
      zoneNext.hidden = single;

      if (!single) { // pre-warm the neighbours
        [1, -1].forEach((d) => {
          const n = new Image();
          n.src = items[(idx + d + items.length) % items.length].href;
        });
      }
    };

    const open = (i) => {
      if (!lb) build();
      opener = doc.activeElement;
      lb.hidden = false;
      void lb.offsetWidth;                // commit hidden=false, then fade in
      lb.classList.add('is-open');
      root.classList.add('lb-open');
      show(i, 0);
      lbClose.focus();
    };

    const close = () => {
      lb.classList.remove('is-open');
      window.setTimeout(() => {
        lb.hidden = true;
        imgs.forEach((im) => { im.className = 'lb-img'; im.removeAttribute('src'); });
      }, mqReduce.matches ? 0 : 300);
      root.classList.remove('lb-open');
      if (opener && typeof opener.focus === 'function') opener.focus();
    };

    items.forEach((a, i) => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        open(i);
      });
    });

    doc.addEventListener('keydown', (e) => {
      if (!lb || lb.hidden) return;
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowLeft') show(idx - 1, -1);
      else if (e.key === 'ArrowRight') show(idx + 1, 1);
      else if (e.key === 'Tab') {
        // contain focus in the dialog (aria-modal promises it)
        const focusables = [lbClose, lbPrev, lbNext].filter((b) => !b.hidden);
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && doc.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && doc.activeElement === last) {
          e.preventDefault();
          first.focus();
        } else if (!focusables.includes(doc.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  }
})();
