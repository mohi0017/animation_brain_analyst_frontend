"""
Parameters Tuning Page for AI Animation Studio
Interactive parameter adjustment with real-time explanations
"""

import streamlit as st
import json
from pathlib import Path

st.set_page_config(
    page_title="Parameters Tuning - AI Animation Studio",
    page_icon="🎛️",
    layout="wide"
)

# Load workflow templates
WORKFLOW_PATH = Path(__file__).parent.parent / "workflows" / "ANIMATION_M1_api_version.json"

def load_workflow():
    """Load current workflow configuration"""
    if WORKFLOW_PATH.exists():
        with open(WORKFLOW_PATH, 'r') as f:
            return json.load(f)
    return None

def save_workflow(workflow):
    """Save updated workflow configuration"""
    with open(WORKFLOW_PATH, 'w') as f:
        json.dump(workflow, f, indent=2)

# Presets
PRESETS = {
    "Standard Cleanup (Current)": {
        "steps": 30,
        "cfg": 7.5,
        "denoise": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "lineart_strength": 0.8,
        "lineart_end": 0.7,
        "canny_strength": 0.6,
        "canny_end": 0.6,
        "description": "✅ Recommended for clean rough sketches with minor anatomy issues"
    },
    "Messy Sketch Fix": {
        "steps": 30,
        "cfg": 7.0,
        "denoise": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "lineart_strength": 0.7,
        "lineart_end": 0.6,
        "canny_strength": 0.5,
        "canny_end": 0.5,
        "description": "For very rough sketches with major anatomy problems"
    },
    "Pose Preservation": {
        "steps": 30,
        "cfg": 8.0,
        "denoise": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "lineart_strength": 0.9,
        "lineart_end": 0.8,
        "canny_strength": 0.7,
        "canny_end": 0.7,
        "description": "When pose/gesture must stay exactly the same"
    },
    "Maximum Anatomy Freedom": {
        "steps": 35,
        "cfg": 7.0,
        "denoise": 1.0,
        "sampler": "heun",
        "scheduler": "simple",
        "lineart_strength": 0.6,
        "lineart_end": 0.5,
        "canny_strength": 0.5,
        "canny_end": 0.4,
        "description": "Extreme anatomy corrections needed"
    },
    "Fast Testing": {
        "steps": 20,
        "cfg": 8.0,
        "denoise": 0.8,
        "sampler": "dpm_fast",
        "scheduler": "simple",
        "lineart_strength": 0.8,
        "lineart_end": 0.7,
        "canny_strength": 0.6,
        "canny_end": 0.6,
        "description": "Quick iterations during testing"
    }
}

st.title("🎛️ Advanced Settings & Fine-Tuning")
st.markdown("_Adjust how the AI processes your images. These are advanced settings for experienced users._")
st.info("💡 **New to this page?** Start with the **Presets** in the sidebar. They work great for most cases!")
st.markdown("---")

# Load current workflow
workflow = load_workflow()
if not workflow:
    st.error("⚠️ Could not load workflow file. Please check workflows/ANIMATION_M1_api_version.json exists.")
    st.stop()

# Sidebar: Presets
with st.sidebar:
    st.header("📋 Ready-to-Use Presets")
    st.caption("Pick a preset that matches your needs")
    
    selected_preset = st.selectbox(
        "Choose a Preset",
        options=["Custom"] + list(PRESETS.keys()),
        index=1,  # Default to "Standard Cleanup"
        help="These presets are pre-configured settings for common animation tasks"
    )
    
    if selected_preset != "Custom":
        preset = PRESETS[selected_preset]
        st.info(f"**{selected_preset}**\n\n{preset['description']}")
        
        if st.button("✨ Apply This Preset", use_container_width=True):
            # Apply preset values
            st.session_state.update(preset)
            st.success(f"✅ Applied: {selected_preset}")
            st.rerun()
    else:
        st.caption("You're using custom settings. Adjust parameters below.")
    
    st.markdown("---")
    st.markdown("### 📚 Need Help?")
    st.caption("View detailed guides and explanations")
    if st.button("📖 Open Documentation", use_container_width=True, type="secondary"):
        st.switch_page("pages/3_📚_Documentation.py")

