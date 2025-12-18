# How We Fix Anatomy Problems While Keeping Your Pose
## The "Timed Release" Method Explained Simply

---

## 🎯 The Problem We Solved

**The Issue:**  
When the AI helps you clean up rough sketches, it uses something called "structure control" (ControlNet with Line and Edge detection). This control works at 100% strength (from start to finish) by default.

This creates a problem:

If your rough sketch has issues like:
- Face shape is unclear or distorted
- Hands are messy or fingers are merged together
- Body proportions are off

...then the structure control **forces** the AI to stay inside those incorrect shapes, even if you write "perfect face" or "correct hands" in your instructions.

**Why this happens:**  
The structure control is active 100% of the time (from beginning to end), so the AI never gets a chance to fix the anatomy problems - it's locked into following your rough sketch exactly.

---

## ✅ Our Solution: The "Timed Release" Strategy

**The Big Idea:**  
Let the structure control lock in your character's pose for the **first 60-70%** of the process, then **release control** for the **last 30-40%** so the AI can freely fix anatomy problems based on your instructions.

Think of it like training wheels on a bike:
- First part: Training wheels ON → Learn balance (lock in the pose)
- Last part: Training wheels OFF → Ride freely (fix the anatomy)

---

## ⚙️ How We Made It Work

### **1. The Settings We Use**

These are in the workflow file (`ANIMATION_M1_api_version.json`):

**Basic Generation Settings:**
```
Steps: 30 (how many times to process)
Follow Instructions: 7.5 (was 8.9 before - too strict!)
How Much to Change: 100% (complete transformation)
Processing Method: euler
Step Timing: simple
```

**Structure Control Settings:**
```
Line Detection:
  - Strength: 0.8 (80%)
  - Starts at: 0% (beginning)
  - Stops at: 70% (step 21 out of 30) ← THIS IS KEY!

Edge Detection:
  - Strength: 0.6 (60%)
  - Starts at: 0% (beginning)
  - Stops at: 60% (step 18 out of 30) ← THIS IS KEY!
```

### **2. Why These Numbers?**

| Setting | Value | Why We Chose This |
|---------|-------|-------------------|
| **Follow Instructions** | 7.5 | Balance between following structure and being creative. 8.9 was too strict and made images look "overcooked". |
| **Line Stops At** | 70% | Keeps your pose locked for the first 21 steps, then gives AI 9 steps to fix anatomy. |
| **Edge Stops At** | 60% | Stops edge control earlier (step 18) so AI can smooth shapes while still keeping the pose safe. |
| **How Much to Change** | 100% | Complete transformation ensures clean output, not just minor fixes. |

---

## 🎨 Writing Better Instructions

### **A. Focus on Anatomy (Use Strong Weights)**

Since the structure control releases at 70%, the AI needs **STRONG instruction words** to know what to fix in the remaining 30% of steps.

We use a special syntax where `(keyword:1.3)` means "pay 1.3x more attention to this word".

#### **For Fixing Face Problems:**
```
(perfectly drawn face:1.3), (beautiful clear face:1.3), 
(sharp anime eyes:1.3), (clear facial features:1.2), 
(defined face:1.2), (visible eyes:1.2), (visible nose:1.1), 
(visible mouth:1.1), (facial structure:1.2)
```

#### **For Fixing Hand Problems:**
```
(anatomically correct hands:1.3), (proper fingers:1.2), 
(five fingers:1.2), (palm structure:1.2)
```

#### **For Overall Anatomy:**
```
(anatomically correct:1.3), (proper proportions:1.2), 
(correct anatomy:1.2), (hand-drawn feel:1.1)
```

### **B. What NOT to Include (Negative Instructions)**

Negative instructions tell the AI **what to avoid** from the rough sketch:

```
(deformed face:1.4), (messy hands:1.3), (fused fingers:1.3), 
(facial distortion:1.3), (undefined face:1.4), (missing eyes:1.3), 
(extra fingers:1.3), (fewer digits:1.3), bad anatomy, bad hands, 
deformed, extra limbs
```

### **C. Focus on Quality, Not Movement**

**Important Understanding:**  
Since structure control already locks your character's **POSE/MOVEMENT**, you don't need to mention action words like "running" or "jumping". Instead, focus on:

- **Line quality:** `(crisp edges:1.2), (uniform line weight:1.2), (professional inking:1.2)`
- **Surface look:** `(vector style:1.2), (clean lineart:1.3)`
- **Natural feeling:** `(hand-drawn feel:1.1)` ← This makes the result less robotic

---

## 🔄 What Happens During Processing (Step-by-Step)

### **Total: 30 Steps**

#### **Steps 1-18 (0-60%): Both Controls Are ACTIVE**
- **Edge Detection:** Locks shapes, edges, and overall structure
- **Line Detection:** Locks pose, gesture, and where lines go
- **What AI Does:** Follows your rough sketch strictly, no anatomy fixes yet
- **Result:** Structure is established, movement is locked in

#### **Steps 19-21 (60-70%): Edge Control STOPS, Line Control Still ACTIVE**
- **Edge Detection:** Stopped, AI can smooth the edges now
- **Line Detection:** Still active, keeps the pose safe
- **What AI Does:** Starts making shapes smoother while keeping pose
- **Result:** Edges get smoother, shapes become more defined

#### **Steps 22-30 (70-100%): Both Controls Are STOPPED**
- **Edge Detection:** Stopped
- **Line Detection:** Stopped
- **What AI Does:** **COMPLETE FREEDOM** to fix anatomy based on your strong instruction words
- **What Gets Fixed:**
  - Face structure becomes clear
  - Hands get proper anatomy with 5 fingers
  - Body proportions adjust to correct
  - Line quality improves (smooth ink, even thickness)
