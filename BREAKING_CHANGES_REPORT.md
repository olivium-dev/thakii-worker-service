# Breaking Changes Report

## Overview
This report details all breaking changes introduced in commits `cf625d0` and `adc1ab6` that implement logarithmic threshold for scene detection. These changes were made on the branch `fix/github-actions-inputs-proper-interpolation` after commit `4300cc8` from PR [#1](https://github.com/olivium-dev/thakii-worker-service/pull/1).

## Summary
The changes fundamentally altered the scene detection algorithm from a fixed pixel-count threshold to a dynamic logarithmic percentage-based threshold. This introduced **6 major breaking changes** that affect configuration, behavior, and output.

---

## Breaking Changes Table

| # | Category | Change | Before (PR #1) | After (Current) | Impact Level | Affected Components |
|---|----------|--------|----------------|-----------------|--------------|---------------------|
| 1 | **Constructor Signature** | Removed `min_change` parameter | `__init__(threshold, min_change, min_segment_duration)` | `__init__(threshold, min_segment_duration)` | 🔴 **CRITICAL** | All code instantiating `VideoSegmentFinder` |
| 2 | **Environment Variable** | `MIN_CHANGE` no longer used | Used: `MIN_CHANGE=10000` | Ignored (not read) | 🔴 **CRITICAL** | Deployment configs, `.env` files, GitHub Actions |
| 3 | **Environment Variable** | `MAX_SEGMENTS` no longer used | Used: `MAX_SEGMENTS=10` (limits output) | Removed (no limit enforcement) | 🔴 **CRITICAL** | Output size control, pagination logic |
| 4 | **Detection Algorithm** | Removed `PastFrameChangesTracker` class | Required "stable frames" before detection | Uses rolling window + spike detection | 🟠 **HIGH** | Scene detection logic |
| 5 | **Threshold Calculation** | Changed from fixed to dynamic logarithmic | Fixed: 10,000 pixels must change | Dynamic: `15 * log10(duration)` % of pixels | 🟠 **HIGH** | Detection sensitivity |
| 6 | **Output Guarantees** | Removed minimum segment guarantee | Always guaranteed at least 2 segments | No minimum, can return 1 or 0 segments | 🟠 **HIGH** | PDF generation reliability |

---

## Detailed Analysis

### 1. Constructor Signature Change
**Breaking Change:** The `VideoSegmentFinder` constructor no longer accepts `min_change` parameter.

#### Before (PR #1 - commit 4300cc8):
```python
def __init__(self, threshold=None, min_change=None, min_segment_duration=None):
    self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 15))
    self.min_change = min_change or int(os.getenv('MIN_CHANGE', 10000))
    self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
```

#### After (Current - commit cf625d0):
```python
def __init__(self, threshold=None, min_segment_duration=None):
    self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 15))
    self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
    # min_change parameter REMOVED
```

#### Impact:
- ✅ **No immediate breakage** because all current code uses `VideoSegmentFinder()` without arguments
- ⚠️ **Potential breakage** if any external code or future code tries to pass `min_change` parameter
- 🔧 **Configuration ignored**: `MIN_CHANGE` environment variable is completely ignored

#### Affected Code Locations:
- `src/main.py:49` - `video_segment_finder = VideoSegmentFinder()`
- `src/video_segment_finder.py:235` - Test code
- `src/content_segment_exporter.py:88` - Example code
- `src/plot.py:71` - Plot utility
- `generate_real_transcription.py:25` - Helper script
- All test files in `tests/test_video_segment_finder.py`

---

### 2. MIN_CHANGE Environment Variable Obsolete
**Breaking Change:** The `MIN_CHANGE` configuration parameter is no longer read or used.

#### Before:
```bash
# env.example (PR #1)
MIN_CHANGE=10000  # Minimum pixel changes to detect scene
```

```python
# Used in algorithm
self.min_change = min_change or int(os.getenv('MIN_CHANGE', 10000))
has_changed = results["num_pixels_changed"] > self.min_change
```

#### After:
```bash
# env.example (Current - still present but unused)
MIN_CHANGE=10000  # ⚠️ THIS IS IGNORED
```

```python
# Algorithm now calculates dynamically
min_change_percentage = 15 * math.log10(duration_seconds)
min_change_pixels = int(total_pixels * (min_change_percentage / 100.0))
```

#### Impact:
- 🔴 **Deployment configurations** that set `MIN_CHANGE` will have **no effect**
- 🔴 **GitHub Actions workflow** inputs for `MIN_CHANGE` will be **silently ignored**
- 🔴 **Documentation/PR #1** shows `MIN_CHANGE` as configurable, but it **no longer works**
- ⚠️ The `env.example` file **still contains** `MIN_CHANGE=10000` (misleading)

#### Migration Required:
```bash
# OLD CONFIG (no longer works):
MIN_CHANGE=10000

# NEW BEHAVIOR (automatic):
# For 100-second video: 30% of pixels = 276,480 pixels (for 1280x720)
# For 800-second video: 43% of pixels = 401,653 pixels (for 1280x720)
# Cannot be configured via environment variable
```

---

### 3. MAX_SEGMENTS Environment Variable Removed
**Breaking Change:** The `MAX_SEGMENTS` configuration parameter has been completely removed from the algorithm.

#### Before (PR #1):
```python
# Video segment finder enforced maximum
max_segments = int(os.getenv('MAX_SEGMENTS', 10))
if len(selected_frames) > max_segments:
    print(f"🔧 Reducing {len(selected_frames)} segments to {max_segments} for better text coherence")
    # Keep evenly distributed segments
    frame_nums = sorted(selected_frames.keys())
    keep_every = len(frame_nums) // max_segments
    # ... reduce to max_segments
```

#### After (Current):
```python
# MAX_SEGMENTS check completely removed
# No limit enforcement at all
print(f"✅ Final scenes after filtering: {len(selected_frames)} screenshots")
# Can return any number of frames
```

#### Impact:
- 🔴 **No upper bound** on number of PDF pages generated
- 🔴 **Deployment configurations** setting `MAX_SEGMENTS` are **completely ignored**
- 🔴 **PR #1 testing** validated with `MAX_SEGMENTS=15`, but this is **no longer functional**
- ⚠️ Videos with many scene changes could generate **hundreds of pages**
- ⚠️ The `env.example` file **still contains** `MAX_SEGMENTS=10` (misleading)

#### Real-World Impact Example:
```
Test Video (804 seconds):
- Before (with MAX_SEGMENTS=10): Guaranteed ≤ 10 pages
- After (no limit): 9 pages detected (happened to be reasonable)

Hypothetical Action Movie (2 hours, many cuts):
- Before (with MAX_SEGMENTS=10): Would be capped at 10 pages
- After (no limit): Could generate 50+ pages
```

---

### 4. Detection Algorithm Complete Rewrite
**Breaking Change:** The fundamental scene detection logic changed from "stable frames" to "rolling window with spike detection".

#### Before (PR #1) - Stable Frame Algorithm:
```python
class PastFrameChangesTracker:
    def __init__(self):
        self.prev_frame_changes = [False, False, False, False, False]
    
    def are_previous_frames_stable(self):
        return sum([1 if x else 0 for x in self.prev_frame_changes]) == 0

prev_video_changes = PastFrameChangesTracker()

# Only save frame if previous frames were stable AND current changed
if prev_video_changes.are_previous_frames_stable() and has_changed:
    save_frame = True
```

**Algorithm Logic**: Required ALL previous 5 frames to have NO changes before saving a new frame.

#### After (Current) - Rolling Window with Spike Detection:
```python
# ENHANCED: Rolling window of recent changes
recent_changes = []  # Store recent pixel change counts
window_size = 5

# Track actual change amounts
recent_changes.append(num_pixels_changed)
if len(recent_changes) > window_size:
    recent_changes.pop(0)

# Detect scene change when:
# 1. Current frame has significant change (above logarithmic threshold)
# 2. This change is notably higher than recent average (spike)
is_significant_change = num_pixels_changed > min_change_pixels
is_spike = num_pixels_changed > (avg_recent * 1.5)

if is_significant_change and is_spike:
    save_frame()
```

**Algorithm Logic**: Detects spikes above baseline motion, adapts to video content.

#### Impact:
- 🟠 **Completely different detection behavior**
- 🟠 **Videos with continuous motion** (lectures, talking heads) now work correctly
- 🟠 **Static videos** may detect fewer scenes
- 🟠 **Output consistency broken**: Same video will produce different results before/after

#### Behavioral Comparison:
| Video Type | Before (Stable Frames) | After (Rolling Window) |
|------------|----------------------|----------------------|
| Static slides + transitions | ✅ Works well | ✅ Works well |
| Talking head (continuous motion) | ❌ Only 1-2 frames detected | ✅ Detects scene changes |
| Action scenes | ❌ No frames after first | ✅ Detects major changes |
| Very static content | ✅ Good | ⚠️ May detect less |

---

### 5. Threshold Calculation Changed from Fixed to Dynamic
**Breaking Change:** The minimum change threshold is no longer a fixed pixel count but a dynamic percentage based on video duration.

#### Before (PR #1):
```python
# Fixed threshold from configuration
self.min_change = 10000  # Always 10,000 pixels

# Same threshold for all videos regardless of length
has_changed = results["num_pixels_changed"] > self.min_change
```

#### After (Current):
```python
# Dynamic logarithmic calculation
duration_seconds = total_frames / fps
min_change_percentage = 15 * math.log10(duration_seconds)
min_change_percentage = max(5.0, min(min_change_percentage, 50.0))  # 5-50% range
min_change_pixels = int(total_pixels * (min_change_percentage / 100.0))

# Threshold varies by video length
is_significant_change = num_pixels_changed > min_change_pixels
```

#### Impact Examples:

| Video Duration | Resolution | Before (Fixed) | After (Dynamic) | Ratio |
|---------------|-----------|---------------|----------------|-------|
| 10 seconds | 1280x720 | 10,000 pixels | 138,240 pixels (15%) | 13.8x higher |
| 100 seconds | 1280x720 | 10,000 pixels | 276,480 pixels (30%) | 27.6x higher |
| 804 seconds | 1280x720 | 10,000 pixels | 401,653 pixels (43.6%) | 40.2x higher |
| 1000 seconds | 1280x720 | 10,000 pixels | 414,720 pixels (45%) | 41.5x higher |

#### Impact:
- 🟠 **Dramatically higher thresholds** for most videos (10-40x increase)
- 🟠 **Fewer scenes detected** for long videos (more selective)
- 🟠 **Different PDF page counts** for same videos
- 🟠 **Cannot be overridden** via configuration

#### Real Impact on Test Video:
```
Test video (804 seconds, 1280x720):
- Before: 10,000 pixels threshold → Would detect many scenes
- After: 401,653 pixels threshold (40x higher) → Detected 9 scenes

Result: Much more selective, only major scene changes captured
```

---

### 6. Minimum Segment Guarantee Removed
**Breaking Change:** The algorithm no longer guarantees a minimum number of segments.

#### Before (PR #1):
```python
# MINIMUM SEGMENT GUARANTEE: Ensure we always have at least 2 segments
if len(selected_frames) < 2:
    print(f"⚠️ Only {len(selected_frames)} segments found, creating minimum segments...")
    
    # Create at least 2 segments from the video
    video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret1, frame1 = video_reader.read()
    # ... get middle frame
    
    selected_frames = {
        0: {"timestamp": timestamp1, "frame": frame1},
        total_frames // 2: {"timestamp": timestamp2, "frame": frame2}
    }
    print(f"✅ Minimum segments created: {len(selected_frames)}")
```

#### After (Current):
```python
# No minimum guarantee - removed entirely
print(f"✅ Final scenes after filtering: {len(selected_frames)} screenshots")
# Can return 0, 1, or any number
```

#### Impact:
- 🟠 **Videos with no detected changes** could return 0-1 segments
- 🟠 **PDF generation may fail** if insufficient frames
- 🟠 **No fallback mechanism** for edge cases
- ⚠️ Particularly risky for very static videos or very short videos

#### Risk Scenarios:
```
Scenario 1: Very static video (lecture with no slide changes)
- Before: Guaranteed 2 segments (start + middle)
- After: Could detect 0-1 segments → PDF may be incomplete

Scenario 2: Very short video (< 10 seconds)
- Before: Guaranteed 2 segments minimum
- After: May only detect 1 segment → Single-page PDF

Scenario 3: Video processing failure
- Before: Always had fallback to create 2 segments
- After: No fallback, could fail completely
```

---

## Configuration File Impact

### env.example Changes Needed

#### Current State (Misleading):
```bash
# PDF Generation Configuration
# Video Analysis Parameters
VIDEO_THRESHOLD=15          # ✅ Still used
MIN_CHANGE=10000            # ❌ IGNORED - No longer used
MIN_SEGMENT_DURATION=2000   # ✅ Still used
MAX_SEGMENTS=10             # ❌ IGNORED - No longer used
```

#### Should Be (Accurate):
```bash
# PDF Generation Configuration
# Video Analysis Parameters
VIDEO_THRESHOLD=15          # Pixel difference threshold for scene detection
MIN_SEGMENT_DURATION=2000   # Minimum duration between segments (ms)

# REMOVED PARAMETERS (no longer configurable):
# - MIN_CHANGE: Now calculated dynamically using logarithmic formula
#   Formula: min_change_percentage = 15 * log10(duration_seconds)
#   Range: 5% - 50% of total pixels
# - MAX_SEGMENTS: No longer enforced, unlimited pages possible
```

---

## GitHub Actions Workflow Impact

### From PR #1:
The deployment workflow (`deploy-worker-service.yml`) accepts these inputs:

```yaml
inputs:
  video_threshold:
    description: 'Minimum pixel difference for scene detection'
    default: '15'
  max_segments:
    description: 'Maximum number of PDF segments/pages'  # ❌ NO LONGER WORKS
    default: '10'
  # ... other inputs
```

### Impact:
- 🔴 `max_segments` input is **completely non-functional**
- 🔴 Workflow still accepts this input but **it has zero effect**
- 🔴 PR #1 was tested with `max_segments=15` but **this test is now invalid**

---

## Deployment Risks

### Configuration Drift
| Configuration Location | Status | Risk |
|----------------------|--------|------|
| `env.example` | Contains obsolete `MIN_CHANGE`, `MAX_SEGMENTS` | 🔴 Misleading |
| GitHub Actions inputs | Accepts obsolete `max_segments` | 🔴 Non-functional |
| Production `.env` files | May still set obsolete variables | 🟡 Harmless but confusing |
| Documentation/PR #1 | Shows configuration that no longer works | 🔴 Incorrect |

### Behavioral Changes in Production
| Scenario | Before Deployment | After Deployment | Risk |
|----------|------------------|------------------|------|
| Long videos (>10 min) | Controlled by `MAX_SEGMENTS=10` | Unlimited pages | 🔴 High |
| Static videos | Guaranteed 2+ segments | May get 0-1 segments | 🟠 Medium |
| Videos with motion | Poor detection (1-2 frames) | Good detection (many frames) | 🟢 Improvement |
| Configured thresholds | `MIN_CHANGE` respected | `MIN_CHANGE` ignored | 🔴 High |

---

## Migration Recommendations

### 1. Update Configuration Files
```bash
# Remove obsolete variables from env.example
- MIN_CHANGE=10000
- MAX_SEGMENTS=10

# Add documentation
# Note: Scene detection threshold is now automatic
# Formula: 15 * log10(duration_seconds) % of pixels
```

### 2. Update GitHub Actions Workflow
```yaml
# Remove non-functional input
inputs:
  video_threshold:
    description: 'Minimum pixel difference for scene detection'
    default: '15'
  # REMOVE: max_segments (no longer functional)
```

### 3. Add Output Safeguards
Consider adding back some safety limits:
```python
# Suggested safeguard in video_segment_finder.py
MAX_PAGES_WARNING = 50
if len(selected_frames) > MAX_PAGES_WARNING:
    print(f"⚠️ Warning: {len(selected_frames)} pages detected (very high)")

MIN_PAGES_WARNING = 2
if len(selected_frames) < MIN_PAGES_WARNING:
    print(f"⚠️ Warning: Only {len(selected_frames)} pages detected")
```

### 4. Update Tests
The test suite in `tests/test_video_segment_finder.py` has hardcoded expected values:
```python
# These assertions may now fail:
self.assertEqual(len(frame_nums), 7)   # May be different now
self.assertEqual(len(frame_nums), 12)  # May be different now
```

### 5. Document Breaking Changes
Update `README.md` or create `CHANGELOG.md`:
```markdown
## Version X.X.X - Breaking Changes
- Removed `MIN_CHANGE` configuration parameter
- Removed `MAX_SEGMENTS` configuration parameter
- Changed scene detection algorithm to logarithmic threshold
- No longer guarantees minimum number of segments
```

---

## Testing Recommendations

### Before Deploying to Production:

1. **Test with representative videos:**
   ```bash
   # Short video (< 1 min)
   # Medium video (5-15 min) 
   # Long video (> 30 min)
   # Static content video
   # Action/motion video
   ```

2. **Compare output with PR #1 baseline:**
   ```bash
   # Checkout PR #1 version
   git checkout 4300cc8
   python -m src.main test.mp4 -o output_old.pdf
   
   # Checkout current version
   git checkout HEAD
   python -m src.main test.mp4 -o output_new.pdf
   
   # Compare page counts
   ```

3. **Verify edge cases:**
   - Video with no scene changes
   - Very short video (< 5 seconds)
   - Very long video (> 1 hour)
   - Video with continuous motion

4. **Load test:**
   - Process multiple videos to check for consistent behavior
   - Monitor memory usage (unlimited segments could use more memory)

---

## Rollback Plan

If issues are discovered in production:

### Quick Rollback (Revert to PR #1):
```bash
# Revert the breaking change commits
git revert adc1ab6  # Revert docs
git revert cf625d0  # Revert logarithmic implementation
git push origin fix/github-actions-inputs-proper-interpolation

# Or reset to PR #1 state
git reset --hard 4300cc8
git push --force origin fix/github-actions-inputs-proper-interpolation
```

### Gradual Migration (Feature Flag):
Add a feature flag to switch between algorithms:
```python
USE_LOGARITHMIC_THRESHOLD = os.getenv('USE_LOGARITHMIC_THRESHOLD', 'true').lower() == 'true'

if USE_LOGARITHMIC_THRESHOLD:
    # New logarithmic algorithm
else:
    # Old fixed threshold algorithm
```

---

## Conclusion

### Breaking Change Summary:
- **6 major breaking changes** identified
- **2 configuration parameters** completely non-functional
- **1 algorithm** completely rewritten
- **1 safety guarantee** removed
- **0 migration path** provided in commits

### Risk Assessment:
- 🔴 **Critical**: Configuration drift and non-functional parameters
- 🟠 **High**: Algorithm behavior changes affecting output
- 🟢 **Low**: No immediate runtime errors (code still executes)

### Recommended Actions:
1. **Immediate**: Update `env.example` and workflow to remove obsolete parameters
2. **Before Deploy**: Test thoroughly with representative videos
3. **During Deploy**: Monitor for unexpected page count changes
4. **After Deploy**: Update documentation and close/comment on PR #1

### Next Steps:
- [ ] Clean up configuration files
- [ ] Update GitHub Actions workflow
- [ ] Add safeguards for extreme page counts
- [ ] Update test assertions
- [ ] Document changes in CHANGELOG
- [ ] Test with production videos before deploy

