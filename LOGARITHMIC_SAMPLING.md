# Logarithmic Threshold for Intelligent Scene Detection

## Overview
The video segment finder uses **logarithmic calculation** to determine the **minimum change threshold** for detecting scene changes. This threshold represents the percentage of pixels that must change between frames to count as a new scene.

## Formula

```
min_change_percentage = 15 × log₁₀(duration_seconds)
```

### Key Constraint
- **100 seconds → 30% threshold** (as specified)
- This means 30% of pixels must change to detect a new scene in a 100-second video

### Mathematical Derivation
```
30 = k × log₁₀(100)
30 = k × 2
k = 15
```

## Threshold Scaling Examples

| Video Duration | Formula | Change Threshold |
|----------------|---------|------------------|
| 10 seconds | 15 × log₁₀(10) = 15 × 1.0 | **15%** |
| 100 seconds | 15 × log₁₀(100) = 15 × 2.0 | **30%** ✓ |
| 804 seconds | 15 × log₁₀(804) = 15 × 2.91 | **43.6%** |
| 1,000 seconds | 15 × log₁₀(1000) = 15 × 3.0 | **45%** |
| 10,000 seconds | 15 × log₁₀(10000) = 15 × 4.0 | **60%** (capped at 50%) |

## How It Works

The logarithmic threshold is used in an **enhanced intelligent scene detection** algorithm:

### 1. Calculate Dynamic Threshold
```python
# For 804-second video:
min_change_percentage = 15 * log10(804.4) = 43.6%
min_change_pixels = total_pixels * 0.436
```

### 2. Intelligent Scene Detection Features

#### A. Rolling Window Analysis
- Tracks recent 5 frames of pixel changes
- Calculates moving average to understand baseline motion
- Adapts to different video content types

#### B. Spike Detection
```python
# Detect significant scene changes:
is_significant = num_pixels_changed > min_change_pixels
is_spike = num_pixels_changed > (avg_recent * 1.5)

# Save frame if both conditions met:
if is_significant and is_spike:
    save_frame()
```

#### C. Dynamic Frame Sampling
- **Short videos (<60s)**: Check every 0.25 seconds
- **Medium videos (60s-30m)**: Check every 0.5 seconds  
- **Long videos (>30m)**: Check every 1 second

#### D. Post-Processing Filters
- Remove segments shorter than 2 seconds (glitches/noise)
- Remove initial blank frame
- Keep only meaningful scene transitions

### Benefits

✅ **Content-Aware**: Detects actual scene changes, not uniform intervals
✅ **Adaptive**: Threshold scales with video duration
✅ **Robust**: Works with continuous motion (lectures, presentations)
✅ **Efficient**: Dynamic frame sampling for performance
✅ **Clean**: Filters out noise and glitches
✅ **Real Transcription**: Uses Whisper AI for accurate subtitles

## Test Results

### Test Video: `test-video.mp4`
- **Duration**: 804.4 seconds (~13.4 minutes)
- **Resolution**: 1280×720 (921,600 pixels per frame)
- **FPS**: 29
- **Calculated Threshold**: 15 × log₁₀(804.4) = **43.6%**
- **Minimum Change**: 401,653 pixels must change
- **Detection Results**: 
  - Initial detections: 11 scene changes
  - After filtering: 9 final scenes
- **Output**: `output-enhanced.pdf` with **9 pages**
- **File Size**: 1.34 MB
- **Transcription**: 225 segments, 1,581 words (real Whisper AI transcription)

### Frame Detection Examples
The algorithm detected real scene transitions like:
- Speaker introduction → Main content
- Slide changes during presentation
- Significant visual transitions
- End of presentation

## Why Logarithmic Threshold?

Using logarithmic scaling for the change threshold is ideal because:

1. **Longer Videos Need Higher Bar**: As videos get longer, we want to capture only the most significant changes
2. **Prevents Over-Segmentation**: Without this, long videos would have hundreds of tiny segments
3. **Content Quality**: Forces algorithm to focus on major scene transitions, not minor movements
4. **Natural Scaling**: 10× longer video → ~15% higher threshold (not 10× higher)
5. **Balances Output**: Keeps PDF page count reasonable regardless of video duration

## Previous Approach Issues

The old algorithm had a critical flaw:

### Problem: "Stable Frame" Requirement
```python
# Old approach (BROKEN):
if prev_frames_all_stable() and current_frame_changed():
    save_frame()  # Only saves if previous 5 frames had NO changes
```

**Why it failed**: 
- Videos with continuous motion (lectures, talking heads) always have SOME pixel changes
- After first detection, previous frames are never "stable" again
- Result: Only 1-2 frames captured from entire video

### Solution: Rolling Window + Spike Detection
```python
# New approach (WORKS):
if current_change > min_threshold and current_change > (avg_recent * 1.5):
    save_frame()  # Detects spikes above baseline motion
```

**Why it works**:
- Adapts to baseline motion in the video
- Detects **relative** spikes, not absolute stability
- Works with any content type (static, motion, lectures, etc.)
- Logarithmic threshold prevents over-sensitivity

