# 🎛️ ComfyUI Parameters Tuning Guide
## Complete Reference for AI Animation Studio

---

## 📋 Table of Contents

1. [KSampler Parameters](#ksampler-parameters)
2. [ControlNet Parameters](#controlnet-parameters)
3. [Preprocessor Parameters](#preprocessor-parameters)
4. [Model Parameters](#model-parameters)
5. [Quick Reference Tables](#quick-reference-tables)
6. [Recommended Presets](#recommended-presets)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 KSampler Parameters

### **1. Steps**
**Location:** Node 5 (KSampler)  
**Current Value:** `30`  
**Range:** `1-150` (recommended: `20-50`)

**What it does:**
- Number of denoising iterations
- More steps = more detail, but diminishing returns after 30-40
- Each step refines the image progressively

**Effect:**
- **Low (10-20):** Fast but rough/incomplete generation
- **Medium (20-35):** ✅ Best balance (recommended)
- **High (40+):** Slower, minimal quality improvement

**Recommendation:**
- **Cleanup/Tie Down:** 25-30 steps
- **Colors:** 30-35 steps
- **Skeleton/Roughs:** 20-25 steps

---

### **2. CFG Scale (Classifier Free Guidance)**
**Location:** Node 5 (KSampler)  
**Current Value:** `7.5`  
**Range:** `1.0-30.0` (recommended: `6.0-9.0`)

**What it does:**
- Controls how strictly AI follows your prompt
- Higher = more prompt adherence, but can be "overcooked"
- Lower = more creative freedom, but may ignore prompt

**Effect:**
| CFG Value | Prompt Adherence | Creativity | Quality | Best For |
|-----------|------------------|------------|---------|----------|
| 3.0-5.0 | Low | Very High | Artistic | Experimental |
| 6.0-7.0 | Medium-Low | High | Balanced | Natural looks |
| **7.5-8.5** | **Medium** ✅ | **Medium** | **Best** | **Most cases** |
| 9.0-12.0 | High | Low | Sharp | Strict requirements |
| 13.0+ | Very High | Very Low | Over-saturated | Not recommended |

**With ControlNet (Our Case):**
- **6.5-7.5:** ✅ Best range when using ControlNet
- **Reason:** ControlNet already provides structural guidance, so lower CFG prevents conflict

**Recommendation:**
- **Cleanup Phase:** 7.5 (current) ✅
- **With weak ControlNet:** 8.0-8.5
- **With strong ControlNet:** 7.0-7.5

---

### **3. Denoise**
**Location:** Node 5 (KSampler)  
**Current Value:** `1.0`  
**Range:** `0.0-1.0`

**What it does:**
- How much AI "re-imagines" vs "refines" the input
- 1.0 = complete regeneration from noise
- 0.0 = no change to input

**Effect:**
| Denoise | Behavior | Use Case |
|---------|----------|----------|
| 0.0-0.3 | Minor tweaks only | Color correction, tiny fixes |
| 0.4-0.6 | Moderate changes | Img2img refinement |
| 0.7-0.9 | Major changes | Significant cleanup |
| **1.0** ✅ | **Full generation** | **Complete transformation** |

**With ControlNet:**
- **1.0 is ideal** for rough→clean transformation
- ControlNet structure prevents total chaos
- Allows maximum cleanup while keeping pose

**Recommendation:**
- **Cleanup/Tie Down:** 1.0 (current) ✅
- **Minor fixes only:** 0.6-0.8

---

### **4. Sampler Name**
**Location:** Node 5 (KSampler)  
**Current Value:** `euler`  
**Options:** `euler`, `euler_a`, `dpm_2`, `dpm_2_ancestral`, `heun`, `dpm_fast`, `lms`, `ddim`, `plms`, `uni_pc`, `dpm_adaptive`

**What it does:**
- Algorithm for noise reduction
- Different samplers produce different styles

**Comparison:**
| Sampler | Speed | Quality | Stability | Character | Best For |
|---------|-------|---------|-----------|-----------|----------|
| **euler** ✅ | Fast | Good | Stable | Clean, precise | **Line art** |
| euler_a | Fast | Good | Less stable | More varied | Artistic |
| dpm_2 | Medium | Better | Stable | Smooth | Paintings |
| dpm_2_ancestral | Medium | Good | Less stable | Creative | Colors |
| heun | Slow | Excellent | Very stable | Precise | Details |
| dpm_fast | Very fast | OK | Stable | Quick drafts | Testing |
| ddim | Medium | Good | Stable | Smooth | General |

**Recommendation:**
- **Cleanup:** `euler` (current) ✅ or `heun` (slower but better)
- **Colors:** `euler_a` or `dpm_2_ancestral`
- **Testing:** `dpm_fast`

---

### **5. Scheduler**
**Location:** Node 5 (KSampler)  
**Current Value:** `simple`  
**Options:** `normal`, `karras`, `exponential`, `simple`, `ddim_uniform`

**What it does:**
- Controls step timing/spacing during denoising
- Affects how noise is removed across steps

**Effect:**
| Scheduler | Character | Best For |
|-----------|-----------|----------|
| **simple** ✅ | Uniform, predictable | **Stable results** |
| normal | Standard timing | General use |
| karras | More detail in early steps | Complex images |
| exponential | Smooth transitions | Gradients |
| ddim_uniform | Specific to DDIM sampler | DDIM only |

**Recommendation:**
- **Keep `simple`** ✅ for predictable, stable results
- Experiment with `karras` for more detail

---

### **6. Seed**
**Location:** Node 5 (KSampler)  
**Current Value:** `153563715982370`  
**Range:** Any integer

**What it does:**
- Random number generator seed
- Same seed + same settings = identical output
- Different seed = variation

**Effect:**
- **Fixed seed:** Reproducible results for testing
- **Random seed:** Variation for each generation

**Recommendation:**
- **Production:** Use fixed seed for consistency
- **Exploration:** Use random/increment seed

---

## 🎮 ControlNet Parameters

### **1. ControlNet Strength (Weight)**
**Location:** Node 39 (CR Multi-ControlNet Stack)  
**Current Values:** 
- Lineart: `0.8`
- Canny: `0.6`

**Range:** `0.0-2.0` (recommended: `0.5-1.0`)

**What it does:**
- How strongly ControlNet influences generation
- Higher = more structural control
- Lower = more creative freedom

**Effect:**
| Strength | Control | Freedom | Use Case |
|----------|---------|---------|----------|
| 0.3-0.5 | Weak | High | Loose interpretation |
| **0.6-0.8** ✅ | **Medium** | **Medium** | **Balanced** |
| 0.9-1.0 | Strong | Low | Strict following |
| 1.1-1.5 | Very Strong | Very Low | Exact copy |
| 1.6+ | Extreme | None | Not recommended |

**Lineart vs Canny:**
- **Lineart (0.8):** Stronger control for pose/gesture
- **Canny (0.6):** Weaker for edge refinement

**Recommendation:**
- **Clean rough sketches:** Lineart 0.7-0.8, Canny 0.5-0.6 ✅
- **Messy rough sketches:** Lineart 0.6-0.7, Canny 0.4-0.5
- **Perfect pose preservation:** Lineart 0.9-1.0, Canny 0.7-0.8

---

### **2. Start Percent**
**Location:** Node 39 (CR Multi-ControlNet Stack)  
**Current Value:** `0` (both)  
**Range:** `0.0-1.0`

**What it does:**
- When ControlNet starts influencing generation
- 0.0 = from beginning
- 0.2 = after 20% of steps

**Effect:**
- **0.0:** ✅ Standard, control from start
- **0.1-0.3:** Allow initial creative freedom
- **0.4+:** Not recommended (too late)

**Recommendation:**
- **Keep at 0.0** ✅ for consistent control

---

### **3. End Percent (The "Timed Release" 🔥)**
**Location:** Node 39 (CR Multi-ControlNet Stack)  
**Current Values:**
- Lineart: `0.7` ✅
- Canny: `0.6` ✅

**Range:** `0.0-1.0`

**What it does:**
- **CRITICAL PARAMETER** for anatomy correction
- When ControlNet stops influencing generation
- 1.0 = active entire process
- 0.7 = releases at 70%, AI fixes anatomy in last 30%

**Effect (30 Steps Total):**
| End % | Release Point | AI Freedom Window | Anatomy Fix Ability |
|-------|---------------|-------------------|---------------------|
| 1.0 | Never | None | ❌ None |
| 0.9 | Step 27 | 3 steps | ⚠️ Minimal |
| 0.8 | Step 24 | 6 steps | ⚠️ Limited |
| **0.7** ✅ | **Step 21** | **9 steps** | **✅ Good** |
| **0.6** ✅ | **Step 18** | **12 steps** | **✅ Better** |
| 0.5 | Step 15 | 15 steps | ⚠️ May lose pose |
| 0.4- | Step 12- | 18+ steps | ❌ Too much freedom |

**Lineart 0.7 vs Canny 0.6 Strategy:**
```
Steps 1-18:  Canny + Lineart BOTH ACTIVE
             → Lock shapes and pose

Steps 19-21: Canny RELEASED, Lineart ACTIVE
             → Smooth edges, refine shapes

Steps 22-30: BOTH RELEASED
             → Fix face, hands, anatomy
```

**Recommendation:**
- **Balanced (current):** Lineart 0.7, Canny 0.6 ✅
- **More anatomy freedom:** Lineart 0.6, Canny 0.5
- **Strict pose preservation:** Lineart 0.8, Canny 0.7
- **Maximum anatomy fix:** Lineart 0.5, Canny 0.4

---

## 🔧 Preprocessor Parameters

### **1. LineArt Preprocessor**
**Location:** Node 19 (LineArtPreprocessor)  
**Current Settings:**
- `coarse`: `disable`
- `resolution`: `1920`

#### **Coarse Mode**
**Options:** `disable`, `enable`

**What it does:**
- Simplifies line detection
- `disable` = detailed lines (current) ✅
- `enable` = simplified/coarse lines

**Recommendation:**
- **Cleanup/Tie Down:** `disable` ✅
- **Sketch/Roughs:** `enable`

#### **Resolution**
**Range:** `512-2048`

**What it does:**
- Processing resolution for line detection
- Higher = more detail but slower

**Recommendation:**
- **Standard:** 1024-1536
- **High quality (current):** 1920 ✅
- **Fast testing:** 512-1024

---

### **2. Canny Preprocessor**
**Location:** Node 20 (Canny)  
**Current Settings:**
- `low_threshold`: `0.4`
- `high_threshold`: `0.8`

**Range:** `0.0-1.0`

**What it does:**
- Edge detection sensitivity
- Low threshold: weak edges
- High threshold: strong edges

**Effect:**
| Setting | Edges Detected | Best For |
|---------|----------------|----------|
| Low: 0.2, High: 0.6 | Many (even faint) | Messy sketches |
| **Low: 0.4, High: 0.8** ✅ | **Medium** | **Clean sketches** |
| Low: 0.6, High: 0.9 | Few (only strong) | Final artwork |

**Recommendation:**
- **Rough sketches:** Low 0.3-0.4, High 0.7-0.8
- **Clean sketches (current):** Low 0.4, High 0.8 ✅
- **Very clean:** Low 0.5, High 0.9

---

## 🎨 Model Parameters

### **1. Checkpoint Model**
**Location:** Node 1 (CheckpointLoaderSimple)  
**Current Value:** `Realistic_Vision_V5.1.safetensors`

**What it does:**
- Base AI model for generation
- Different models have different strengths

**Recommendations by Phase:**
- **Cleanup/Tie Down:** Realistic Vision ✅, AnythingV5
- **Colors:** DreamShaper, Deliberate
- **Anime Style:** AnythingV5, CounterfeitV3

---

## 📊 Quick Reference Tables

### **Common Scenarios**

| Scenario | CFG | Denoise | Lineart Strength | Lineart End | Canny End |
|----------|-----|---------|------------------|-------------|-----------|
| **Standard Cleanup** ✅ | 7.5 | 1.0 | 0.8 | 0.7 | 0.6 |
| Messy Rough Sketch | 7.0 | 1.0 | 0.7 | 0.6 | 0.5 |
| Perfect Pose Lock | 8.0 | 1.0 | 0.9 | 0.8 | 0.7 |
| Maximum Anatomy Fix | 7.0 | 1.0 | 0.6 | 0.5 | 0.4 |
| Fast Testing | 8.0 | 0.8 | 0.8 | 0.7 | 0.6 |
| Color Phase | 7.5 | 1.0 | 0.7 | 0.8 | 0.7 |

### **Problem → Solution**

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Face still unclear | End % too high | Lower Lineart end to 0.6 |
| Hands wrong | End % too high | Lower Lineart end to 0.6 |
| Pose changed too much | End % too low | Raise Lineart end to 0.8 |
| Lines too stiff/robotic | CFG too high | Lower CFG to 7.0 |
| Not following prompt | CFG too low | Raise CFG to 8.0 |
| Over-saturated/dirty | CFG too high | Lower CFG to 7.0 |
| Incomplete generation | Steps too low | Increase steps to 30 |
| Too slow | Steps/resolution too high | Reduce to 25 steps, 1024 res |

---

## 🎯 Recommended Presets

### **Preset 1: Standard Cleanup (Current) ✅**
```json
{
  "steps": 30,
  "cfg": 7.5,
  "denoise": 1.0,
  "sampler": "euler",
  "scheduler": "simple",
  "lineart_strength": 0.8,
  "lineart_end": 0.7,
  "canny_strength": 0.6,
  "canny_end": 0.6
}
```
**Use:** Clean rough sketches with minor anatomy issues

### **Preset 2: Messy Sketch Fix**
```json
{
  "steps": 30,
  "cfg": 7.0,
  "denoise": 1.0,
  "sampler": "euler",
  "scheduler": "simple",
  "lineart_strength": 0.7,
  "lineart_end": 0.6,
  "canny_strength": 0.5,
  "canny_end": 0.5
}
```
**Use:** Very rough sketches with major anatomy problems

### **Preset 3: Pose Preservation**
```json
{
  "steps": 30,
  "cfg": 8.0,
  "denoise": 1.0,
  "sampler": "euler",
  "scheduler": "simple",
  "lineart_strength": 0.9,
  "lineart_end": 0.8,
  "canny_strength": 0.7,
  "canny_end": 0.7
}
```
**Use:** When pose/gesture must stay exactly the same

### **Preset 4: Maximum Anatomy Freedom**
```json
{
  "steps": 35,
  "cfg": 7.0,
  "denoise": 1.0,
  "sampler": "heun",
  "scheduler": "simple",
  "lineart_strength": 0.6,
  "lineart_end": 0.5,
  "canny_strength": 0.5,
  "canny_end": 0.4
}
```
**Use:** Extreme anatomy corrections needed

### **Preset 5: Fast Testing**
```json
{
  "steps": 20,
  "cfg": 8.0,
  "denoise": 0.8,
  "sampler": "dpm_fast",
  "scheduler": "simple",
  "lineart_strength": 0.8,
  "lineart_end": 0.7,
  "canny_strength": 0.6,
  "canny_end": 0.6
}
```
**Use:** Quick iterations during testing

---

## 🔬 Advanced Tuning Tips

### **1. CFG + ControlNet Strength Relationship**
```
High CFG + High ControlNet = Over-constrained (stiff/robotic)
High CFG + Low ControlNet = Prompt-driven (may lose structure)
Low CFG + High ControlNet = Structure-driven (natural but controlled) ✅
Low CFG + Low ControlNet = Too much freedom (may diverge)
```

**Optimal:** `CFG 7.0-7.5` + `ControlNet 0.7-0.8` ✅

### **2. Steps vs Quality**
```
10 steps  = 40% quality
20 steps  = 75% quality
30 steps  = 95% quality ✅
40 steps  = 98% quality (diminishing returns)
50+ steps = 99% quality (not worth the time)
```

**Sweet spot:** 25-35 steps

### **3. Ending Step Fine-Tuning**
```
If face unclear but pose good:
  → Lineart end OK, lower Canny end by 0.1

If hands wrong but face OK:
  → Both ends too high, lower by 0.1

If pose drifting significantly:
  → Ends too low, raise Lineart by 0.1

If nothing fixing:
  → Prompt weights too low, increase to (keyword:1.4)
```

---

## 📝 Parameter Change Log

| Date | Parameter | Old | New | Reason |
|------|-----------|-----|-----|--------|
| 2025-12-18 | CFG | 8.9 | 7.5 | Balance ControlNet + prompt |
| 2025-12-18 | Lineart End | 1.0 | 0.7 | Enable anatomy correction |
| 2025-12-18 | Canny End | 1.0 | 0.6 | Enable anatomy correction |

---

## 🎓 Learning Path

1. **Start:** Use Standard Preset (current settings) ✅
2. **Experiment:** Change one parameter at a time
3. **Document:** Note which changes improve results
4. **Iterate:** Build your custom preset
5. **Share:** Document what works for your use case

---

## 📞 Support

**Need help tuning?**
1. Check [Troubleshooting](#troubleshooting) section
2. Review [Quick Reference Tables](#quick-reference-tables)
3. Try recommended presets
4. Document your test results

---

**Last Updated:** Dec 18, 2025  
**Version:** 1.0  
**Status:** Production-ready ✅

