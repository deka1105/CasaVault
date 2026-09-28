# Hyperframes Composition Brief: CasaVault

## Objective
Create a short, polished launch-style brag video for CasaVault — a statute-aware rental record that checks leases against the law and cites its sources or refuses.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 19-22 seconds

## Source Material
- Project root: `/Users/shubhamarundekatey/ClaudeCode/day30/CasaVault`
- Primary files read: `static/index.html`, `static/style.css`, `README.md`, `PLAN.md`
- Product name: CasaVault
- Tagline: "Keep proof of your rental — and know what the law says."
- Key UI moment to recreate: The three-state finding cards (red violation with monospace statute citation) and the agent refusal
- Copy that must appear verbatim:
  - "87% of landlords have a lawyer."
  - "16% of tenants do."
  - "They don't lose because they're wrong."
  - "Deposit exceeds first-year cap" — `68 P.S. § 250.511a(a)`
  - "Deposit waiver clause is void" — `68 P.S. § 250.511a(f)`
  - "No escrow bank disclosed" — `68 P.S. § 250.511b`
  - "How long does he have to return my deposit?"
  - "30 days from move-out." — `68 P.S. § 250.512`
  - "Will I win in court?"
  - "I can't answer that."
  - "Here's who can: Philly Tenant Hotline (267) 443-2500"
  - "Every answer cites a source."
  - "Every refusal routes to a human."
  - "CasaVault"
  - "Built at LexHack 2026"

## Creative Direction
- Tone preset: polished
- Creative direction: quiet civic tech that takes rights seriously — documentary gravity, not startup energy
- Interpretation: Restrained pacing, longer holds, serif presence. Confidence through stillness. The product's severity earns the viewer's attention.
- Angle: This is the anti-AI product: it cites or it shuts up. The most impressive thing CasaVault does is refuse. Show the product being right, then show it being honest.
- Hook: The 87/16% statistic — two lines of serif text on warm paper, then "They don't lose because they're wrong."
- Outro: "Every answer cites a source. Every refusal routes to a human." then CasaVault wordmark + LexHack 2026.
- Avoid:
  - Generic SaaS language ("streamline", "seamless", "revolutionize")
  - Abstract filler visuals
  - Anything that undercuts the gravity — no playfulness, no bounce

## Visual Identity
- Background: #f6f4ef (warm paper)
- Text: #1b1a17 (near-black ink)
- Accent: #1d5c4d (deep teal)
- Violation: #9f2f24 (red, for flagged findings)
- Violation bg: #fdf0ee (light red wash)
- Caution: #7d5507 (yellow)
- Surface: #ffffff (card background)
- Display font: Georgia, ui-serif (serif headings — the product uses serif for display)
- Body font: system-ui, ui-sans-serif
- Mono font: SFMono-Regular, ui-monospace (for citations — this is the product's visual signature)
- Visual references: the red-bordered finding card with monospace citation, the warm paper ground, the card UI with rounded corners (12px radius)

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. **The Stakes** — 3.5s — Three lines of serif text appear sequentially on warm paper: the 87/16 stat, then "They don't lose because they're wrong."
2. **Upload + Flags** — 6s — Recreated UI card with lease filename, then three red violation cards arrive one by one, each with a monospace statute citation. The citations are the visual star.
3. **Grounded Agent** — 5.5s — "Ask this vault" panel. Question typed, grounded answer with citation. Then "Will I win?" → refusal + hotline handoff. The refusal is the punchline.
4. **Closer** — 4s — Two statement lines + CasaVault wordmark + LexHack 2026.

## Audio
- Audio role: warm bed, restrained accents
- Audio arc: bed fades in from near-silence, stays low-mid through the middle, gentle fade at the end
- Music: `happy-beats-business-moves-vol-11-by-ende-dot-app.mp3`
- Music treatment: fade in 0–1s, volume 0.25–0.30 (lower than typical — this is restrained), steady through middle, fade out over final 2s
- Music cue guidance: bundled preset at `<skill-dir>/assets/music/cues/happy-beats-business-moves-vol-11-by-ende-dot-app.music-cues.json`. 114.84 BPM. Strong cues:
  - ~1.60s for hook text landing
  - ~5.80s for lease card entering
  - ~8.96s for first violation card
  - Beat grid ~8.96, ~9.50, ~10.01 for three violation cards
  - ~12.65s for agent answer reveal
  - ~17.91s for refusal moment
- Audio-reactive treatment: subtle; the violation cards gain a faint presence/glow on bass. Nothing showy.
- Audio-coupled moments:
  - Scene 2: three violation cards land one per beat (~0.52s apart) with card-place SFX
  - Scene 3: refusal text lands with one dry impactSoft_medium
- SFX selection guidance: card-place for violation card arrivals (warm, not aggressive); impactSoft_medium for the refusal moment; interface/drop for soft transitions. All at 0.6–0.7 volume. No aggressive hits — polished restraint.
- SFX analysis guidance: `<skill-dir>/assets/sfx/sfx-analysis.md`
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copied into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, and `hyperframes-cli`. /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show the recreated finding cards (real UI element from the product) with their monospace citations.
- Show the agent refusal — the product's signature behavior.
- Keep all text readable in the final render. Serif display text for headings, monospace for citations.
- Keep the video within 19-22 seconds.
- Include the music bed and sparse SFX layer.
- Treat music cue metadata as optional timing hints. Hyperframes decides exact animation timing.
- Major reveals may move toward nearby strong cues within ±0.15s.
- Use SFX to support the card arrivals and the refusal moment.
- Honor the fade-out on the music in the final 2s.
- When music is present, consider Hyperframes audio-reactive workflow for subtle visual elements.
- Use local assets for audio. All assets already copied to `brag-output/composition/assets/`.
- Run `hyperframes check` before render.
