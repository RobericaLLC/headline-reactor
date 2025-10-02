"""End-to-end smoke test for production readiness"""
import time
import subprocess
import sys

HEADLINES = [
    "NVDA US NVIDIA IN TALKS FOR MAJOR ACQUISITION",
    "EA US ELECTRONIC ARTS NEARS DEAL WITH MICROSOFT",
    "AMD US AMD ANNOUNCES NEW AI CHIP BREAKTHROUGH",
    "AAPL US APPLE BEATS QUARTERLY EARNINGS",
    "TSLA US TESLA MISSES DELIVERY TARGETS",
]

SLO_MS = 2000  # 2 second SLO for suggest command

def run_cli(headline: str) -> tuple[str, float]:
    """Run headline-reactor suggest-v2 and measure latency."""
    t1 = time.time()
    try:
        result = subprocess.run(
            ["python", "-c", 
             f"from headline_reactor.cli import app; import sys; sys.argv = ['cli', 'suggest-v2', '{headline}']; app()"],
            capture_output=True,
            text=True,
            timeout=5
        )
        dt_ms = (time.time() - t1) * 1000
        output = result.stdout + result.stderr
        return output, dt_ms
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]", 5000
    except Exception as e:
        return f"[ERROR] {e}", (time.time() - t1) * 1000

def main():
    print("=" * 70)
    print("SMOKE TEST: End-to-End Production Readiness")
    print("=" * 70)
    
    t0 = time.time()
    passed = 0
    failed = 0
    
    for i, h in enumerate(HEADLINES, 1):
        print(f"\n[{i}/{len(HEADLINES)}] {h[:60]}...")
        out, dt_ms = run_cli(h)
        
        # Validate output
        checks = []
        checks.append(("Has suggestions", "IOC TTL=" in out))
        checks.append(("Has action", ("BUY" in out or "SELL" in out or "NO ACTION" in out)))
        checks.append((f"Within SLO ({SLO_MS}ms)", dt_ms < SLO_MS))
        checks.append(("No errors", "[ERROR]" not in out and "[TIMEOUT]" not in out))
        
        all_pass = all(c[1] for c in checks)
        
        if all_pass:
            print(f"  [PASS] {int(dt_ms)}ms")
            for check_name, result in checks:
                status = "✓" if result else "✗"
                print(f"    {status} {check_name}")
            passed += 1
        else:
            print(f"  [FAIL] {int(dt_ms)}ms")
            for check_name, result in checks:
                status = "✓" if result else "✗"
                print(f"    {status} {check_name}")
            print(f"  Output: {out[:200]}")
            failed += 1
    
    total_time = time.time() - t0
    
    print("\n" + "=" * 70)
    print("SMOKE TEST RESULTS")
    print("=" * 70)
    print(f"  Passed: {passed}/{len(HEADLINES)}")
    print(f"  Failed: {failed}/{len(HEADLINES)}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg latency: {(total_time/len(HEADLINES))*1000:.0f}ms")
    print("=" * 70)
    
    if failed > 0:
        print("\n[FAIL] Some tests failed")
        sys.exit(1)
    else:
        print("\n[PASS] All systems operational")
        sys.exit(0)

if __name__ == "__main__":
    main()

