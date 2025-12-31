# M2 Workflow Parameters (Current Defaults)

These are the best current parameter values used by the M2 workflow files.

## IP-Adapter
- Weight: 0.6
- End: 0.8

## ControlNet Union
- Strength: 0.5
- End: 0.6

## ControlNet OpenPose
- Strength: 1.0
- End: 0.0

## KSampler 1
- Steps: 40
- CFG: 9
- Denoise: 0.8

## KSampler 2
- Steps: 40
- CFG: 9
- Denoise: 0.4

## Auto-Adaptive Rules (Implemented)

### Core Safe Constraints (never break)
- OpenPose strength >= 0.90
- Union strength >= 0.60
- OpenPose end fixed at 0.00 (background safety)
- Union end gap rule applies only when OpenPose end > 0
- IP-Adapter end < Union end
- KSampler2 denoise < KSampler1 denoise

### Input-Driven Adjustments
- Messy lines -> KS1 denoise +, Union strength/end +, IP weight/end -
- Clean lines -> KS1 denoise -, Union strength/end -, KS2 denoise +
- High anatomy risk -> OpenPose strength/end +, IP weight -
- Simple design -> KS1 denoise -, IP weight -
- Detailed design -> KS1 denoise +, IP weight + (keep IP end < Union end)
- Pose lock on -> OpenPose strength/end +, KS1 cfg mid
- Style lock on -> IP weight capped (unless style_match is true)
- CleanUp phase -> anatomy/structure priority (OpenPose/Union +, IP weight -)
- Tie Down phase -> reduce style influence (IP weight/end -, KS1 denoise capped)

### Issue-Based Overrides (optional signals)
- Over-processed -> KS2 denoise -, KS2 cfg -, IP weight -
- Pose drift -> OpenPose strength/end +, Union strength +, KS1 denoise -
- Lines too thin/weak -> KS2 cfg +, KS2 denoise + (slightly), Union strength +
