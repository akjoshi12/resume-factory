# Brag Plan: Resume Factory

## What is this app?
A local-first Reflex app that takes a job posting and your real resume history, runs an LLM through a LangGraph pipeline to draft a tailored resume and cover letter, then refuses to let the draft out the door until every claim is checked against the source, the PDF is proven to parse, and a human has approved it — no cloud, no telemetry, nothing leaves the machine.

## The angle
Everyone's worried AI resume tools make you sound like everyone else. This one has the opposite failure mode covered: it worries the model is lying about you. The whole video is one dry, matter-of-fact walkthrough of a tool that polices its own output — catches a fabricated claim before a human ever sees it, then shrugs and admits there's no such thing as an "ATS score" because no ATS actually emits one. The joke is the rigor. It's played completely straight.

## Hook (first 2-3 seconds)
Black screen. One line types out, plain, no drama:
"I asked an AI to rewrite my resume."
Beat of silence. Long enough to feel like a setup with no punchline yet — because deadpan doesn't announce the twist.

## Key moments (the middle)
- **The self-check catches a lie.** The review screen appears: badges across the top (page count, JD coverage, "parses"). A red callout slides in — "Unverified claims" — naming a specific fabricated line the model added that isn't in the source bullets. The line gets struck through / reverted to the real source text. The callout dismisses. Badges settle to green. No cheering, just the system doing the thing it's supposed to.
- **It never leaves the Mac.** A single quiet frame: "Local machine" as one box — UI, model, PDF renderer, all inside it. One line out, to nothing. Caption: "Runs on my Mac. Reached over Tailscale. Nothing uploaded." A dry aside about free-tier cloud models seeing your phone number and who you're applying to — stated flatly, not as scare copy.

## Outro / punchline
"There's no ATS score here. Because no ATS emits one." — hold on that line, then a clean cut to the product mark: **Resume Factory**, small tagline underneath: "It won't lie for you. Not even a little." Long hold. No CTA, no URL — this isn't a startup that needs you to sign up.

## User flow worth showing
Entry → key action → result, compressed into the centerpiece scene:
1. **Entry:** A job posting pasted into the description box; "Generate resume" clicked.
2. **Key action:** The review gate — badges, the caught-and-reverted fabricated claim, Approve clicked.
3. **Result:** A finished PDF, downloaded, done.
This is Key Moment 1 above — the flow *is* the highlight, not a separate scene.

## Tone
- Preset: deadpan
- Creative direction: an engineer's dry, matter-of-fact proof that the tool refuses to lie for you — no winking, no excitement, the rigor itself is the entertainment.
- Interpretation: long holds (4-7s per scene), one thought per scene, generous empty space, sparse type. Motion stays clean and unhurried — the pace itself is part of the joke. No hype language anywhere in the copy.

## Format: landscape — 1920x1080
## Duration: 23s

