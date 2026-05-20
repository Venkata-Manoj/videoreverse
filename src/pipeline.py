import os
import re
import time
import json
from datetime import datetime, timezone

from src.ingest import ingest_video
from src.synthesize import build_blueprint
from src.compile import compile_prompts
from src.export import format_text
from src.path_resolver import normalize_for_env
from utils.logger import set_log_level, info, error, warn, debug, log_pipeline_step
from utils.retry import with_retry, RETRY_CONFIG, RetriableError
from utils.validation import validate_blueprint, sanitize_blueprint
from utils.fallback import FallbackMode, build_fallback_blueprint, compile_fallback_prompts, log_fallback_usage
from utils.video_type import detect_video_type, get_video_type_label
from utils.cli import detect_environment


def _normalize_path(target, wsl_mode=None):
    if not isinstance(target, str):
        return target
    if '://' in target:
        return target

    is_unc = target.startswith('\\\\')
    if is_unc:
        unc_path = target.replace('\\\\', '/').replace('\\', '/')
        parts = [p for p in unc_path.split('/') if p]
        if len(parts) >= 2:
            return f'/mnt/{parts[0].lower()}/{"/".join(parts[1:])}'

    env = wsl_mode or detect_environment()
    if env == 'win':
        return os.path.abspath(target)

    is_windows_path = bool(re.match(r'^[a-zA-Z]:[\\/]', target))
    if is_windows_path:
        drive = target[0].lower()
        posix_path = target[2:].replace('\\', '/').lstrip('/')
        return f'/mnt/{drive}/{posix_path}'

    if re.match(r'^/mnt/[a-z]/', target, re.IGNORECASE):
        return target
    return os.path.abspath(target)


