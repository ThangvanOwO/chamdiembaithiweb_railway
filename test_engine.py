"""Quick test script for the grading engine."""
import sys
sys.path.insert(0, 'grading/engine')
import hi as engine

IMAGE_PATH = r'anh\f15599be46dfc7819ece.jpg'

print("Running engine on:", IMAGE_PATH)
result = engine.process_sheet(IMAGE_PATH, debug=True)

if result:
    print("\n" + "="*50)
    print("RESULTS:")
    print("="*50)
    print(f"  Detection method : {result.get('detect_method', '?')}")
    print(f"  Offsets          : {result.get('offsets', {})}")
    print(f"  SBD              : {result.get('sbd')}")
    print(f"  Ma de            : {result.get('made')}")
    print(f"  Score            : {result.get('score')}/{result.get('max_score')}")
    print(f"\n  Part 1 answers:")
    p1 = result.get('part1', {})
    for q in range(1, 41):
        a = p1.get(q, '-')
        end = '  ' if q % 10 != 0 else '\n'
        print(f"    Q{q:2d}={a}", end=end)
    print(f"\n  Part 2 answers:")
    p2 = result.get('part2', {})
    for q in range(1, 9):
        qa = p2.get(q, {})
        parts = [f"{r}={qa.get(r, '-')}" for r in ['a','b','c','d']]
        print(f"    Q{q}: {', '.join(parts)}")
    print(f"\n  Part 3 answers:")
    p3 = result.get('part3', {})
    for q in range(1, 7):
        print(f"    Q{q}: {p3.get(q, '-')}")
else:
    print("FAILED - engine returned None")
