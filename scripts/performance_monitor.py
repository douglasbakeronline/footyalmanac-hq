"""Performance monitoring and optimization utilities for footyalmanac-hq."""
import time
import json
import os
from datetime import datetime
from functools import wraps

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")

def timing_decorator(func):
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"⏱️  {func.__name__} took {duration:.2f}s", flush=True)
        log_performance(func.__name__, duration)
        return result
    return wrapper

def log_performance(operation, duration, metadata=None):
    """Log performance metrics to file."""
    path = os.path.join(DATA, "performance.json")
    
    try:
        with open(path) as f:
            logs = json.load(f)
    except:
        logs = []
    
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "operation": operation,
        "duration_seconds": round(duration, 3),
        "metadata": metadata or {}
    }
    
    logs.append(entry)
    
    # Keep last 1000 entries
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    with open(path, "w") as f:
        json.dump(logs, f, indent=1)

def get_performance_stats(operation=None, hours=24):
    """Get performance statistics for operations."""
    path = os.path.join(DATA, "performance.json")
    
    try:
        with open(path) as f:
            logs = json.load(f)
    except:
        return {}
    
    # Filter by operation if specified
    if operation:
        logs = [l for l in logs if l["operation"] == operation]
    
    # Filter by time window
    cutoff = time.time() - (hours * 3600)
    logs = [l for l in logs if time.mktime(time.strptime(l["timestamp"], "%Y-%m-%dT%H:%M:%S.%f")) > cutoff]
    
    if not logs:
        return {}
    
    durations = [l["duration_seconds"] for l in logs]
    
    return {
        "count": len(durations),
        "min": min(durations),
        "max": max(durations),
        "avg": sum(durations) / len(durations),
        "total": sum(durations)
    }

def check_cache_efficiency():
    """Analyze cache hit rates."""
    path = os.path.join(DATA, "performance.json")
    
    try:
        with open(path) as f:
            logs = json.load(f)
    except:
        return {"cache_hits": 0, "cache_misses": 0, "hit_rate": 0}
    
    gather_ops = [l for l in logs if l["operation"] == "gather"]
    
    # Cache hits are typically faster
    fast = sum(1 for op in gather_ops if op["duration_seconds"] < 2.0)
    slow = len(gather_ops) - fast
    
    hit_rate = (fast / len(gather_ops) * 100) if gather_ops else 0
    
    return {
        "cache_hits": fast,
        "cache_misses": slow,
        "hit_rate": round(hit_rate, 1),
        "total_ops": len(gather_ops)
    }

def analyze_bottlenecks(limit=10):
    """Identify slowest operations."""
    path = os.path.join(DATA, "performance.json")
    
    try:
        with open(path) as f:
            logs = json.load(f)
    except:
        return []
    
    # Sort by duration
    sorted_logs = sorted(logs, key=lambda x: x["duration_seconds"], reverse=True)
    
    return sorted_logs[:limit]

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance monitoring")
    parser.add_argument("--stats", action="store_true", help="Show performance stats")
    parser.add_argument("--cache", action="store_true", help="Show cache efficiency")
    parser.add_argument("--bottlenecks", action="store_true", help="Show slowest operations")
    parser.add_argument("--operation", help="Filter by operation name")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = get_performance_stats(args.operation)
        print(json.dumps(stats, indent=2))
    elif args.cache:
        cache = check_cache_efficiency()
        print(json.dumps(cache, indent=2))
    elif args.bottlenecks:
        bottlenecks = analyze_bottlenecks()
        for b in bottlenecks:
            print(f"{b['operation']}: {b['duration_seconds']}s at {b['timestamp']}")
    else:
        parser.print_help()
