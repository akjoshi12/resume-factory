# Brag Plan: Resume Factory v2

## What is this app?
A local-first resume and cover-letter tailor. v2 first tells you whether a job is worth applying to, then gives you an ATS-style score that shows how it was calculated, checks every claim against your real history, and runs as an always-on background service on the Mac.

## The angle
A v2 changelog that plays as a sequel. The first video ended with "There's no ATS score here. Because no ATS emits one." v2 now ships one, but as an honest proxy with its weights printed (45 / 35 / 10 / 10). The joke is that it is still too honest to call it a real ATS score. Around that sit the practical upgrades: a quick scan before you write anything, dashboard tallies, three UI skins, and a service that never needs starting.

## Hook (first 2-3 seconds)
"Should I even apply?" types out in an input, then a cursor clicks the real button: **Quick scan: should I apply?**

## Key moments (the middle)
- Quick scan result card: "81% fit" counts up, **Apply** badge lands, Strengths (green) / Gaps (red), and "Tools asked for that you have not used: dbt".
- ATS match: the review badge row (`1 page` · `ATS 86%` · `parses`), then a 4-segment bar fills: Tools 45 / Keywords 35 / Title 10 / Parse 10. Caption: "A proxy. Working shown."
- Claim check: "Unverified claims" callout, the fabricated "Built dbt models" gets struck, then "0 unverified claims".
- Dashboard tiles (Applications / Waiting to hear / Interviews / Rejected) count up while the panel skin swaps minimal → glass → skeuo.
- Background service: a terminal card showing `launchctl list`, with `com.resumefactory.app` and `com.resumefactory.lmstudio` both up. "Always on. Starts at login. Restarts itself."

## Outro / punchline
"RESUME FACTORY v2". Tagline: "Tells you if it's worth applying. Still won't lie for you."

## User flow worth showing
Paste posting → Quick scan → verdict → generate → review (ATS + claim check) → dashboard.

## Tone
- Preset: app-store
- Creative direction: a crisp v2 sequel changelog that keeps the last video's dry honesty
- Interpretation: feature cards with clean slides, a light SFX layer, steady pace, one dry callback line.

## Format: landscape — 1920x1080
## Duration: 25s

## Visual identity (from the project)
- Background: `#0f1b2d` (minimal skin, dark navy)
- Panel: `#16243a`
- Accent: Radix orange `#f76b15` (rxconfig accent_color="orange")
- Green `#3dd68c`, red `#ff6369`, amber `#ffc53d`, text `#edeef0`, muted `#b0b4ba`
- Display font: Inter; data font: JetBrains Mono
- Strongest visual element: the real review badge row and the Quick scan verdict card

## Share copy (draft)
Resume Factory v2: tells you if a job's worth applying to before you write a word, scores the resume with its working shown, still refuses to invent facts, and now runs as an always-on service on my Mac.

## Audio direction
- Role: upbeat light bed with consistent card accents
- Music: `happy-beats-business-moves-vol-11-by-ende-dot-app.mp3` (114.84 BPM), around 0.3 volume, fade in over 1s and out over the last 1.5s
- Music cue guidance: preset read. Strong cues 3.70 (scan card), 8.96 (ATS scene), 12.65 (claim check), 17.91 (skin swap), 22.65 (logo).
- Audio-reactive: none (keeps the render deterministic and simple)
- SFX: keypresses on the hook, a click on the button, card slides on scene entrances, a soft impact on the strike, a bell on the logo.
- Restraint: no SFX on every text line.

## Storyboard
1. Hook — 0–3.7s — "Should I even apply?" typed, then a click on the Quick scan button.
2. Quick scan — 3.7–8.96s — 81% fit, Apply, Strengths / Gaps, missing tool dbt.
3. ATS match — 8.96–12.65s — badge row and the 45/35/10/10 bar; "A proxy. Working shown."
4. Claim check — 12.65–15.8s — Unverified claim struck; 0 unverified claims.
5. Dashboard + skins — 15.8–19.5s — tiles count up; skin swaps at 17.91.
6. Background service — 19.5–22.65s — launchctl card; "Always on. Starts at login. Restarts itself." + "Open it from your phone over Tailscale."
7. Outro — 22.65–25s — logo and tagline.
