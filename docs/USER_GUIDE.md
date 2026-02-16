# AI Animation Studio M4 - User Guide

> Canonical reference: `docs/M4_MASTER_PLAN_DYNAMIC_STATIC.md`

Use this guide to run the M4 cleanup pipeline in the web app.

Live app: [animationbrainanalystfrontend-onyntxm9glmlrq5lrfjn8v.streamlit.app](https://animationbrainanalystfrontend-onyntxm9glmlrq5lrfjn8v.streamlit.app/)

---

## 1) What This App Does (M4)
- Cleans rough or tiedown sketches into clean line art.
- Preserves pose using a Motion-Lock control chain.
- Uses a reference image only for style (IP-Adapter).

---

## 2) Quick Start
1) Open the app link above.
2) Upload your input sketch (PNG/JPG).
3) Upload a reference image (style guide).
4) Select the source and destination phase.
5) Click Generate.

---

## 3) Interface Walkthrough

### A) Input Image
- Upload the sketch you want to clean.
- Best results with clear subject silhouette.

### B) Reference Image (Style Guide)
- Used for style only, not for pose.
- Use a clean, finished reference image with continuous and smooth lines in the style you want.

### C) Phase Selection
- Roughs → Tie Down: light cleanup.
- Roughs → CleanUp: aggressive cleanup.
- Tie Down → CleanUp: final polish.

### D) Control Behavior
- Most advanced settings are now agent-controlled.
- UI keeps generation flow simple; controller computes parameters automatically.

### E) Output
- You get two outputs:
  - Transparent PNG (for compositing)
  - Original output (non-transparent)

---

## 4) Best Practices
- Use a clean reference image with the subject centered.
- If your sketch is very messy, choose Roughs → CleanUp.
- If lines are already clean, use Tie Down → CleanUp.
- Keep reference image close to your desired style (anime, cartoon, etc.).

---

## 5) Common Issues

### Output looks over-stylized
- Use a simpler reference image.
- Try reducing style influence by choosing a cleaner input.

### Output loses details
- Use a cleaner input sketch.
- Choose Tie Down → CleanUp instead of Roughs → CleanUp.

---

## 6) FAQ

**Q: Does the reference image change the prompt?**  
A: Mostly via style conditioning, but adaptive guardrails/modifiers may be injected based on reference conflict analysis.

**Q: What is the best reference image?**  
A: A clean, finished line art frame in your target style, centered and square.

**Q: Can I use colored reference images?**  
A: Yes, but line art references usually work best for clean output.
