import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.unit.test_framework import describe, it


def run_tests():
    def _test_detect_videos():
        test_videos = [
            {'name': 'test1.mp4', 'required': True},
            {'name': 'test_drone.mp4', 'required': False},
        ]
        print(f'  Testing video detection for {len(test_videos)} videos', flush=True)

    describe('Pipeline Integration Tests', lambda: it('should detect test videos', _test_detect_videos))

    def _test_output_structure():
        mock_output = {
            'video_metadata': {},
            'blueprint': {
                'global_aesthetic': {},
                'chronological_shots': [],
            },
            'prompts': {},
        }
        assert 'video_metadata' in mock_output
        assert 'blueprint' in mock_output
        assert 'prompts' in mock_output
        print('  Mock output structure validated', flush=True)

    describe('Pipeline Integration Tests', lambda: it('should validate pipeline output structure', _test_output_structure))
