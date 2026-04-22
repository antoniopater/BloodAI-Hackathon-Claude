---
name: hackathon-scorer
description: "Score and evaluate a hackathon project against the 'Built with 4.7' hackathon judging criteria. Use this skill whenever you need to assess project readiness, identify weak areas, get a score breakdown, or prepare for demo day. Trigger on: 'score my project', 'how ready am I', 'evaluate hackathon', 'judging criteria check', 'rate my demo', 'what should I improve', or any mention of hackathon scoring/evaluation."
---

# Hackathon Project Scorer — "Built with Opus 4.7"

Score any project against the four judging categories. Run this assessment iteratively throughout development to track progress and identify gaps.

## Scoring Rubric

For each category, score 1-10 and multiply by the weight. Max total = 10.0

### 1. IMPACT (weight: 0.30) — Score 1-10

Evaluate these questions:
- **Real-world potential**: Does this solve a problem people actually have? (1=toy, 10=life-changing)
- **Who benefits & how much**: Is the beneficiary group large? Is the pain point severe? (1=niche/mild, 10=universal/critical)
- **Could people actually use this?**: Is it close to a real product or pure prototype? (1=concept only, 10=ready to ship)
- **Problem statement fit**: Does it clearly fit "#1 Build From What You Know" or "#2 Build For What's Next"? (1=forced, 10=perfect fit)

Scoring guide:
- 1-3: Toy project, no clear user, solves nothing important
- 4-5: Interesting but niche, unclear who would use it daily
- 6-7: Clear problem, identifiable users, some real-world traction possible
- 8-9: Significant problem, large user base, obvious path to adoption
- 10: Could change how an industry/field works; judges immediately think "I want this"

### 2. DEMO (weight: 0.25) — Score 1-10

Evaluate these questions:
- **Working demo**: Does it actually work end-to-end, or just slides? (1=mockup, 10=fully functional)
- **Holds up live**: Would it survive live testing without crashes? (1=fragile, 10=bulletproof)
- **Cool to watch**: Is there a "wow" moment? (1=boring, 10=audience gasps)

Scoring guide:
- 1-3: Doesn't work, crashes, or is just screenshots
- 4-5: Works but clunky, no visual appeal, boring to watch
- 6-7: Functional, decent UI, one or two interesting moments
- 8-9: Smooth, polished, has a clear "wow" moment, good pacing
- 10: Audience leans forward, judges want to try it themselves, memorable

Demo "wow" checklist:
- [ ] Has a dramatic before/after (manual process vs. app)
- [ ] Visual feedback during processing (not just a spinner)
- [ ] Results are immediately useful (not "here's some JSON")
- [ ] At least one moment that surprises (unexpected capability)
- [ ] Works on first try in front of people

### 3. OPUS 4.7 USE (weight: 0.20) — Score 1-10

Evaluate these questions:
- **Creative integration**: Is Opus 4.7 used in a surprising/novel way? (1=basic chat, 10=mind-blowing)
- **Beyond basic**: Goes further than "send prompt, get text back"? (1=wrapper, 10=deep integration)
- **Surfaces capabilities**: Shows what Opus 4.7 can do that other models can't? (1=generic LLM use, 10=Opus-specific magic)

Scoring guide:
- 1-3: Basic chat wrapper, could be any LLM, no creative use
- 4-5: Uses Opus but in a standard way (summarize, generate text)
- 6-7: Interesting multi-step use, some creative prompting, good integration
- 8-9: Novel architecture combining Opus with other systems, shows unique capabilities
- 10: Judges say "we didn't think of using it that way"; surfaces capabilities that surprise even Anthropic

Creative use patterns that score well:
- Opus as a verification/second-opinion layer over another ML model
- Opus for multimodal understanding (PDF/image → structured data)
- Opus generating dynamic logic (not just text but code, queries, decisions)
- Opus in an agentic loop with tool use
- Combining Opus reasoning with domain-specific models

### 4. DEPTH & EXECUTION (weight: 0.20) — Score 1-10

Evaluate these questions:
- **Beyond first idea**: Did the team iterate and push past the obvious? (1=first draft, 10=deeply refined)
- **Engineering quality**: Is the code clean, tested, well-structured? (1=spaghetti, 10=production-grade)
- **Real craft**: Does it feel wrestled with — not just hacked together? (1=quick hack, 10=labor of love)

Scoring guide:
- 1-3: Obvious first idea, no iteration, messy code, thrown together
- 4-5: Some thought, but feels rushed, missing error handling, basic structure
- 6-7: Good structure, handles edge cases, clear architecture, some polish
- 8-9: Excellent engineering, thoughtful design decisions, documented, tested
- 10: Production quality, every detail considered, deep domain knowledge evident

Quality signals:
- [ ] Error handling for all API calls
- [ ] Loading states and graceful degradation
- [ ] Mobile responsive
- [ ] Clean repo with README, setup instructions, architecture docs
- [ ] Open source license (REQUIRED by rules)
- [ ] No hardcoded secrets
- [ ] Meaningful commit history (not one big commit)

---

## How to run the assessment

When scoring a project, follow this format:

```
╔══════════════════════════════════════════════════╗
║         HACKATHON SCORE — [Project Name]         ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  IMPACT (30%)           [X]/10  →  [Y]/3.0      ║
║  ├─ Real-world potential:     [score]            ║
║  ├─ Who benefits:             [score]            ║
║  ├─ Could people use this:    [score]            ║
║  └─ Problem statement fit:    [score]            ║
║                                                  ║
║  DEMO (25%)             [X]/10  →  [Y]/2.5      ║
║  ├─ Working demo:             [score]            ║
║  ├─ Holds up live:            [score]            ║
║  └─ Cool to watch:            [score]            ║
║                                                  ║
║  OPUS 4.7 USE (20%)     [X]/10  →  [Y]/2.0      ║
║  ├─ Creative integration:     [score]            ║
║  ├─ Beyond basic:             [score]            ║
║  └─ Surfaces capabilities:    [score]            ║
║                                                  ║
║  DEPTH & EXECUTION (20%) [X]/10 →  [Y]/2.0      ║
║  ├─ Beyond first idea:        [score]            ║
║  ├─ Engineering quality:      [score]            ║
║  └─ Real craft:               [score]            ║
║                                                  ║
║  ══════════════════════════════════════════════   ║
║  TOTAL:                          [Z]/10.0        ║
║  GRADE:  [emoji + label]                         ║
║                                                  ║
║  TOP 3 IMPROVEMENTS TO MAKE:                     ║
║  1. [most impactful improvement]                 ║
║  2. [second improvement]                         ║
║  3. [third improvement]                          ║
║                                                  ║
║  ESTIMATED COMPETITIVE POSITION:                 ║
║  [assessment of where this would place]          ║
╚══════════════════════════════════════════════════╝
```

Grade scale:
- 9.0-10.0: 🏆 Winner territory
- 8.0-8.9:  🥈 Strong contender  
- 7.0-7.9:  👍 Solid project
- 6.0-6.9:  ⚠️ Needs work
- Below 6.0: 🔴 Major gaps

## Rules reminder (disqualification risks)
- ❗ Everything MUST be open source
- ❗ All work must be NEW (started during hackathon)
- ❗ Team size: 1 or 2 only
- ❗ No legal/ethical violations, no stolen code/data/assets