## Visual identity (from the project)
- Background: `#0a0a0a` (near-black — the app itself ships with zero custom branding; this is a deliberate treatment for the video, not lifted from the app's default Radix theme)
- Accent (verified/approved): `#34d399` (emerald green — matches the app's own semantic "green" badges for parse-ok / low stage)
- Accent (violation/alert): `#ef4444` (red — matches the app's own semantic red for violations / parse failure), used once, briefly, for the one flagged claim
- Text: `#f2f2ee` (off-white)
- Display font: a clean, restrained sans (e.g. Inter) for headline lines
- Body/data font: a monospace-adjacent face for badges, claim text, and the "Local machine" label — echoes the app's own terse, technical register
- Strongest visual element: the red "Unverified claims" callout flipping to a green "parses" badge — the app's actual claim-verification UI, not an invented graphic

## Share copy (draft)
Built an AI resume tool that would rather show you its own mistakes than lie for you — it checks every rewritten line against your real history, runs entirely on my Mac, and still won't give itself an ATS score, because that number doesn't exist.

## Audio direction
- Role: sparse, restrained accents — the music should almost disappear
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (109.96 BPM, steady/clean character) at very low volume (0.14)
- Music treatment: fades in under Scene 1 at low volume, stays flat and unobtrusive through the middle, small lift into the outro, clean fade on the final hold — no swell, no build
- Music cue guidance: preset read from `assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json`. Target strong cues near 8.74s (the violation callout landing, inside Scene 2) and 17.47s (the cut into Scene 4 / outro). Treat 22.93s as an optional soft accent on the final logo hold, not a hard hit — deadpan restraint means the beat should support the cut, not announce it.
- Audio-reactive treatment: none — deadpan calls for stillness, not visual elements breathing with the music
- SFX posture: very sparse — 1-2 dry cues total, nothing bright or celebratory
- Audio-coupled moments: the hook line may type out with faint, randomized `keyboard/keypress-*` ticks at very low volume; the red callout's arrival gets one dry, low cue (a soft click or muted error tone, not a jarring alarm); the flip to green gets no sound at all — restraint is the point
- Restraint rule: no whooshes, no swells, no celebratory chimes, no audio-reactive glow. If a cue calls attention to itself, cut it.

## Storyboard

### Scene 1 — Hook — 5s
Black frame. "I asked an AI to rewrite my resume." types out character by character, then holds, fully settled, in silence-adjacent stillness.
Sequential/interaction: yes — the line types out character by character, then holds for the remainder of the scene.
Audio intent: quiet, almost administrative — no tension score, just a fact being typed.
Audio-coupled idea: faint randomized keypress ticks under the typing, very low volume; nothing after it settles.
Music: vol-12, fading in under the scene, very low (0.10-0.14).
Transition mood: slow crossfade → Scene 2

### Scene 2 — The self-check — 6s (5s-11s)
Cut to the review-gate screen (recreated from the app's real UI: page-count badge, coverage badge, "parses" badge in a row). A red callout slides in: "Unverified claims" with one specific fabricated line named (something concrete-sounding and slightly absurd, invented by the model, that isn't in the source bullets). The line strikes through and is replaced by the real source text. The callout dismisses; the badge row settles fully green.
Sequential/interaction: yes — badges appear first (already settled from the cut), then the red callout slides in, then the strike-through/replace happens, then the callout dismisses and the badge turns green. Each step must fully hold before the next starts.
Audio intent: procedural, almost clinical — a system quietly doing its job, not a dramatic catch.
Audio-coupled idea: one dry, low click/alert-adjacent tone exactly as the red callout lands (~8.7s, near the strong cue at 8.74s); no sound on the green flip.
Music: vol-12 continues flat, low.
Transition mood: hard cut (deadpan restraint, not a dramatic wipe) → Scene 3

### Scene 3 — Local machine — 6s (11s-17s)
A single outlined box labeled "Local machine" containing small labels for UI, model, PDF renderer — no external arrows in, one line out to nothing (or to a small "Tailscale" label, dead-ending). Caption beneath: "Runs on my Mac. Reached over Tailscale. Nothing uploaded." A second, smaller line follows after a beat: "Free-tier cloud models see your phone number and who you're applying to. This one doesn't."
Sequential/interaction: yes — the box and its internal labels are present from the cut; the two caption lines arrive one after another, each held to its full reading floor before the next appears.
Audio intent: flat, informational, mildly conspiratorial in a dry way — not ominous, just stated.
Audio-coupled idea: none — let this scene sit in near-silence apart from the music bed.
Music: vol-12 continues flat, low; begins its small lift right at the transition into Scene 4.
Transition mood: slow crossfade (matches the cue near 17.47s) → Scene 4

### Scene 4 — Punchline / outro — 6s (17s-23s)
"There's no ATS score here." holds, then "Because no ATS emits one." arrives beneath it. Clean cut to the product mark: "Resume Factory" centered, small tagline underneath: "It won't lie for you. Not even a little." Long hold to black.
Sequential/interaction: yes — the two punchline lines arrive one after another (each fully held), then a hard cut to the logo card, which then holds untouched to the end.
Audio intent: the driest possible landing — the joke is that nothing swells for it.
Audio-coupled idea: at most one soft, low accent right on the logo cut (optionally nudged toward the 22.93s cue), and only if it stays dry — skip it entirely if it reads as celebratory.
Music: gentle fade-out starting under the logo hold, silent by the last frame.
Transition mood: hard cut into logo, then long hold → end

**Music mood for this video:** deadpan
**Audio summary:** A single low, steady bed (vol-12) that barely rises above a whisper, one or two dry SFX at most, and no audio-reactive visuals — the restraint is doing the same work as the copy.
