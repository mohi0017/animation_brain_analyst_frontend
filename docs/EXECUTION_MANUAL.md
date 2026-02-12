# Comprehensive Execution Manual
**AI Animation Cleanup, Style Transfer & Motion Preservation**

**Client:** Animation Production Studio  
**Project Duration:** Dec 12, 2025 – Feb 12, 2026 (8 Weeks)  
**Capacity:** 5 Hours/Day, Mon-Fri Only  
**Architecture:** 6-Stage Hybrid Pipeline (ComfyUI + ControlNet)  
**Lead Technical Architect:** [Your Name]  
**Date:** December 14, 2025

---

## 1. Executive Summary

This document serves as the master technical blueprint for the development of the AI Animation Cleanup System. It expands the initial roadmap into a granular, task-by-task execution guide.

The system utilizes a rigid 6-Stage Pipeline to decouple motion from appearance. By leveraging ControlNet for geometric constraints and Custom LoRAs for phase mapping (Rough → Clean), we guarantee 100% frame-count preservation while automating the labor-intensive "cleanup" and "coloring" stages of 2D animation.

### Core Technical Mandates
*   **100% Motion Lock:** No frame interpolation. No hallucinated movement.
*   **Phase Awareness:** The system mathematically distinguishes between "Rough," "Tiedown," and "Clean" states.
*   **Non-Destructive Style Transfer:** Style is applied as a "skin" over the existing motion "skeleton."
*   **Transparent Output:** All characters are isolated on RGBA backgrounds using BiRefNet.
*   **Automated Verification:** Every output is mathematically checked against the input using Optical Flow before delivery.

---

## 2. Resource Planning & Milestone Schedule

**Capacity Constraints & Rules:**
*   **Working Days:** Monday - Friday (Weekends OFF).
*   **Daily Capacity:** 5 Hours/Day (25 Hours/Week).
*   **Continuity Rule:** Next Milestone starts the immediate next working day after the previous one ends.
*   **Holidays:** Dec 25 (Christmas) and Jan 1 (New Year) are non-working days.

| Milestone | Core Deliverable | Start Date | End Date |
| :--- | :--- | :--- | :--- |
| **M1** | Motion-Lock Engine | Dec 12 (Fri) | Dec 19 (Fri) |
| **M3** | Style Transfer & Retargeting | Dec 22 (Mon) | Dec 30 (Tue) |
| **M3** | Phase Translation (LoRA) | Dec 31 (Wed) | Jan 14 (Wed) |
| **M4** | Consistency & Fail-Safe | Jan 15 (Thu) | Jan 27 (Tue) |
| **M5** | Web Platform | Jan 28 (Wed) | Feb 11 (Wed) |
| **Final** | Project Closure | Feb 12 (Thu) | Feb 12 (Thu) |

---

## 3. Detailed Execution Plan

### 3.1 Milestone 1: The Motion-Lock Engine (Dec 12 - Dec 19)
**Focus:** Infrastructure Setup & Motion Constraints.

*   **Day 1 (Fri, Dec 12): Infrastructure**
    *   Task 1.1: Provision RunPod GPU (RTX 4090).
    *   Task 1.2: Configure Persistent Volume mapping.
    *   Task 1.3: Install ComfyUI & Manager.
*   **Day 2 (Mon, Dec 15): Model Ingestion**
    *   Task 1.4: Download Checkpoints (SD 1.5, DreamShaper).
    *   Task 1.5: Install ControlNet Models (Lineart, Canny, OpenPose).
    *   Task 1.6: Install ComfyUI-BiRefNet nodes.
*   **Day 3 (Tue, Dec 16): Skeleton Workflow**
    *   Task 1.7: Build basic ControlNet Graph.
    *   Task 1.8: Test on "Bouncing Ball" (Mechanical Motion).
*   **Day 4 (Wed, Dec 17): Stress Testing**
    *   Task 1.9: Test Resolution Scaling (512px vs 1024px).
    *   Task 1.10: Verify VRAM limits.
*   **Day 5 (Thu, Dec 18): Transparency Check**
    *   Task 1.11: Integrate BiRefNet.
    *   Task 1.12: Verify RGBA Output export.
*   **Day 6 (Fri, Dec 19): Buffer & Review**
    *   Task 1.13: Finalize M1 Deliverable. Prepare Demo Video.

### 3.2 Milestone 3: Style & Motion Transfer (Dec 22 - Dec 30)
**Focus:** IP-Adapter & OpenPose.