# Main content: Parameter sections
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Basic Settings", 
    "🎮 Structure Control", 
    "🔧 Image Processing", 
    "📊 Summary"
])

# ====================
# TAB 1: KSampler Parameters (Basic Settings)
# ====================
with tab1:
    st.header("🎯 Basic Generation Settings")
    st.markdown("_These control how the AI creates your image_")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Steps
        st.subheader("1️⃣ Steps (How Many Times to Process)")
        steps = st.slider(
            "Number of processing steps",
            min_value=10,
            max_value=50,
            value=workflow["5"]["inputs"].get("steps", 30),
            step=5,
            help="Higher values = more detailed results, but takes longer. 30 is usually perfect."
        )
        
        st.markdown(f"""
        **Current:** `{steps}` steps
        
        **Effect:**
        - 🟢 **20-25:** Fast, good for testing
        - ✅ **25-35:** Best balance (recommended)
        - 🟡 **35-50:** Slower, minimal improvement
        
        **Recommendation:** 30 steps for cleanup, 35 for colors
        """)
        
        st.markdown("---")
        
        # CFG Scale
        st.subheader("2️⃣ CFG Scale (How Strictly to Follow Instructions)")
        cfg = st.slider(
            "How closely the AI should follow your instructions",
            min_value=3.0,
            max_value=15.0,
            value=float(workflow["5"]["inputs"].get("cfg", 7.5)),
            step=0.5,
            help="Lower = more creative and flexible. Higher = follows instructions exactly but can look overdone."
        )
        
        if cfg < 6.0:
            cfg_status = "🟡 Low - More creative, may ignore prompt"
        elif cfg <= 8.5:
            cfg_status = "✅ Optimal - Balanced control"
        else:
            cfg_status = "🔴 High - Over-saturated, \"cooked\" look"
        
        st.markdown(f"""
        **Current:** `{cfg}` → {cfg_status}
        
        **Effect:**
        - **3-5:** Very creative, loose prompt following
        - **6-7:** Natural, balanced
        - ✅ **7-8.5:** Best for ControlNet (current)
        - **9-12:** Strict, sharp but may over-saturate
        - **13+:** Not recommended
        
        **With ControlNet:** 7.0-7.5 is ideal to prevent conflict
        """)
        
        st.markdown("---")
        
        # Denoise
        st.subheader("3️⃣ Denoise (How Much to Change)")
        denoise = st.slider(
            "How much the AI should change your image",
            min_value=0.0,
            max_value=1.0,
            value=float(workflow["5"]["inputs"].get("denoise", 1.0)),
            step=0.1,
            help="1.0 = complete regeneration, 0.0 = no change"
        )
        
        st.markdown(f"""
        **Current:** `{denoise}`
        
        **Effect:**
        - **0.0-0.3:** Minor tweaks only
        - **0.4-0.6:** Moderate img2img refinement
        - **0.7-0.9:** Major cleanup changes
        - ✅ **1.0:** Complete transformation (recommended)
        
        **With ControlNet:** 1.0 is ideal for rough→clean
        """)
        
        st.markdown("---")
        
        # Sampler
        st.subheader("4️⃣ Sampler")
        samplers = ["euler", "euler_a", "dpm_2", "dpm_2_ancestral", "heun", "dpm_fast", "lms", "ddim"]
        sampler = st.selectbox(
            "Noise reduction algorithm",
            options=samplers,
            index=samplers.index(workflow["5"]["inputs"].get("sampler_name", "euler")),
            help="Different algorithms produce different styles"
        )
        
        sampler_info = {
            "euler": "✅ Fast, clean, precise - Best for line art",
            "euler_a": "Fast, more varied - Good for artistic",
            "dpm_2": "Medium speed, smooth - Good for paintings",
            "heun": "Slow, excellent quality - Best details",
            "dpm_fast": "Very fast - Testing only"
        }
        
        st.info(sampler_info.get(sampler, "Good general-purpose sampler"))
        
        # Scheduler
        st.subheader("5️⃣ Scheduler")
        schedulers = ["simple", "normal", "karras", "exponential", "ddim_uniform"]
        scheduler = st.selectbox(
            "Step timing/spacing",
            options=schedulers,
            index=schedulers.index(workflow["5"]["inputs"].get("scheduler", "simple")),
            help="Controls how noise is removed across steps"
        )
        
        scheduler_info = {
            "simple": "✅ Uniform, predictable - Stable results",
            "karras": "More detail in early steps - Complex images",
            "normal": "Standard timing - General use"
        }
        
        st.info(scheduler_info.get(scheduler, ""))
    
    with col2:
        st.subheader("📊 Live Preview")
        
        # Visual indicator for CFG
        st.markdown("**CFG Scale Effect:**")
        if cfg < 6.0:
            st.warning("⚠️ May ignore prompt details")
        elif cfg <= 8.5:
            st.success("✅ Optimal balance")
        else:
            st.error("⚠️ Risk of over-saturation")
        
        # Steps efficiency chart
        st.markdown("**Steps Efficiency:**")
        efficiency = min(100, int((steps / 30) * 95))
        st.progress(efficiency / 100)
        st.caption(f"{efficiency}% quality at {steps} steps")
        
        # Denoise mode
        st.markdown("**Denoise Mode:**")
        if denoise < 0.4:
            st.info("🔧 Minor tweaks")
        elif denoise < 0.7:
            st.info("🎨 Refinement")
        elif denoise < 1.0:
            st.info("🔨 Major changes")
        else:
            st.success("✨ Full generation")

