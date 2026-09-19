# Hyperframes Composition Brief: Resume Factory

## Objective
Create a short launch-style brag video for Resume Factory.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 23 seconds

## Source Material
- Project root: `/Users/atrijoshi/Documents/resume-factory-v2`
- Primary files read: `README.md`, `rxconfig.py`, `rfactory/app.py`, `rfactory/pages/review.py`, `rfactory/pages/dashboard.py`, `rfactory/pages/new_application.py`, `rfactory/pages/common.py`, `architecture.json`
- Product name: Resume Factory
- Tagline / strongest claim: "There is no 'ATS score' here, because no applicant tracking system emits one." Also: any rephrased bullet with a number or named entity not present in the source (or declared skill pool) is a violation — forced retry, and if retries run out the draft still reaches the human with violations shown, never silently accepted.
- Key UI or visual moment to recreate: the review-gate screen's badge row (page count / coverage / "parses") plus the red "Unverified claims" callout that names a fabricated line and gets corrected before approval — this is the app's real claim-verification UI (see `rfactory/pages/review.py`, `_signals()` and the violations `rx.callout`).
- Copy that must appear verbatim:
  - "I asked an AI to rewrite my resume."
  - "Unverified claims"
  - "There's no ATS score here."
  - "Because no ATS emits one."
  - "Runs on my Mac. Reached over Tailscale. Nothing uploaded."
  - "Resume Factory"
  - "It won't lie for you. Not even a little."

## Creative Direction
- Tone preset: deadpan
- Creative direction: an engineer's dry, matter-of-fact proof that the tool refuses to lie for you. No winking, no excitement — the rigor itself is the entertainment.
- Interpretation: long holds (4-7s per scene), one thought per scene, generous empty space, sparse type, unhurried clean motion. No hype language.
- Angle: Most AI resume tools worry about sounding generic. This one worries the model is lying about you — so it checks every rewritten claim against the real source, proves the PDF parses, and still won't invent an ATS score because no ATS emits one. The video plays that rigor completely straight, like a systems audit rather than a launch pitch.
- Hook: Black screen, one typed line: "I asked an AI to rewrite my resume." Then it holds in silence-adjacent stillness — no twist announced yet.
- Outro / punchline: "There's no ATS score here." → "Because no ATS emits one." → hard cut to the "Resume Factory" mark and tagline "It won't lie for you. Not even a little." Long hold, no CTA, no URL.
- Avoid:
  - Generic SaaS language ("streamline," "supercharge," etc.)
  - Abstract filler visuals unrelated to the actual review-gate UI
  - Inventing a colorful brand identity the app doesn't have — the near-black/mono treatment IS the identity
  - Any triumphant/celebratory sting on the violation-catch or the outro — restraint is the point

## Visual Identity
- Background: `#0a0a0a`
- Text: `#f2f2ee`
- Accent (verified): `#34d399` (emerald — matches the app's own semantic green badges)
- Accent (violation): `#ef4444` (red — matches the app's own semantic red badges), used once, briefly
- Display font: a clean restrained sans (e.g. Inter) for headline lines
- Body/data font: a monospace-adjacent face for badges, the claim text, and the "Local machine" label
- Visual references from the project: the review page's badge row and red violation callout (`rfactory/pages/review.py`); the "local machine boundary" framing from `architecture.json`'s runtime diagram (everything — UI, graph, model, LaTeX, PDFs — inside one offline-first box, reached only via the tailnet)

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract. Scene summary:

1. **Hook** — 5s — "I asked an AI to rewrite my resume." types out, then holds.
2. **The self-check** — 6s — Review-gate badges settle in; red "Unverified claims" callout names one fabricated line; it's struck through and replaced with real source text; callout dismisses; badges go fully green.
3. **Local machine** — 6s — One outlined "Local machine" box containing UI/model/PDF renderer; caption "Runs on my Mac. Reached over Tailscale. Nothing uploaded."; second line: "Free-tier cloud models see your phone number and who you're applying to. This one doesn't."
4. **Punchline / outro** — 6s — "There's no ATS score here." then "Because no ATS emits one." → hard cut to "Resume Factory" mark + tagline, long hold.

## Audio
- Audio role: sparse, restrained accents — music should almost disappear
- Audio arc: flat and quiet throughout, tiny lift into the outro, fades out under the final hold
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: fade in low under Scene 1 (target ~0.14 volume), stays flat through Scenes 2-3, small lift entering Scene 4, fades to silence by the last frame
- Music cue guidance: bundled preset at `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json` (109.96 BPM). Candidate strong cues: 8.74s (land the red-callout arrival in Scene 2), 17.47s (the cut into Scene 4), 22.93s (optional soft accent on the final logo hold — skip if it reads as celebratory). Treat as hints only; ignore if they hurt readability or the deadpan restraint.
- Audio-reactive treatment: none — deadpan restraint calls for stillness, not visual elements breathing with the music
- Audio-coupled moments:
  - Scene 1 hook line — faint, randomized low-volume keypress ticks while typing, then silence once settled
  - Scene 2 callout arrival — one dry, low click/alert-adjacent SFX exactly as the red callout lands; no sound on the green flip
  - Scene 4 logo cut — at most one soft, dry accent, only if it stays understated
- SFX selection guidance: choose from `interface/` or `ui/` families for the callout accent — favor a muted click or restrained error tone over anything bright or celebratory (`impactBell`/`chips`/`glitch` families are wrong for this tone)
- SFX analysis guidance: read `<skill-dir>/assets/sfx/sfx-analysis.md`; prefer low high-frequency-risk files since these cues repeat close to spoken-register copy and must stay unobtrusive
- Exact SFX choice: Hyperframes should choose exact filenames, timestamps, density, and volume based on the implemented animation
- Audio files: copy the chosen music into `brag-output/composition/assets/music/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`. `/brag` is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (the review-gate badge row + violation callout, described above).
- Keep all text readable in the final render — respect the reading-time floors in the brag plan.
- Keep the video within 15-25 seconds (target 23s).
- Include the planned music layer at very low, restrained volume; keep SFX to 1-2 dry cues total.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints. Ignore cues that hurt readability, scene pacing, or the product story.
- Use only 1-3 strong cue locks in this 23s video.
- No audio-reactive visuals for this tone — skip that step deliberately (documented here, not a failure).
- Use local assets for audio.
- Run `hyperframes check` before render — it is brag's single gate.