*   **Day 1 (Mon, Dec 22): Style Injection**
    *   Task 2.1: Install IP-Adapter Plus.
    *   Task 2.2: Calibrate Style Weights (0.6-0.8).
*   **Day 2 (Tue, Dec 23): OpenPose Setup**
    *   Task 2.3: Integrate OpenPose Preprocessors.
    *   Task 2.4: Test Character Retargeting.
*   **Day 3 (Wed, Dec 24): Logic Gates**
    *   Task 2.5: Implement "Cleanup" vs "Retarget" switch.
    *   *Note: Dec 25 is Holiday (Christmas).*
*   **Day 4 (Fri, Dec 26): Integration Testing**
    *   Task 2.6: Combine Style + Skeleton into one workflow.
*   **Day 5 (Mon, Dec 29): Optimization**
    *   Task 2.7: Optimize Latent Preview settings for speed.
*   **Day 6 (Tue, Dec 30): M3 Delivery**
    *   Task 2.8: Record Style Transfer Demos.

### 3.3 Milestone 3: Phase Mapping (Dec 31 - Jan 14)
**Focus:** Custom LoRA Training (Rough to Clean) - Optional Optimization.

*   **Days 1-2 (Wed, Dec 31 - Fri, Jan 2): Dataset Prep**
    *   *Note: Jan 1 is Holiday (New Year).*
    *   Task 3.1: Format 50 pairs of Rough/Clean images.
    *   Task 3.2: Captioning and Tagging.
*   **Days 3-4 (Mon, Jan 5 - Tue, Jan 6): Training Run 1**
    *   Task 3.3: Configure Kohya_ss.
    *   Task 3.4: Initial Training (Epoch 10).
*   **Days 5-6 (Wed, Jan 7 - Thu, Jan 8): Training Run 2 (Refinement)**
    *   Task 3.5: Analyze Loss curves.
    *   Task 3.6: Retrain with adjusted Learning Rate if needed.
*   **Days 7-10 (Fri, Jan 9 - Wed, Jan 14): Integration**
    *   Task 3.7: Embed LoRA into ComfyUI.
    *   Task 3.8: Develop "Line Density" Analyzer Node.

### 3.4 Milestone 4: Safety & Consistency (Jan 15 - Jan 27)
**Focus:** AnimateDiff & Optical Flow.

*   **Days 1-3 (Thu, Jan 15 - Mon, Jan 19): Temporal Logic**
    *   Task 4.1: Configure AnimateDiff Context Window (16 frames).
    *   Task 4.2: Implement Cross-Frame Attention.
*   **Days 4-7 (Tue, Jan 20 - Fri, Jan 23): Fail-Safe Engine**
    *   Task 4.3: Write MotionGuard.py (Optical Flow).
    *   Task 4.4: Define "Pass/Fail" Thresholds.
*   **Days 8-9 (Mon, Jan 26 - Tue, Jan 27): Stress Test & Delivery**
    *   Task 4.5: Run batch of 100 frames. Finalize M4.

### 3.5 Milestone 5: Web Platform (Jan 28 - Feb 11)
**Focus:** Frontend & Deployment.

*   **Days 1-3 (Wed, Jan 28 - Fri, Jan 30): API Wrapper**
    *   Task 5.1: Export JSON to RunPod Serverless.
    *   Task 5.2: Create Python Handler script.
*   **Days 4-6 (Mon, Feb 2 - Wed, Feb 4): Frontend Build**
    *   Task 5.3: Next.js Setup & Upload UI.
    *   Task 5.4: Video Player & Comparison Slider.
*   **Days 7-8 (Thu, Feb 5 - Fri, Feb 6): Business Logic**
    *   Task 5.5: Stripe Integration.
    *   Task 5.6: S3 Auto-Delete Policies.
*   **Days 9-11 (Mon, Feb 9 - Wed, Feb 11): Final Polish**
    *   Task 5.7: Load Testing (Simulate Users).
    *   Task 5.8: Final Handoff to Client.

---

## 4. Deliverables Checklist

*   [ ] **Source Code:** GitHub Repository (Frontend + Backend Wrappers).
*   [ ] **ComfyUI Workflow:** production_pipeline_v1.json.
*   [ ] **Custom Models:** Trained LoRA file (phase_mapper.safetensors).
*   [ ] **API Documentation:** Swagger/OpenAPI spec.
*   [ ] **Verification Report:** Results of Optical Flow stress tests.
