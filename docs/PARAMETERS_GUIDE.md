# 🎛️ Settings Guide for AI Animation Studio
## Easy-to-Understand Guide for All Users

---

## 📋 What's In This Guide

1. [Basic Generation Settings](#basic-generation-settings)
2. [Structure Control Settings](#structure-control-settings)
3. [Image Processing Settings](#image-processing-settings)
4. [AI Model Settings](#ai-model-settings)
5. [Quick Help Tables](#quick-help-tables)
6. [Ready-to-Use Presets](#ready-to-use-presets)
7. [Common Problems & Solutions](#common-problems--solutions)

---

## 🎯 Basic Generation Settings

These control how the AI creates your image.

### **1. Steps (How Many Times to Process)**
**Where to find:** Basic Settings tab  
**Current setting:** `30`  
**What you can use:** `10-50` (we recommend `20-35`)

**What this does:**
- This is how many times the AI processes your image to make it better
- More steps = more detail, but it takes longer
- After about 30 steps, you don't get much improvement

**How it affects your image:**
- **Low (10-20):** Fast but image quality isn't great
- **Medium (20-35):** ✅ Best choice for most people
- **High (35-50):** Slower, but doesn't look much better

**Our recommendations:**
- **For CleanUp/Tie Down phase:** 25-30 steps
- **For adding Colors:** 30-35 steps
- **For Skeleton/Roughs:** 20-25 steps

---

### **2. How Strictly to Follow Instructions**
**Where to find:** Basic Settings tab  
**Current setting:** `7.5`  
**What you can use:** `3.0-15.0` (we recommend `6.0-9.0`)

**What this does:**
- Controls how closely the AI follows your instructions
- Higher number = AI follows instructions exactly, but can look overdone
- Lower number = AI is more creative, but might ignore some instructions

**How it affects your image:**

| Setting | How AI Behaves | Best For |
|---------|----------------|----------|
| 3.0-5.0 | Very creative, might not follow instructions | Experimental art |
| 6.0-7.0 | Natural and balanced | Most situations |
| **7.5-8.5** ✅ | **Good balance** | **Best for most cases** |
| 9.0-12.0 | Follows instructions strictly | When you need exact results |
| 13.0+ | Too strict, can look "cooked" | Not recommended |

**Special note for our app:**
- **6.5-7.5:** ✅ Best range when the app is helping you keep your pose
- **Why:** The app already helps keep your character's structure, so you don't need a high setting

**Our recommendations:**
- **For CleanUp phase:** 7.5 (current setting) ✅
- **If you want more creativity:** 7.0
- **If AI isn't following instructions:** 8.0-8.5

---

### **3. How Much to Change**
**Where to find:** Basic Settings tab  
**Current setting:** `1.0` (100%)  
**What you can use:** `0.0-1.0` (0%-100%)

**What this does:**
- How much the AI should change your image
- 1.0 = completely transform it
- 0.0 = don't change anything

**How it affects your image:**

| Setting | What Happens | Good For |
|---------|--------------|----------|
| 0.0-0.3 | Very tiny changes only | Just fixing colors |
| 0.4-0.6 | Medium changes | Refining details |
| 0.7-0.9 | Big changes | Major cleanup |
| **1.0** ✅ | **Complete transformation** | **Rough to clean drawings** |

**Special note:**
- **1.0 is perfect** for turning rough sketches into clean art
- The app keeps your character's pose safe, so you can use the maximum setting

**Our recommendations:**
- **For CleanUp/Tie Down:** 1.0 (current setting) ✅
- **For small fixes only:** 0.6-0.8

---

### **4. Processing Method**
**Where to find:** Basic Settings tab  
**Current setting:** `euler`  
**Other options:** `euler_a`, `heun`, `dpm_2`, `dpm_fast`, and more

**What this does:**
- This is the algorithm (computer method) the AI uses
- Different methods create slightly different styles

**Which one to use:**

| Method | Speed | Quality | Character | Best For |
|--------|-------|---------|-----------|----------|
| **euler** ✅ | Fast | Good | Clean, precise lines | **Line art (use this!)** |
| euler_a | Fast | Good | More varied | Artistic styles |
| heun | Slow | Excellent | Very precise | When you need perfect details |
| dpm_2 | Medium | Better | Smooth | Paintings |
| dpm_fast | Very fast | OK | Quick drafts | Testing things quickly |

**Our recommendations:**
- **For CleanUp:** `euler` (current) ✅ or `heun` (slower but better quality)
- **For Colors:** `euler_a` or `dpm_2`
- **For quick tests:** `dpm_fast`

---

### **5. Step Timing**
**Where to find:** Basic Settings tab  
**Current setting:** `simple`  
**Other options:** `normal`, `karras`, `exponential`

**What this does:**
- Controls the timing of how the AI processes each step
- Think of it like the rhythm of the processing

**Which one to use:**

| Timing | What It Does | Best For |
|--------|--------------|----------|
| **simple** ✅ | Predictable, steady | **Most reliable (use this!)** |
| normal | Standard timing | General use |
| karras | More detail early on | Complex images |
| exponential | Smooth blending | Gradients and soft transitions |

**Our recommendations:**
- **Keep it on `simple`** ✅ for reliable, consistent results
- Try `karras` if you need extra detail

---

### **6. Random Seed Number**
**Where to find:** Basic Settings tab  
**Current setting:** `153563715982370` (a random number)  

**What this does:**
- This is like a "recipe number" for the AI
- Same number + same settings = exact same image every time
- Different number = different variation

**When to use what:**
- **Fixed number (same each time):** When you want consistent results for testing
- **Random number (changes each time):** When you want to see different variations

---

## 🎮 Structure Control Settings

These settings control how the AI keeps your character's pose and structure.

### **1. Line Following Strength**
**Where to find:** Structure Control tab  
**Current settings:** 
- Line Detection: `0.8` (80%)
- Edge Detection: `0.6` (60%)

**What you can use:** `0.0-1.5` (we recommend `0.5-1.0`)

**What this does:**
- Controls how strictly the AI follows the lines in your drawing
- Higher = AI sticks to your lines more
- Lower = AI has more freedom to fix problems

**How it affects your image:**

| Strength | How AI Follows Lines | Freedom to Fix Problems | Good For |
|----------|---------------------|------------------------|----------|
| 0.3-0.5 | Loosely | High | Very rough sketches |
| **0.6-0.8** ✅ | **Medium** | **Medium** | **Most situations** |
| 0.9-1.0 | Strictly | Low | Keeping pose exactly the same |
| 1.1-1.5 | Very strictly | Very low | Making exact copies |

**Why we use two values:**
- **Line Detection (0.8):** Stronger control to keep your pose
- **Edge Detection (0.6):** Weaker to allow edge smoothing

**Our recommendations:**
- **For clean rough sketches:** Line 0.7-0.8, Edge 0.5-0.6 ✅
- **For very messy sketches:** Line 0.6-0.7, Edge 0.4-0.5
- **To keep pose exactly:** Line 0.9-1.0, Edge 0.7-0.8

---

### **2. When to Stop Following Lines (MOST IMPORTANT!)**
**Where to find:** Structure Control tab  
**Current settings:**
- Line Detection stops at: `70%` (step 21 out of 30)
- Edge Detection stops at: `60%` (step 18 out of 30)

**What you can use:** `0.4-1.0` (40%-100%)

**What this does:**
- **THIS IS THE MOST IMPORTANT SETTING!**
- Controls when the AI stops following your lines and can freely fix anatomy problems
- Lower number = AI gets freedom earlier = more anatomy fixes
- Higher number = AI follows lines longer = keeps pose more exactly

**How it works (with 30 steps total):**

| Stop At | AI Stops Following At | Time to Fix Anatomy | Can Fix Anatomy? |
|---------|----------------------|---------------------|------------------|
| 100% (1.0) | Never stops | 0 steps | ❌ No fixes possible |
| 90% (0.9) | Step 27 | 3 steps | ⚠️ Very minimal fixes |
| 80% (0.8) | Step 24 | 6 steps | ⚠️ Limited fixes |
| **70% (0.7)** ✅ | **Step 21** | **9 steps** | **✅ Good fixes** |
| **60% (0.6)** ✅ | **Step 18** | **12 steps** | **✅ Better fixes** |
| 50% (0.5) | Step 15 | 15 steps | ⚠️ Might lose pose |
| 40% (0.4) | Step 12 | 18 steps | ❌ Too much freedom |

**Why this works (The "Timed Release" Strategy):**
```
Steps 1-18:  Both controls ACTIVE
             → Your character's shape and pose are locked in

Steps 19-21: Edge control STOPS, Line control still ACTIVE
             → AI can smooth edges, shape still safe

Steps 22-30: Both controls STOPPED
             → AI can fix face, hands, and anatomy problems
```

**Our recommendations:**
- **Balanced (current):** Line 0.7, Edge 0.6 ✅ (works for most cases)
- **Need more anatomy fixes:** Line 0.6, Edge 0.5
- **Need to keep pose exactly:** Line 0.8, Edge 0.7
- **Maximum anatomy fixing:** Line 0.5, Edge 0.4

---

## 🔧 Image Processing Settings

These control how your image is analyzed before generation.

### **1. Line Detection Detail Level**
**Where to find:** Image Processing tab  
**Current setting:** `High detail` (1920 pixels)

**What this does:**
- How much detail the AI looks for when detecting lines in your drawing
- Higher = sees more details but takes longer
- Lower = faster but might miss small details

**Our recommendations:**
- **Standard quality:** 1024-1536 pixels
- **High quality (current):** 1920 pixels ✅
- **Fast testing:** 512-1024 pixels

---

### **2. Edge Detection Sensitivity**
**Where to find:** Image Processing tab  
**Current settings:**
- Weak edge detection: `0.4`
- Strong edge detection: `0.8`

**What this does:**
- How sensitive the AI is when finding edges in your drawing
- Lower numbers = finds even faint lines
- Higher numbers = only finds strong, dark lines

**How it affects detection:**

| Settings | What Gets Detected | Best For |
|----------|-------------------|----------|
| Low: 0.2, High: 0.6 | Everything (even faint lines) | Very messy, light sketches |
| **Low: 0.4, High: 0.8** ✅ | **Medium edges** | **Most sketches** |
| Low: 0.6, High: 0.9 | Only strong lines | Clean, dark line art |

**Our recommendations:**
- **For rough sketches:** Low 0.3-0.4, High 0.7-0.8
- **For most sketches (current):** Low 0.4, High 0.8 ✅
- **For very clean art:** Low 0.5, High 0.9

---

## 🎨 AI Model Settings

### **Which AI Model to Use**
**Where to find:** Basic Settings tab  
**Current model:** `Realistic_Vision_V5.1`

**What this does:**
- This is the base AI brain that creates your images
- Different AI models are better at different things

**Which model for which task:**
- **For CleanUp/Tie Down:** Realistic Vision ✅ or AnythingV5
- **For adding Colors:** DreamShaper or Deliberate
- **For Anime style:** AnythingV5 or CounterfeitV3

---

## 📊 Quick Help Tables

### **What Settings to Use for Different Situations**

| What You're Doing | Follow Instructions | How Much to Change | Line Strength | Line Stop At | Edge Stop At |
|-------------------|--------------------|--------------------|---------------|-------------|-------------|
| **Standard cleanup** ✅ | 7.5 | 100% | 0.8 | 70% | 60% |
| Very messy sketch | 7.0 | 100% | 0.7 | 60% | 50% |
| Keep pose exactly | 8.0 | 100% | 0.9 | 80% | 70% |
| Fix anatomy problems | 7.0 | 100% | 0.6 | 50% | 40% |
| Quick test | 8.0 | 80% | 0.8 | 70% | 60% |
| Add colors | 7.5 | 100% | 0.7 | 80% | 70% |

### **Problem → Solution**

| Problem You're Having | What's Causing It | How to Fix It |
|-----------------------|-------------------|---------------|
| Face still unclear | Stops following lines too late | Lower "Line Stop At" to 60% |
| Hands still wrong | Stops following lines too late | Lower "Line Stop At" to 60% |
| Pose changed too much | Stops following lines too early | Raise "Line Stop At" to 80% |
| Lines look too stiff | Following instructions too strictly | Lower "Follow Instructions" to 7.0 |
| Not following instructions | Not following strictly enough | Raise "Follow Instructions" to 8.0 |
| Image looks overdone | Following instructions too strictly | Lower "Follow Instructions" to 7.0 |
| Image looks incomplete | Not enough processing steps | Increase steps to 30 |
| Takes too long | Too many steps | Reduce to 25 steps |

---

## 🎯 Ready-to-Use Presets

### **Preset 1: Standard Cleanup (Current Settings) ✅**
**Use this when:** You have a clean rough sketch with minor problems

Settings:
- Steps: 30
- Follow Instructions: 7.5
- How Much to Change: 100%
- Processing Method: euler
- Line Strength: 0.8
- Line Stop At: 70%
- Edge Strength: 0.6
- Edge Stop At: 60%

### **Preset 2: Fix Messy Sketch**
**Use this when:** Your sketch is very rough with major anatomy problems

Settings:
- Steps: 30
- Follow Instructions: 7.0
- How Much to Change: 100%
- Processing Method: euler
- Line Strength: 0.7
- Line Stop At: 60%
- Edge Strength: 0.5
- Edge Stop At: 50%

### **Preset 3: Keep Pose Exactly**
**Use this when:** The pose must stay exactly the same, only fix details

Settings:
- Steps: 30
- Follow Instructions: 8.0
- How Much to Change: 100%
- Processing Method: euler
- Line Strength: 0.9
- Line Stop At: 80%
- Edge Strength: 0.7
- Edge Stop At: 70%

### **Preset 4: Maximum Anatomy Fixes**
**Use this when:** You need extreme anatomy corrections

Settings:
- Steps: 35
- Follow Instructions: 7.0
- How Much to Change: 100%
- Processing Method: heun
- Line Strength: 0.6
- Line Stop At: 50%
- Edge Strength: 0.5
- Edge Stop At: 40%

### **Preset 5: Quick Testing**
**Use this when:** You want to test quickly

Settings:
- Steps: 20
- Follow Instructions: 8.0
- How Much to Change: 80%
- Processing Method: dpm_fast
- Line Strength: 0.8
- Line Stop At: 70%
- Edge Strength: 0.6
- Edge Stop At: 60%

---

## 💡 Advanced Tips for Power Users

### **1. How Settings Work Together**
```
High "Follow Instructions" + High "Line Strength" = Too stiff/robotic
High "Follow Instructions" + Low "Line Strength" = Follows text, might lose structure
Low "Follow Instructions" + High "Line Strength" = Natural but controlled ✅
Low "Follow Instructions" + Low "Line Strength" = Too much freedom
```

**Best combination:** `Follow Instructions: 7.0-7.5` + `Line Strength: 0.7-0.8` ✅

### **2. Steps vs Quality**
```
10 steps  = 40% quality
20 steps  = 75% quality
30 steps  = 95% quality ✅
40 steps  = 98% quality (not much better, takes longer)
50+ steps = 99% quality (not worth the extra time)
```

**Sweet spot:** 25-35 steps

### **3. Fine-Tuning the "Stop Following" Setting**
```
If face is unclear but pose is good:
  → Lower Edge "Stop At" by 10%

If hands are wrong but face is OK:
  → Lower both "Stop At" settings by 10%

If pose is changing too much:
  → Raise Line "Stop At" by 10%

If nothing is fixing:
  → Lower "Stop At" settings more, or increase instruction weights
```

---

## 🎓 How to Learn

1. **Start here:** Use the Standard Preset (current settings) ✅
2. **Experiment:** Change only ONE setting at a time
3. **Take notes:** Write down which changes make things better
4. **Build your own:** Create your own preset based on what works
5. **Share:** Help others by sharing what you learned

---

## 📞 Need Help?

**Can't find the answer?**
1. Check the [Problem → Solution](#problem--solution) table above
2. Try one of our [Ready-to-Use Presets](#ready-to-use-presets)
3. Ask for help in the community

---

## 🔄 Change History

| Date | What Changed | Old Value | New Value | Why |
|------|--------------|-----------|-----------|-----|
| Dec 18, 2025 | Follow Instructions | 8.9 | 7.5 | Better balance with structure control |
| Dec 18, 2025 | Line Stop At | 100% | 70% | Allow anatomy fixes |
| Dec 18, 2025 | Edge Stop At | 100% | 60% | Allow anatomy fixes |

---

**Last Updated:** Dec 18, 2025  
**Version:** 2.0 (Simplified for Everyone)  
**Status:** Ready to use ✅