- **Result:** Anatomically correct, clean final artwork

---

## 📊 Before vs After Comparison

### **Before (Problems We Had):**

| Problem | What Caused It | What We Saw |
|---------|----------------|-------------|
| Face unclear/distorted | Structure control at 100% | Instructions to make "clear face" were ignored |
| Messy/merged hands | Structure control at 100% | Extra or missing fingers |
| Wrong proportions | Structure control at 100% | No anatomy corrections happened |
| "Overcooked" look | "Follow Instructions" too high (8.9) | Dirty, harsh lines |
| Too robotic | No natural variation | Too stiff and mechanical |

### **After (How We Fixed It):**

| Problem | How We Fixed It | What We Get Now |
|---------|-----------------|-----------------|
| Face unclear | Stop at 70% + (perfectly drawn face:1.3) | Face clears up in last 30% of steps |
| Messy hands | Stop at 70% + (anatomically correct hands:1.3) | Proper 5 fingers per hand |
| Wrong proportions | Strong anatomy instruction words | Correct proportions |
| "Overcooked" | Changed to 7.5 | Clean, balanced output |
| Too robotic | Added (hand-drawn feel:1.1) | Natural variation |

---

## 🧪 How to Test If It's Working

### **What to Test With:**
Upload a rough sketch that has:
1. ✅ Face shape that's a bit unclear (eyes not visible, nose/mouth messy)
2. ✅ Hands with merged fingers or wrong number of fingers
3. ✅ Body proportions that are slightly off

### **What Should Happen:**

**During First 70% (Steps 1-21):**
- AI follows your rough sketch's structure
- Face might still look unclear
- Hands might still be messy
- Pose and gesture are locked correctly

**During Last 30% (Steps 22-30):**
- Face suddenly becomes clear - eyes become visible and sharp
- Hands correct to proper anatomy with 5 fingers each
- Body proportions adjust to correct
- Lines become smooth and even thickness

### **What to Check:**
1. ✅ The instructions created have strong anatomy words (with :1.3 weights)
2. ✅ The workflow settings show Line stops at 70%, Edge stops at 60%
3. ✅ "Follow Instructions" is set to 7.5 (not 8.9)
4. ✅ Final image has clear face with visible eyes, nose, mouth
5. ✅ Hands have correct number of fingers (5 per hand)

---

## 🔧 If You Need to Adjust

You can fine-tune these settings based on your needs:

### **If You Need More Anatomy Fixes:**
```
Line Stops At: 60% (instead of 70%)
Edge Stops At: 50% (instead of 60%)
```
**Effect:** More anatomy correction, but might lose some pose accuracy

### **If You Need to Keep Pose More Strictly:**
```
Line Stops At: 80% (instead of 70%)
Edge Stops At: 70% (instead of 60%)
```
**Effect:** Better pose preservation, but less anatomy correction

### **If Lines Look Too Robotic:**
- **Problem:** Too clean and mechanical
- **Fix:** Lower "Follow Instructions" to `7.0` (more creative)

### **If AI Isn't Following Instructions:**
- **Problem:** Output doesn't match what you asked for
- **Fix:** Raise "Follow Instructions" to `8.0` (more strict)

---

## 📈 How to Know It's Working Well

### **Good Signs (It's Working!):**
✅ Face is clearly visible with defined eyes, nose, mouth  
✅ Hands are anatomically correct with proper finger count  
✅ Body proportions look correct  
✅ Lines are smooth and even thickness  
✅ Natural hand-drawn feeling (not too robotic)  
✅ Pose and gesture match your rough sketch  

### **Bad Signs (Needs Adjustment):**
❌ Face still unclear or distorted  
❌ Hands still have merged/extra/missing fingers  
❌ Lines are too stiff or too messy  
❌ Pose changed significantly from rough sketch  

---

## 🚀 What We've Done

- ✅ **Updated Workflow:** Set "Follow Instructions" to 7.5, optimized when controls stop
- ✅ **Updated Instructions:** Added strong anatomy words (weights 1.3-1.4)
- ✅ **Updated Backup Instructions:** Same anatomy focus for when AI service is down
- ✅ **Created This Guide:** So everyone understands how it works
- ✅ **Published to GitHub:** All changes are saved and available

---

## 💡 Key Things to Remember

1. **"Timed Release" is Critical:** Structure control must stop (at less than 100%) to allow anatomy fixes
2. **Strong Words Matter:** Use `(keyword:1.3)` for face/hands to override the rough sketch
3. **Quality Over Movement:** Focus instructions on line quality, not action words (movement is already locked)
4. **Balance is Key:** 7.5 is the sweet spot for "Follow Instructions" when using structure control at 100% change
5. **Negative is Powerful:** Strong negative instructions for anatomy issues are essential

---

## 📞 Common Problems & Quick Fixes

**Problem:** Face still unclear after generation  
**Quick Fix:** Increase face instruction words to 1.4, or lower Line "Stop At" to 60%

**Problem:** Pose changed too much from rough sketch  
**Quick Fix:** Increase Line "Stop At" to 80%, or increase Line Strength to 0.9

**Problem:** Lines look too stiff and robotic  
**Quick Fix:** Add more `(hand-drawn feel:1.2)` weight, or lower "Follow Instructions" to 7.0

**Problem:** AI not following instructions at all  
**Quick Fix:** Increase "Follow Instructions" to 8.0, or increase instruction word weights to 1.4

---

**Created:** Dec 18, 2025  
**Version:** 2.0 (Simplified for Everyone)  
**Status:** Ready to use ✅