# ====================
# TAB 2: ControlNet Parameters (Structure Control)
# ====================
with tab2:
    st.header("🎮 Structure Control Settings")
    st.markdown("_These settings control how the AI keeps the pose and anatomy of your character_")
    st.info("💡 **What is this?** These settings help the AI understand your character's pose while still being able to fix anatomy problems.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📍 Line Detection Control")
        st.caption("Controls how strictly the AI follows the lines in your drawing")
        
        # Lineart Strength
        lineart_strength = st.slider(
            "Line Following Strength",
            min_value=0.0,
            max_value=1.5,
            value=float(workflow["39"]["inputs"].get("controlnet_strength_1", 0.8)),
            step=0.1,
            help="Higher values = AI follows your lines more closely. Lower = more freedom to fix problems."
        )
        
        st.markdown(f"""
        **Current:** `{lineart_strength}`
        
        **Effect:**
        - **0.5-0.6:** Loose interpretation
        - ✅ **0.7-0.8:** Balanced (recommended)
        - **0.9-1.0:** Strict following
        - **1.1+:** Very strict, may be too rigid
        """)
        
        # Lineart End Percent (CRITICAL)
        st.markdown("### 🔥 When to Stop Following Lines")
        st.caption("**This is the most important setting!** It controls when the AI stops following your lines and can freely fix anatomy.")
        lineart_end = st.slider(
            "Stop following lines at this percentage",
            min_value=0.4,
            max_value=1.0,
            value=float(workflow["39"]["inputs"].get("end_percent_1", 0.7)),
            step=0.1,
            help="⭐ This enables anatomy correction! Lower = more freedom to fix face/hands"
        )
        
        release_step = int(steps * lineart_end)
        freedom_steps = steps - release_step
        
        if lineart_end >= 0.9:
            end_status = "🔴 Too high - No anatomy fixes"
        elif lineart_end >= 0.7:
            end_status = "✅ Optimal - Good anatomy correction"
        elif lineart_end >= 0.5:
            end_status = "🟡 Low - Maximum freedom, may lose pose"
        else:
            end_status = "🔴 Too low - Will lose pose"
        
        st.markdown(f"""
        **Current:** `{lineart_end}` → {end_status}
        
        **Release Point:** Step {release_step}/{steps}  
        **Freedom Window:** {freedom_steps} steps to fix anatomy
        
        **Effect:**
        - **1.0:** ❌ No anatomy fixes (active entire process)
        - **0.9:** ⚠️ Minimal fixes (3 steps)
        - **0.8:** ⚠️ Limited fixes (6 steps)
        - ✅ **0.7:** Good fixes (9 steps) - **Recommended**
        - **0.6:** Better fixes (12 steps)
        - **0.5:** ⚠️ May lose pose (15 steps)
        
        **How it works:**
        ```
        Steps 1-{release_step}: Follow rough sketch structure
        Steps {release_step+1}-{steps}: AI fixes face/hands/anatomy
        ```
        """)
        
        st.markdown("---")
        
        st.subheader("📍 Canny ControlNet")
        
        # Canny Strength
        canny_strength = st.slider(
            "Canny Strength",
            min_value=0.0,
            max_value=1.5,
            value=float(workflow["39"]["inputs"].get("controlnet_strength_2", 0.6)),
            step=0.1,
            help="How strongly canny influences edges"
        )
        
        st.markdown(f"""
        **Current:** `{canny_strength}`
        
        **Typically lower than Lineart** (0.5-0.7)
        """)
        
        # Canny End Percent
        canny_end = st.slider(
            "Canny End Percent",
            min_value=0.4,
            max_value=1.0,
            value=float(workflow["39"]["inputs"].get("end_percent_2", 0.6)),
            step=0.1,
            help="Usually released earlier than Lineart for edge smoothing"
        )
        
        canny_release = int(steps * canny_end)
        
        st.markdown(f"""
        **Current:** `{canny_end}`
        
        **Release Point:** Step {canny_release}/{steps}
        
        **Strategy:** Release Canny earlier ({canny_end}) than Lineart ({lineart_end})
        - Canny smooths edges first
        - Lineart maintains pose longer
        - Both release for final anatomy fixes
        """)
    
    with col2:
        st.subheader("📊 ControlNet Strategy")
        
        # Visual timeline
        st.markdown("**Release Timeline:**")
        
        # Canny phase
        st.markdown(f"**Steps 1-{canny_release}:** Canny ACTIVE")
        st.progress(canny_end)
        
        # Lineart phase
        st.markdown(f"**Steps 1-{release_step}:** Lineart ACTIVE")
        st.progress(lineart_end)
        
        # Freedom phase
        st.markdown(f"**Steps {release_step+1}-{steps}:** BOTH RELEASED")
        st.success(f"✨ {freedom_steps} steps for anatomy correction")
        
        st.markdown("---")
        
        # Recommendations
        st.markdown("**Quick Presets:**")
        
        if st.button("⚡ More Anatomy Freedom"):
            st.session_state['lineart_end'] = 0.6
            st.session_state['canny_end'] = 0.5
            st.rerun()
        
        if st.button("🔒 More Pose Control"):
            st.session_state['lineart_end'] = 0.8
            st.session_state['canny_end'] = 0.7
            st.rerun()
        
        if st.button("⚖️ Balanced (Recommended)"):
            st.session_state['lineart_end'] = 0.7
            st.session_state['canny_end'] = 0.6
            st.rerun()

