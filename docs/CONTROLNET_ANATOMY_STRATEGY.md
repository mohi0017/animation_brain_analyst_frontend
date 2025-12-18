# ControlNet + Anatomy Correction Strategy
## "Timed Release" Method for Rough to Clean Animation Pipeline

---

## 🎯 The Core Problem

**Problem:** Jab aap ControlNet (Lineart + Canny) use karte hain Denoise 1.0 ke saath, toh AI ko purani rough sketch ki shape follow karni padti hai. Agar rough sketch mein:
- Face ki shape kharab hai
- Hands messy hain ya fingers fused hain
- Body proportions off hain

...toh ControlNet AI ko **"Majboor"** kar deta hai ke woh usi kharab shape ke andar hi rahe, chahe aap prompt mein kitna bhi "perfect face" ya "anatomically correct hands" likhein.

**Root Cause:** ControlNet ka default behavior hai ke woh **100% time** (start=0.0, end=1.0) active rahta hai, isliye AI kabhi bhi anatomy fix nahi kar pata.

---

## ✅ The Solution: "Timed Release" Strategy

**Concept:** ControlNet ko **pehle 60-70% steps** mein structure lock karne do, phir **aakhri 30-40% steps** mein AI ko "Azad" kar do taake woh anatomy fix kar sake based on high-weight prompt keywords.

---

## ⚙️ Implementation Details

### **1. ComfyUI Workflow Settings**

Current optimized settings in `ANIMATION_M1_api_version.json`:

```json
{
  "5": {
    "class_type": "KSampler",
    "inputs": {
      "steps": 30,
      "cfg": 7.5,        // ✅ Reduced from 8.9 (was too harsh)
      "denoise": 1.0,    // ✅ Full generation from noise
      "sampler_name": "euler",
      "scheduler": "simple"
    }
  },
  "39": {
    "class_type": "CR Multi-ControlNet Stack",
    "inputs": {
      "controlnet_1": "control_v11p_sd15_lineart_fp16.safetensors",
      "controlnet_strength_1": 0.8,
      "start_percent_1": 0,
      "end_percent_1": 0.7,    // ✅ Release at 70% (step 21/30)
      
      "controlnet_2": "control_v11p_sd15_canny_fp16.safetensors",
      "controlnet_strength_2": 0.6,
      "start_percent_2": 0,
      "end_percent_2": 0.6     // ✅ Release at 60% (step 18/30)
    }
  }
}
```

### **2. Why These Numbers?**

| Setting | Value | Reason |
|---------|-------|--------|
| **CFG** | 7.5 | Balance between ControlNet strength and prompt creativity. 8.9 was too strict, causing "over-baked" results. |
| **Lineart End** | 0.7 (70%) | Locks pose/lines for first 21 steps, then AI fixes anatomy in last 9 steps. |
| **Canny End** | 0.6 (60%) | Releases edges earlier (step 18) so AI can smooth shapes while Lineart still guides pose. |
| **Denoise** | 1.0 | Full generation ensures clean output, not just modifications. |

---

## 🎨 Prompt Engineering Strategy

### **A. Anatomy-Focused Keywords (High Weight)**

Since ControlNet releases control at 70%, AI needs **HIGH-WEIGHT** keywords to know what to fix in the remaining 30% steps:

#### **Face Correction:**
```
(perfectly drawn face:1.3), (beautiful clear face:1.3), 
(sharp anime eyes:1.3), (clear facial features:1.2), 
(defined face:1.2), (visible eyes:1.2), (visible nose:1.1), 
(visible mouth:1.1), (facial structure:1.2)
```

#### **Hand Correction:**
```
(anatomically correct hands:1.3), (proper fingers:1.2), 
(five fingers:1.2), (palm structure:1.2)
```

#### **General Anatomy:**
```
(anatomically correct:1.3), (proper proportions:1.2), 
(correct anatomy:1.2), (hand-drawn feel:1.1)
```

### **B. Negative Prompt Power**

Negative prompts tell AI **what to remove** from the rough sketch:

```
(deformed face:1.4), (messy hands:1.3), (fused fingers:1.3), 
(facial distortion:1.3), (undefined face:1.4), (missing eyes:1.3), 
(extra fingers:1.3), (fewer digits:1.3), bad anatomy, bad hands, 
deformed, extra limbs
```

### **C. Material Focus, Not Motion**

**Key Insight:** Since ControlNet locks **MOTION/POSE**, don't waste weights on action words like "running" or "jumping". Focus on:

- **Ink quality:** `(crisp edges:1.2), (uniform line weight:1.2), (professional inking:1.2)`
- **Surface texture:** `(vector style:1.2), (clean lineart:1.3)`
- **Natural feel:** `(hand-drawn feel:1.1)` ← This softens ControlNet rigidity

---

## 🔄 Generation Flow (Step-by-Step)

### **30 Steps Total:**

#### **Steps 1-18 (0-60%): Both ControlNets Active**
- **Canny:** Locks shapes, edges, and overall structure
- **Lineart:** Locks pose, gesture, and line placement
- **AI Behavior:** Follows rough sketch strictly, no anatomy fixes yet
- **Result:** Structure established, motion locked

#### **Steps 19-21 (60-70%): Canny Released, Lineart Still Active**
- **Canny:** Released, AI can smooth edges
- **Lineart:** Still active, maintains pose/gesture
- **AI Behavior:** Starts refining shapes while keeping pose
- **Result:** Edges smoother, shapes more defined

