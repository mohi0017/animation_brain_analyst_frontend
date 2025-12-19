"""
Documentation Viewer - View all project documentation in one place
"""

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Documentation - AI Animation Studio",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Project Documentation")
st.markdown("Complete documentation for AI Animation Studio")
st.markdown("---")

# Documentation files
DOCS_DIR = Path(__file__).parent.parent / "docs"

docs = {
    "📖 Parameters Guide": "PARAMETERS_GUIDE.md",
    "🎮 ControlNet Anatomy Strategy": "CONTROLNET_ANATOMY_STRATEGY.md",
    "🔧 ComfyUI Integration": "COMFYUI_INTEGRATION.md",
    "📋 Technical Report": "TECHNICAL_REPORT.md",
}

# Sidebar navigation
with st.sidebar:
    st.header("📑 Documentation")
    selected_doc = st.radio(
        "Select Document",
        options=list(docs.keys()),
        index=0
    )
    
    st.markdown("---")
    st.markdown("### 🔗 Quick Links")
    st.markdown("- [Streamlit Documentation](https://docs.streamlit.io)")
    st.markdown("- [ComfyUI Documentation](https://github.com/comfyanonymous/ComfyUI)")
    st.markdown("- [Gemini API Docs](https://ai.google.dev/docs)")

# Display selected documentation
doc_file = docs[selected_doc]
doc_path = DOCS_DIR / doc_file

if doc_path.exists():
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Display the markdown content
    st.markdown(content, unsafe_allow_html=True)
    
    # Download button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.download_button(
            label=f"📥 Download {doc_file}",
            data=content,
            file_name=doc_file,
            mime="text/markdown",
            use_container_width=True
        )
else:
    st.error(f"❌ Documentation file not found: {doc_path}")
    st.info("Please ensure the docs/ directory contains all documentation files.")

# Footer
st.markdown("---")
st.caption("💡 **Tip:** Use the sidebar to navigate between different documentation files")
st.caption("📖 **Note:** You can download any documentation file using the download button")

