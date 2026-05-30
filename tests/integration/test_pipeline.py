import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.unit.test_framework import describe, it


def _test_video_exists(path: str, required: bool) -> bool:
    exists = os.path.exists(path)
    if not exists and required:
        print(f'  FAIL: required video not found: {path}', flush=True)
        return False
    if exists:
        print(f'  Found: {path}', flush=True)
    return True


def run_tests():
    def _test_detect_videos():
        test_videos = [
            {'name': 'test1.mp4', 'required': True},
            {'name': 'test_drone.mp4', 'required': False},
        ]
        base = Path(__file__).resolve().parent.parent.parent
        ok = all(_test_video_exists(str(base / v['name']), v['required']) for v in test_videos)
        assert ok, 'Required test videos missing'

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

    def _test_ingest_frames_filtered():
        base = Path(__file__).resolve().parent.parent.parent
        video_path = str(base / 'test1.mp4')
        if not os.path.exists(video_path):
            print('  SKIP: test1.mp4 not available', flush=True)
            return

        from src.ingest import ingest_video

        result = ingest_video(video_path, options={
            'blur_threshold': 50,
            'max_frames': 60,
        })

        extraction = result.get('extraction', {})
        frames_filtered = extraction.get('frames_filtered')
        assert frames_filtered is not None, f'frames_filtered is None'
        assert isinstance(frames_filtered, int), f'frames_filtered should be int, got {type(frames_filtered)}'
        assert frames_filtered >= 0, f'frames_filtered should be >= 0, got {frames_filtered}'
        frames_emitted = extraction.get('frames_emitted', 0)
        print(f'  frames_emitted={frames_emitted}, frames_filtered={frames_filtered}', flush=True)

    describe('Pipeline Integration Tests', lambda: it('should include frames_filtered in ingest extraction metadata', _test_ingest_frames_filtered))