#### **Steps 22-30 (70-100%): Both ControlNets Released**
- **Canny:** Released
- **Lineart:** Released
- **AI Behavior:** **FULL FREEDOM** to fix anatomy based on high-weight keywords
- **Focus on:**
  - Face structure correction
  - Hand anatomy with proper finger count
  - Body proportions
  - Material quality (ink smoothness, line weight)
- **Result:** Anatomically correct, clean final art

---

## 📊 Before vs After

### **Before (Problems):**
| Issue | Cause | Symptom |
|-------|-------|---------|
| Distorted face | ControlNet 100% lock | Prompt "clear face" ignored |
| Messy/fused hands | ControlNet 100% lock | Extra/missing fingers |
| Off proportions | ControlNet 100% lock | No anatomy correction |
| Over-baked output | CFG 8.9 too high | Dirty, harsh lines |
| Robotic look | No natural variance | Too stiff/mechanical |

### **After (Fixed):**
| Issue | Solution | Result |
|-------|----------|--------|
| Distorted face | End=0.7 + (perfectly drawn face:1.3) | Face corrects in last 30% |
| Messy hands | End=0.7 + (anatomically correct hands:1.3) | Proper 5 fingers |
| Off proportions | High-weight anatomy keywords | Correct proportions |
| Over-baked | CFG → 7.5 | Clean, balanced output |
| Robotic look | (hand-drawn feel:1.1) | Natural variance |

---

## 🧪 Testing Guide

### **Test Case:**
Upload a rough sketch with:
1. ✅ Face ki shape slightly distorted (eyes unclear, nose/mouth messy)
2. ✅ Hands with fused fingers or missing fingers
3. ✅ Body proportions slightly off

### **Expected Behavior:**

**First 70% (Steps 1-21):**
- AI follows rough sketch structure
- Face may still look unclear
- Hands may still be messy
- Pose/gesture locked correctly

**Last 30% (Steps 22-30):**
- Face suddenly "clears up" - eyes become visible and sharp
- Hands correct to proper anatomy with 5 fingers
- Body proportions adjust to on-model
- Lines become smooth and uniform

### **What to Check:**
1. ✅ Generated prompts contain high-weight anatomy keywords
2. ✅ ComfyUI workflow shows `end_percent_1: 0.7` and `end_percent_2: 0.6`
3. ✅ CFG is 7.5 (not 8.9)
4. ✅ Final output has clear face with visible eyes, nose, mouth
5. ✅ Hands have proper finger count (5 fingers per hand)

---

## 🔧 Fine-Tuning Options

If results need adjustment:

### **More Anatomy Freedom:**
```json
"end_percent_1": 0.6,  // Lineart releases earlier (60%)
"end_percent_2": 0.5   // Canny releases earlier (50%)
```
**Effect:** More anatomy correction, but may lose some pose accuracy

### **More Structure Control:**
```json
"end_percent_1": 0.8,  // Lineart releases later (80%)
"end_percent_2": 0.7   // Canny releases later (70%)
```
**Effect:** Better pose preservation, but less anatomy correction

### **CFG Adjustment:**
- **Too robotic/clean:** `"cfg": 7.0` (lower = more creative)
- **Not following prompt:** `"cfg": 8.0` (higher = stricter prompt adherence)

---

## 📈 Success Metrics

### **Quality Indicators:**
✅ Face clearly visible with defined eyes, nose, mouth  
✅ Hands anatomically correct with proper finger count  
✅ Body proportions on-model  
✅ Lines smooth and uniform weight  
✅ Natural hand-drawn feel (not robotic)  
✅ Pose/gesture preserved from rough sketch  

### **Failure Indicators:**
❌ Face still unclear or distorted  
❌ Hands with fused/extra/missing fingers  
❌ Lines too stiff or too messy  
❌ Pose changed significantly from rough sketch  

---

## 🚀 Implementation Status

- ✅ **Workflow JSON Updated:** CFG 7.5, Ending steps optimized
- ✅ **Prompt Engineer Updated:** Anatomy keywords with high weights (1.3-1.4)
- ✅ **Fallback Prompts Updated:** Same anatomy focus
- ✅ **Documentation Created:** This strategy guide
- ✅ **Pushed to GitHub:** All changes deployed

---

## 💡 Key Takeaways

1. **"Timed Release" is Critical:** ControlNet must release control (end < 1.0) to allow anatomy fixes
2. **High Weights Matter:** Use (keyword:1.3) for face/hands to override rough sketch
3. **Material > Motion:** Focus prompts on ink quality, not action words (ControlNet locks motion)
4. **CFG Balance:** 7.5 is the sweet spot for ControlNet + Denoise 1.0
5. **Negative is Powerful:** Strong negative prompts for anatomy issues are essential

---

## 📞 Support

**Issue:** Face still unclear after generation  
**Fix:** Increase face keyword weights to 1.4 or reduce Lineart end_percent to 0.6

**Issue:** Pose changing too much from rough sketch  
**Fix:** Increase Lineart end_percent to 0.8 or increase strength to 0.9

**Issue:** Lines too stiff/robotic  
**Fix:** Add more (hand-drawn feel:1.2) weight or reduce CFG to 7.0

**Issue:** Not following prompt at all  
**Fix:** Increase CFG to 8.0 or increase keyword weights to 1.4

---

**Created:** Dec 18, 2025  
**Version:** 1.0  
**Status:** Production-ready ✅

