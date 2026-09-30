"""Independent checkpoint for strict variants and Live warning overlays."""
from pathlib import Path
import checkpoint_live_latency as checkpoint

checkpoint.CHECKPOINT = checkpoint.ROOT / 'scratch/restore_points/before_live_validation_20260915'
checkpoint.FILES = ('api/views.py', 'grading/live_latency.py', 'grading/engine/hi.py',
                    'grading/engine/live_bubble_reader.py', 'grading/grader.py',
                    'tests/test_live_latency.py')

if __name__ == '__main__':
    checkpoint.main()