# ====================
# TAB 3: Preprocessors
# ====================
with tab3:
    st.header("🔧 Preprocessor Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📏 LineArt Preprocessor")
        
        lineart_coarse = st.selectbox(
            "Coarse Mode",
            options=["disable", "enable"],
            index=0 if workflow["19"]["inputs"].get("coarse", "disable") == "disable" else 1,
            help="Simplifies line detection"
        )
        
        st.markdown(f"""
        **Current:** `{lineart_coarse}`
        
        - ✅ **disable:** Detailed lines (cleanup/tie down)
        - **enable:** Simplified lines (sketch/roughs)
        """)
        
        lineart_resolution = st.slider(
            "Resolution",
            min_value=512,
            max_value=2048,
            value=workflow["19"]["inputs"].get("resolution", 1920),
            step=128,
            help="Processing resolution for line detection"
        )
        
        st.markdown(f"""
        **Current:** `{lineart_resolution}px`
        
        - **512-1024:** Fast, good for testing
        - **1024-1536:** Standard quality
        - ✅ **1920:** High quality (current)
        """)
    
    with col2:
        st.subheader("🎯 Canny Preprocessor")
        
        canny_low = st.slider(
            "Low Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(workflow["20"]["inputs"].get("low_threshold", 0.4)),
            step=0.1,
            help="Weak edge detection sensitivity"
        )
        
        canny_high = st.slider(
            "High Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(workflow["20"]["inputs"].get("high_threshold", 0.8)),
            step=0.1,
            help="Strong edge detection sensitivity"
        )
        
        st.markdown(f"""
        **Current:** Low `{canny_low}`, High `{canny_high}`
        
        **Effect:**
        - **Low 0.2-0.3:** Detects even faint edges (messy sketches)
        - ✅ **Low 0.4, High 0.8:** Balanced (clean sketches)
        - **Low 0.5+:** Only strong edges (final artwork)
        """)

