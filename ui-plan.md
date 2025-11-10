# SamePage — UI Wow Plan (Hackathon Judges Edition)

This document outlines a focused, high‑leverage plan to make SamePage feel like a polished, trustworthy, “hackathon‑winning” product. It prioritizes what judges notice first: clarity, speed, motion, trust signals, and a crisp story.

## Objectives
- Instant understanding: What it does, how to try, why it’s credible.
- Crisp visuals with tasteful motion and zero clutter.
- Fast interactions with visible progress and great empty/error states.
- Clear evidence and transparency (debug and ADK trace) without overwhelming.

## Design Principles
- Minimal, opinionated UI; one primary action per screen.
- Evidence over magic: show how we scored (toggle), label subscores.
- Motion with purpose: guide attention, never distract.
- Mobile‑first; looks outstanding on a projector.
- Accessibility by default: contrast, keyboard/focus, ARIA.

## Visual Identity
- Color system (Tailwind):
  - Primary: `blue-600` (actions), `blue-700` hover
  - States: Aligned `emerald-600`, Partial `amber-600`, Misaligned `rose-600`
  - Surfaces: `white` cards on `slate-50` background, text `slate-900`
- Typography:
  - Display: system stack with medium/semibold weights (no webfont to keep LCP low)
  - Body: 16–18px base; line-height 1.5–1.65
- Iconography: Simple outline icons (Heroicons) for consensus/divergence; small, consistent 18–20px.

## App Shell & Navigation
- Keep the current simple shell; add a slim top ribbon for status where useful (e.g., “Agents: ADK orchestrated” with tooltip).
- Progressive disclosure: public pitch on landing, then partner inputs, then result card with evidence toggles.

## Page‑by‑Page Plan

### 1) Landing (`templates/index.html`)
- Add a succinct hero: headline + one‑line subhead + “Try Now” CTA scrolling to links.
- Add “Copy” buttons next to A/B links with tooltip “Copied!”.
- “How it works” 3‑step row: Enter, Compare, Align (with small icons).
- Trust strip: “Built on Google Cloud Run + Vertex AI” badges; link to README.

### 2) Partner Form (`templates/form.html`)
- Section titles with small helper text (“1–2 sentences”, examples behind a collapsible).
- Inline validation hints (character count, required markers).
- Microcopy for tone: quick suggestions as pills (“relieved”, “stressed”, “calm”). Click to fill.
- Consent checkbox stays, add brief privacy line under it.

### 3) Waiting (`templates/waiting.html`)
- Replace static text with animated pulse + playful copy (“Brewing your alignment…”).
- Add a progress shim: 3 steps with the current one pulsing: Save → Score → Explain.

### 4) Result (`templates/result.html`)
- Replace numeric score header with an animated radial gauge + label chip.
- Group consensus/divergence into cards with subtle icons; limit to 3 each.
- Themes as pill chips; wrap nicely.
- Recommendations block with “Copy all” and tiny “Apply later” note.
- Evidence toggle remains; label “Why this score?” and show subscores table‑like.
- ADK badge with tooltip that links to `/__diag/adk` in a new tab.
- Celebration confetti when `label == 'Aligned'`.

## High‑Impact Components (with snippets)

### Animated Radial Gauge (Score)
Use a lightweight SVG. Animate stroke dashoffset on load.

```html
<!-- Gauge container -->
<div class="relative w-32 h-32">
  <svg viewBox="0 0 120 120" class="w-32 h-32">
    <circle cx="60" cy="60" r="52" class="fill-none stroke-slate-200" stroke-width="12" />
    <!-- Progress -->
    <circle id="gauge" cx="60" cy="60" r="52"
            class="fill-none stroke-blue-600 transition-[stroke-dashoffset] duration-[1200ms] ease-out"
            stroke-linecap="round" stroke-width="12"
            stroke-dasharray="327" stroke-dashoffset="327" />
  </svg>
  <div class="absolute inset-0 grid place-items-center">
    <div class="text-2xl font-semibold" id="gauge-val">72</div>
  </div>
  <script>
    // Animate gauge to N% of 100 (dasharray ≈ 2πr)
    (function(){
      const score = Number(document.querySelector('[data-score]')?.dataset.score || 72);
      const dash = 327; // 2 * Math.PI * 52
      const el = document.getElementById('gauge');
      if (!el) return;
      const offset = dash - (dash * Math.max(0, Math.min(100, score))) / 100;
      requestAnimationFrame(() => { el.style.strokeDashoffset = offset; });
    })();
  </script>
  <!-- Set container: <div data-score="{{ score }}"> to drive JS -->
```

### Label Chip (State)

```html
<span class="inline-block px-3 py-1 rounded-full text-white"
      data-label="{{ label }}"
      x-data
      :class="{
        'bg-emerald-600': $el.dataset.label==='Aligned',
        'bg-amber-600': $el.dataset.label==='Partial',
        'bg-rose-600': $el.dataset.label==='Misaligned'
      }">
  {{ label }}
</span>
```