async def run_pipeline(options):
    start_time = time.time() * 1000
    fallback = FallbackMode()

    normalized = _normalize_path(options.get('video_path'), options.get('wsl_mode'))
    video_type = options.get('video_type') or detect_video_type(None, None)

    print('═' * 60, flush=True)
    print('  VideoReverse — Universal Video-to-Prompt', flush=True)
    print('═' * 60, flush=True)
    print(f'  Environment: {detect_environment()}', flush=True)
    print(f'  Video Type: {get_video_type_label(video_type) or "auto-detect"}', flush=True)
    print('═' * 60 + '\n', flush=True)

    results = {
        'input': {
            'original': options.get('video_path'),
            'resolved': normalized,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'video_type': video_type,
            'options': options,
        },
        'steps': {},
        'output': None,
        'timing': {},
        'errors': [],
    }

    try:
        ingest_start = time.time() * 1000
        print('\n── Ingestion & Sampling ──\n', flush=True)

        try:
            step1_data = await with_retry(
                lambda: ingest_video(normalized),
                {'maxRetries': options.get('max_retries', RETRY_CONFIG['maxRetries'])}
            )
            results['steps']['ingest'] = step1_data
            results['timing']['ingest_ms'] = time.time() * 1000 - ingest_start

            detected_type = detect_video_type(
                step1_data.get('video_metadata'),
                step1_data.get('extraction')
            )
            info('video-type', f'Detected: {detected_type}')

            if options.get('video_type') and options['video_type'] != detected_type:
                warn('video-type', f'Override: {options["video_type"]} (detected: {detected_type})')
        except Exception as err:
            err_msg = f'Ingestion failed: {err}'
            results['errors'].append({'step': 'ingest', 'error': err_msg})
            error('ingest', err_msg)
            raise

        log_pipeline_step('ingest', results['timing']['ingest_ms'], True)

        blueprint = None
        synth_start = time.time() * 1000
        print('\n── Blueprint Synthesis ──\n', flush=True)

        try:
            blueprint = await with_retry(
                lambda: build_blueprint(normalized, results['steps']['ingest']),
                {'maxRetries': options.get('max_retries', RETRY_CONFIG['maxRetries'])}
            )

            try:
                validate_blueprint(blueprint)
                debug('validation', 'Blueprint validation passed')
            except Exception as validation_err:
                warn('validation', f'Invalid blueprint: {validation_err}')
                info('validation', 'Attempting to sanitize...')
                blueprint = sanitize_blueprint(blueprint)

            results['steps']['synthesize'] = blueprint
            results['timing']['synthesize_ms'] = time.time() * 1000 - synth_start
        except Exception as err:
            results['timing']['synthesize_ms'] = time.time() * 1000 - synth_start

            is_retriable = isinstance(err, RetriableError) and getattr(err, 'is_retriable', False)
            if not is_retriable:
                err_msg = str(err).lower()
                is_retriable = 'rate limit' in err_msg or 'quota' in err_msg

            if is_retriable or options.get('force'):
                fallback.activate(f'Gemini synthesis failed: {err}')
                log_fallback_usage(fallback, 'synthesis', err)

                blueprint = build_fallback_blueprint(results['steps']['ingest'])
                results['steps']['synthesize'] = blueprint
                results['steps']['synthesize']['_fallback'] = True
            else:
                raise

        log_pipeline_step('synthesis', results['timing']['synthesize_ms'], not fallback.is_active())

        prompts = None
        compile_start = time.time() * 1000
        print('\n── Prompt Compilation ──\n', flush=True)

        try:
            prompts = compile_prompts(
                blueprint,
                results['steps']['ingest'].get('video_metadata', {}),
                options.get('models')
            )

            results['steps']['compile'] = prompts
            results['timing']['compile_ms'] = time.time() * 1000 - compile_start
        except Exception as err:
            results['timing']['compile_ms'] = time.time() * 1000 - compile_start
            error('compile', f'Prompt compilation failed: {err}')

            if fallback.is_active():
                prompts = compile_fallback_prompts(blueprint, results['steps']['ingest'])
                results['steps']['compile'] = prompts
            else:
                raise

        log_pipeline_step('compile', results['timing']['compile_ms'], True)

        results['output'] = {
            'video_metadata': results['steps']['ingest'].get('video_metadata', {}),
            'blueprint': blueprint,
            'prompts': prompts,
            '_meta': {
                'video_type': video_type,
                'fallback_active': fallback.is_active(),
                'fallback_reason': fallback.get_reason(),
            },
        }

        results['timing']['total_ms'] = time.time() * 1000 - start_time

        if options.get('dry_run'):
            print('\n' + '═' * 60, flush=True)
            print('  DRY RUN — No files saved', flush=True)
            print('═' * 60, flush=True)
            print(json.dumps(results['output'], indent=2), flush=True)
            return results['output']

        output_dir = os.path.abspath(options.get('output_dir', 'output_blueprints'))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        filename = results['steps']['ingest']['video_metadata']['filename']
        filename = os.path.splitext(filename)[0]
        timestamp = datetime.now(timezone.utc).isoformat().replace(':', '-').replace('.', '-')
        json_file = os.path.join(output_dir, f'{filename}_{timestamp}.json')

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results['output'], f, indent=2)
        print(f'\n💾 JSON: {json_file}', flush=True)

        if options.get('format') in ('txt', 'both'):
            text_file = os.path.join(output_dir, f'{filename}_{timestamp}.txt')
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(format_text(results['output']))
            print(f'📄 Text: {text_file}', flush=True)

        print('\n' + '═' * 60, flush=True)
        print('  Pipeline Complete', flush=True)
        print('═' * 60, flush=True)
        print(f'  Duration:  {(results["timing"]["total_ms"] / 1000):.1f}s', flush=True)
        print(f'  Shots:     {len(blueprint.get("chronological_shots", []))}', flush=True)
        print(f'  Models:    {len(prompts)}', flush=True)
        fallback_status = 'YES ⚠️' if fallback.is_active() else 'NO'
        print(f'  Fallback:  {fallback_status}', flush=True)

        if fallback.is_active():
            print(f'  Reason:    {fallback.get_reason()}', flush=True)

        print('═' * 60 + '\n', flush=True)

        return results['output']

    except Exception as err:
        results['timing']['total_ms'] = time.time() * 1000 - start_time
        results['error'] = str(err)
        results['errors'].append({'step': 'pipeline', 'error': str(err)})

        error('pipeline', f'Pipeline failed after {(results["timing"]["total_ms"] / 1000):.1f}s')
        error('pipeline', f'Error: {err}')

        err_str = str(err)
        if 'peepshow' in err_str:
            print('\n   Fix: npm i -g peepshow  (requires Node 22+)', flush=True)
        elif 'GEMINI_API_KEY' in err_str:
            print('\n   Fix: Add GEMINI_API_KEY to .env file', flush=True)
        elif 'not found' in err_str:
            print('\n   Fix: Check the video path is correct and accessible', flush=True)

        raise