# ====================
# TAB 4: Summary & Export
# ====================
with tab4:
    st.header("📊 Configuration Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 KSampler")
        st.code(f"""
Steps:     {steps}
CFG:       {cfg}
Denoise:   {denoise}
Sampler:   {sampler}
Scheduler: {scheduler}
        """)
        
        st.subheader("🎮 ControlNet")
        st.code(f"""
Lineart Strength: {lineart_strength}
Lineart End:      {lineart_end} (release at step {release_step})
Canny Strength:   {canny_strength}
Canny End:        {canny_end} (release at step {canny_release})
        """)
    
    with col2:
        st.subheader("🔧 Preprocessors")
        st.code(f"""
LineArt Coarse:   {lineart_coarse}
LineArt Res:      {lineart_resolution}px
Canny Low:        {canny_low}
Canny High:       {canny_high}
        """)
        
        st.subheader("📈 Analysis")
        
        # Quality estimate
        quality = min(100, int((steps / 35) * 100))
        st.metric("Estimated Quality", f"{quality}%")
        
        # Anatomy freedom
        anatomy_freedom = int((1.0 - lineart_end) * 100)
        st.metric("Anatomy Freedom", f"{anatomy_freedom}%")
        
        # Generation time estimate
        time_estimate = int(steps * 2)  # rough estimate: 2 sec per step
        st.metric("Est. Generation Time", f"{time_estimate}s")
    
    st.markdown("---")
    
    # Save/Export
    st.subheader("💾 Save Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Save to Workflow", type="primary"):
            # Update workflow with current values
            workflow["5"]["inputs"]["steps"] = steps
            workflow["5"]["inputs"]["cfg"] = cfg
            workflow["5"]["inputs"]["denoise"] = denoise
            workflow["5"]["inputs"]["sampler_name"] = sampler
            workflow["5"]["inputs"]["scheduler"] = scheduler
            
            workflow["39"]["inputs"]["controlnet_strength_1"] = lineart_strength
            workflow["39"]["inputs"]["end_percent_1"] = lineart_end
            workflow["39"]["inputs"]["controlnet_strength_2"] = canny_strength
            workflow["39"]["inputs"]["end_percent_2"] = canny_end
            
            workflow["19"]["inputs"]["coarse"] = lineart_coarse
            workflow["19"]["inputs"]["resolution"] = lineart_resolution
            workflow["20"]["inputs"]["low_threshold"] = canny_low
            workflow["20"]["inputs"]["high_threshold"] = canny_high
            
            save_workflow(workflow)
            st.success("✅ Saved to workflows/ANIMATION_M1_api_version.json")
    
    with col2:
        if st.button("📋 Copy as JSON"):
            config = {
                "steps": steps,
                "cfg": cfg,
                "denoise": denoise,
                "sampler": sampler,
                "scheduler": scheduler,
                "lineart_strength": lineart_strength,
                "lineart_end": lineart_end,
                "canny_strength": canny_strength,
                "canny_end": canny_end
            }
            st.code(json.dumps(config, indent=2))
    
    with col3:
        if st.button("🔄 Reset to Default"):
            st.session_state.clear()
            st.rerun()
    
    # Comparison with current
    st.markdown("---")
    st.subheader("📊 Comparison with Saved Settings")
    
    current_cfg = workflow["5"]["inputs"].get("cfg", 7.5)
    current_lineart_end = workflow["39"]["inputs"].get("end_percent_1", 0.7)
    
    if abs(cfg - current_cfg) > 0.1 or abs(lineart_end - current_lineart_end) > 0.05:
        st.warning("⚠️ You have unsaved changes!")
    else:
        st.info("✅ Current settings match saved configuration")

# Footer
st.markdown("---")
st.caption("💡 **Tip:** Start with 'Standard Cleanup' preset, then adjust one parameter at a time")
st.caption("📖 **Documentation:** See the Documentation page (sidebar) for detailed explanations")

