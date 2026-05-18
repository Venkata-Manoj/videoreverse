import * as path from 'path';

export const DEFAULT_OUTPUT_DIR = 'output_blueprints';
export const DEFAULT_FORMAT = 'both';
export const DEFAULT_LOG_LEVEL = 'info';

export const SUPPORTED_MODELS = [
    'runway_gen4_5',
    'google_veo3_1',
    'kling_3_0',
    'sora_2',
    'luma_dream_machine',
    'pika_2',
    'haiper_2',
    'stable_video_diffusion',
];

export const SUPPORTED_FORMATS = ['json', 'txt', 'both', 'none'];

export const SUPPORTED_LOG_LEVELS = ['debug', 'info', 'warn', 'error', 'quiet'];

export function parseCLIArgs(args) {
    const result = {
        videoPath: null,
        models: null,
        outputDir: DEFAULT_OUTPUT_DIR,
        format: DEFAULT_FORMAT,
        logLevel: DEFAULT_LOG_LEVEL,
        dryRun: false,
        verbose: false,
        quiet: false,
        force: false,
        maxRetries: 3,
        maxDuration: null,
        videoType: null,
        noCache: false,
        wslMode: null,
    };

    for (let i = 0; i < args.length; i++) {
        const arg = args[i];

        switch (arg) {
            case '--help':
            case '-h':
                result.showHelp = true;
                break;

            case '--model':
            case '-m':
                const modelsArg = args[++i];
                if (modelsArg) {
                    result.models = modelsArg.split(',').map(m => m.trim()).filter(Boolean);
                }
                break;

            case '--output-dir':
            case '-o':
                const outDir = args[++i];
                if (outDir) result.outputDir = outDir;
                break;

            case '--format':
            case '-f':
                const fmt = args[++i];
                if (fmt && SUPPORTED_FORMATS.includes(fmt)) {
                    result.format = fmt;
                } else {
                    throw new Error(`Invalid format "${fmt}". Use: ${SUPPORTED_FORMATS.join(', ')}`);
                }
                break;

            case '--log-level':
            case '-l':
                const level = args[++i];
                if (level && SUPPORTED_LOG_LEVELS.includes(level)) {
                    result.logLevel = level;
                } else {
                    throw new Error(`Invalid log level "${level}". Use: ${SUPPORTED_LOG_LEVELS.join(', ')}`);
                }
                break;

            case '--verbose':
            case '-v':
                result.verbose = true;
                result.logLevel = 'debug';
                break;

            case '--quiet':
            case '-q':
                result.quiet = true;
                result.logLevel = 'quiet';
                break;

            case '--dry-run':
                result.dryRun = true;
                break;

            case '--force':
            case '-F':
                result.force = true;
                break;

            case '--max-retries':
            case '-r':
                const retries = parseInt(args[++i], 10);
                if (!isNaN(retries) && retries >= 0) {
                    result.maxRetries = retries;
                }
                break;

            case '--max-duration':
                const duration = parseFloat(args[++i]);
                if (!isNaN(duration) && duration > 0) {
                    result.maxDuration = duration;
                }
                break;

            case '--video-type':
                const videoType = args[++i];
                if (videoType) result.videoType = videoType;
                break;

            case '--no-cache':
                result.noCache = true;
                break;

            case '--wsl':
                result.wslMode = 'wsl';
                break;

            case '--win':
                result.wslMode = 'win';
                break;

            default:
                if (!arg.startsWith('-') && !result.videoPath) {
                    result.videoPath = arg;
                }
        }
    }

    if (result.models) {
        const invalid = result.models.filter(m => !SUPPORTED_MODELS.includes(m));
        if (invalid.length > 0) {
            throw new Error(`Unsupported models: ${invalid.join(', ')}. Supported: ${SUPPORTED_MODELS.join(', ')}`);
        }
    }

    return result;
}

export function printHelp() {
    console.log(`
VideoReverse — Universal Video-to-Prompt Pipeline

Usage:
  node pipeline.js <video_path_or_url> [options]

Arguments:
  video_path_or_url    Path to video file or URL

Options:
  --help, -h           Show this help message
  --model, -m          Generate prompts only for specific models (comma-separated)
                       Options: ${SUPPORTED_MODELS.join(', ')}
  --output-dir, -o      Custom output directory (default: ${DEFAULT_OUTPUT_DIR})
  --format             Output format: ${SUPPORTED_FORMATS.join(', ')} (default: both)
  --log-level, -l      Log level: ${SUPPORTED_LOG_LEVELS.join(', ')} (default: info)
  --verbose, -v        Enable verbose logging (alias for --log-level debug)
  --quiet, -q          Suppress console output (alias for --log-level quiet)
  --dry-run            Output prompts without saving files
  --force, -F          Skip failed steps and use cached results
  --max-retries, -r    Max retry attempts for API calls (default: 3)
  --max-duration       Pre-clip video to first N seconds
  --video-type         Override auto-detected video type
  --no-cache           Disable response caching
  --wsl                Force WSL path conversion
  --win                Force Windows path mode

Examples:
  node pipeline.js /mnt/e/vidrev/test1.mp4
  node pipeline.js E:\\vidrev\\test1.mp4 --model runway_gen4_5,google_veo3_1
  node pipeline.js /mnt/e/vidrev/test1.mp4 --format txt --verbose
  node pipeline.js https://example.com/video.mp4 --dry-run
`);
}

export function detectEnvironment() {
    const platform = process.platform;
    const isWSL = fs.existsSync('/proc/version') && 
                  require('fs').readFileSync('/proc/version', 'utf-8').toLowerCase().includes('microsoft');

    if (isWSL) return 'wsl';
    if (platform === 'win32') return 'win';
    return 'unix';
}

import * as fs from 'fs';