### Copy Buttons (Links & Recommendations)

```html
<button class="text-xs px-2 py-1 bg-slate-200 rounded hover:bg-slate-300" onclick="
  navigator.clipboard.writeText(document.getElementById('copy-src').value).then(()=>{
    const b = this; b.textContent='Copied!'; setTimeout(()=>b.textContent='Copy', 900);
  });
">Copy</button>
```

### Confetti (Aligned Celebration)
Pure JS, no external libs; draw 50 particles for 800ms.

```html
<canvas id="confetti" class="fixed inset-0 pointer-events-none" style="display:none"></canvas>
<script>
  (function(){
    const isAligned = '{{ label }}' === 'Aligned';
    if (!isAligned) return;
    const c = document.getElementById('confetti');
    const ctx = c.getContext('2d');
    const resize = () => { c.width = innerWidth; c.height = innerHeight; };
    resize(); window.addEventListener('resize', resize);
    c.style.display='block';
    const parts = Array.from({length:50},() => ({
      x: Math.random()*c.width, y: -10-Math.random()*c.height/2,
      r: 3+Math.random()*5, vy: 2+Math.random()*3,
      col: ['#059669','#10b981','#34d399','#6ee7b7'][Math.floor(Math.random()*4)]
    }));
    const t0=performance.now();
    const step=(t)=>{
      const dt=t-t0; if (dt>900){ c.style.display='none'; return; }
      ctx.clearRect(0,0,c.width,c.height);
      parts.forEach(p=>{ p.y+=p.vy; ctx.fillStyle=p.col; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,6.283); ctx.fill(); });
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  })();
</script>
```

## Trust, Transparency, and Credibility
- Privacy line always visible; session TTL shown in footer.
- “Built with Google Cloud Run + Vertex AI” captions; link to README.
- ADK badge: small pill “Agents: ADK” with tooltip; link to `/__diag/adk`.
- Evidence toggle default collapsed; clear labels for subscores.

## Accessibility Checklist
- Color contrast: WCAG AA for text and interactive elements.
- Keyboard: visible focus rings (`outline`, `ring-2 ring-offset-2`), tab order logical.
- ARIA: `aria-live="polite"` for waiting status; labels for form inputs; `role="status"` for loaders.
- Reduced motion: respect `prefers-reduced-motion` (skip gauge animation/confetti).

## Performance Targets (Lighthouse)
- LCP < 1.5s on fast 3G; TTI < 2.0s.
- No webfonts; Tailwind CDN is fine; minimize custom JS.
- Preload critical HTML; defer non‑critical scripts; compress SVG.

## Implementation Checklist (by file)

1) `templates/index.html`
   - Add hero section, “Try Now” CTA, and 3‑step explainer.
   - Add copy buttons for A/B links with tooltip feedback.
   - Add small trust strip linking to README.

2) `templates/form.html`
   - Helper texts, example collapsible, tone suggestion pills.
   - Inline validation (simple JS) and character counters.

3) `templates/waiting.html`
   - Animated pulse dots, step progress (Save → Score → Explain).
   - `aria-live` region to announce progress.

4) `templates/result.html`
   - Insert animated radial gauge and state chip.
   - Icons for consensus/divergence headings.
   - Copy‑all button for recommendations.
   - Evidence toggle renamed to “Why this score?” with subscores list.
   - ADK badge with tooltip and link to `/__diag/adk`.
   - Confetti canvas & reduced‑motion check.

5) `base.html`
   - Optional dark mode toggle with `prefers-color-scheme` support.

6) Microinteractions
   - Copy to clipboard (links and recommendations)
   - Gauge animation on appear
   - Confetti on Aligned

## Demo Storyboard (3 minutes)
1. Hook (15s): “Misunderstandings persist after talks.”
2. Inputs (45s): A/B forms; submit → waiting pulses.
3. Result (60s): Animated gauge to 70 (Partial); show consensus/divergence; open “Why this score?”
4. Improve (45s): Apply a recommendation; resubmit; gauge climbs, confetti.
5. Cloud (15s): ADK badge tooltip + `__diag/adk`; quick Infra slide or terminal.

## Nice‑to‑Haves (time‑permitting)
- “Share result” image export (HTML to canvas) for README/Twitter.
- PWA install banner for mobile demos.
- Keyboard shortcut: `?` to open Evidence/Agents panels.

## Risks & Mitigations
- LLM latency: animated progress and timeout messaging; deterministic fallback copy.
- Projectors wash out colors: keep high contrast; avoid light text on white.
- Network dead zones: offline fallback demo state (already supported in app when Firestore/Vertex absent).

## Acceptance Criteria
- Gauge animates; copy buttons work; confetti on Aligned.
- Lighthouse ≥ 90 Perf/Best/SEO and ≥ 95 Accessibility on Result page.
- Judges can discover transparency: Evidence + ADK badge + diag link.
- Mobile and desktop look intentional and refined.

