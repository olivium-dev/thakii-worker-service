# macOS Fork Safety Issues with Redis Queue

## Problem

When using Redis Queue (RQ) with Python on macOS, you may encounter errors like:

```
objc[86815]: +[NSCheapMutableString initialize] may have been in progress in another thread when fork() was called.
objc[86815]: +[NSCheapMutableString initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint on objc_initializeAfterForkError to debug.
```

This is a known issue with Python's multiprocessing on macOS, where the `fork()` system call can cause problems with Apple's Objective-C runtime.

## Solution

There are two ways to fix this issue:

### 1. Set Environment Variable (Recommended)

Set the `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` environment variable to `YES` before running your Python script:

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
python3 rq_worker.py
```

Or in your Python code:

```python
import os
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
```

### 2. Use 'spawn' Instead of 'fork'

Alternatively, you can configure Python to use 'spawn' instead of 'fork' for creating new processes:

```python
import multiprocessing
multiprocessing.set_start_method('spawn')
```

However, this approach may not work with all libraries and can have performance implications.

## Implementation in Thakii Worker Service

We've implemented the environment variable solution in:

1. `rq_worker.py` - Sets the environment variable at runtime
2. LaunchDaemon plist - Sets the environment variable for the system service

## Testing

When testing locally, ensure the environment variable is set before running any scripts that use Redis Queue:

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
python3 test_local_video.py
```

## References

- [Python multiprocessing documentation](https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods)
- [RQ documentation](https://python-rq.org/docs/)
- [macOS fork() safety discussion](https://github.com/python/cpython/issues/77559)
