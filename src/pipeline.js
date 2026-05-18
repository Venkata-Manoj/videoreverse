import { ingestVideo } from './ingest.js';
import { buildBlueprint } from './synthesize.js';
import { compilePrompts } from './compile.js';
import { formatText } from './export.js';
import * as fs from 'fs';
import * as path from 'path';
import { parseCLIArgs, printHelp, detectEnvironment } from '../utils/cli.js';
import { setLogLevel, info, error, warn, debug, logPipelineStep } from '../utils/logger.js';
import { withRetry, RETRY_CONFIG, RetriableError } from '../utils/retry.js';
import { validateBlueprint, sanitizeBlueprint } from '../utils/validation.js';
import { FallbackMode, buildFallbackBlueprint, compileFallbackPrompts, logFallbackUsage } from '../utils/fallback.js';
import { detectVideoType, getVideoTypeLabel } from '../utils/video-type.js';

const __dirname = path.dirname(new URL(import.meta.url).pathname);

function normalizePath(target, wslMode = null) {
    if (typeof target !== 'string') return target;
    if (target.includes('://')) return target;

    const isUNC = target.startsWith('\\\\');
    if (isUNC) {
        const uncPath = target.replace(/\\\\/g, '/').replace(/\\/g, '/');
        const parts = uncPath.split('/').filter(Boolean);
        if (parts.length >= 2) {
            return `/mnt/${parts[0].toLowerCase()}/${parts.slice(1).join('/')}`;
        }
    }

    const env = wslMode || detectEnvironment();
    if (env === 'win') return path.resolve(target);

    const isWindowsPath = /^[a-zA-Z]:[\\/]/.test(target);
    if (isWindowsPath) {
        const drive = target[0].toLowerCase();
        const posixPath = target.slice(2).replace(/\\/g, '/').replace(/^\/+/, '');
        return `/mnt/${drive}/${posixPath}`;
    }

    if (/^\/mnt\/[a-z]\//i.test(target)) return target;
    return path.resolve(target);
}

async function runPipeline(options) {
    const startTime = Date.now();
    const fallback = new FallbackMode();

    const normalized = normalizePath(options.videoPath, options.wslMode);
    const videoType = options.videoType || detectVideoType(null, null);

    console.log('═══════════════════════════════════════════');
    console.log('  VideoReverse — Universal Video-to-Prompt');
    console.log('═══════════════════════════════════════════');
    console.log(`  Environment: ${detectEnvironment()}`);
    console.log(`  Video Type: ${getVideoTypeLabel(videoType) || 'auto-detect'}`);
    console.log('═══════════════════════════════════════════\n');

    const results = {
        input: {
            original: options.videoPath,
            resolved: normalized,
            timestamp: new Date().toISOString(),
            video_type: videoType,
            options,
        },
        steps: {},
        output: null,
        timing: {},
        errors: [],
    };

    try {
        const ingestStart = Date.now();
        console.log('\n── Ingestion & Sampling ──\n');

        try {
            const step1Data = await withRetry(
                () => ingestVideo(normalized),
                { maxRetries: options.maxRetries || RETRY_CONFIG.maxRetries }
            );
            results.steps.ingest = step1Data;
            results.timing.ingest_ms = Date.now() - ingestStart;

            const detectedType = detectVideoType(
                step1Data.video_metadata,
                step1Data.extraction
            );
            info('video-type', `Detected: ${detectedType}`);

            if (options.videoType && options.videoType !== detectedType) {
                warn('video-type', `Override: ${options.videoType} (detected: ${detectedType})`);
            }
        } catch (err) {
            const errMsg = `Ingestion failed: ${err.message}`;
            results.errors.push({ step: 'ingest', error: errMsg });
            error('ingest', errMsg);
            throw err;
        }

        logPipelineStep('ingest', results.timing.ingest_ms, true);

        let blueprint;
        const synthStart = Date.now();
        console.log('\n── Blueprint Synthesis ──\n');

        try {
            blueprint = await withRetry(
                () => buildBlueprint(normalized, results.steps.ingest),
                { maxRetries: options.maxRetries || RETRY_CONFIG.maxRetries }
            );

            try {
                validateBlueprint(blueprint);
                debug('validation', 'Blueprint validation passed');
            } catch (validationErr) {
                warn('validation', `Invalid blueprint: ${validationErr.message}`);
                info('validation', 'Attempting to sanitize...');
                blueprint = sanitizeBlueprint(blueprint);
            }

            results.steps.synthesize = blueprint;
            results.timing.synthesize_ms = Date.now() - synthStart;
        } catch (err) {
            results.timing.synthesize_ms = Date.now() - synthStart;

            const isRetriable = err instanceof RetriableError ? err.isRetriable : 
                err.message.toLowerCase().includes('rate limit') ||
                err.message.toLowerCase().includes('quota');

            if (isRetriable || options.force) {
                fallback.activate(`Gemini synthesis failed: ${err.message}`);
                logFallbackUsage(fallback, 'synthesis', err);

                blueprint = buildFallbackBlueprint(results.steps.ingest);
                results.steps.synthesize = blueprint;
                results.steps.synthesize._fallback = true;
            } else {
                throw err;
            }
        }

        logPipelineStep('synthesis', results.timing.synthesize_ms, !fallback.isActive());

        let prompts;
        const compileStart = Date.now();
        console.log('\n── Prompt Compilation ──\n');

        try {
            prompts = compilePrompts(blueprint, results.steps.ingest.video_metadata, options.models || null);

            results.steps.compile = prompts;
            results.timing.compile_ms = Date.now() - compileStart;
        } catch (err) {
            results.timing.compile_ms = Date.now() - compileStart;
            error('compile', `Prompt compilation failed: ${err.message}`);

            if (fallback.isActive()) {
                prompts = compileFallbackPrompts(blueprint, results.steps.ingest);
                results.steps.compile = prompts;
            } else {
                throw err;
            }
        }

        logPipelineStep('compile', results.timing.compile_ms, true);

        results.output = {
            video_metadata: results.steps.ingest.video_metadata,
            blueprint,
            prompts,
            _meta: {
                video_type: videoType,
                fallback_active: fallback.isActive(),
                fallback_reason: fallback.getReason(),
            },
        };

        results.timing.total_ms = Date.now() - startTime;

        if (options.dryRun) {
            console.log('\n═══════════════════════════════════════════');
            console.log('  DRY RUN — No files saved');
            console.log('═══════════════════════════════════════════');
            console.log(JSON.stringify(results.output, null, 2));
            return results.output;
        }

        const outputDir = path.resolve(options.outputDir);
        if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

        const filename = results.steps.ingest.video_metadata.filename.replace(/\.[^.]+$/, '');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const jsonFile = path.join(outputDir, `${filename}_${timestamp}.json`);

        fs.writeFileSync(jsonFile, JSON.stringify(results.output, null, 2));
        console.log(`\n💾 JSON: ${jsonFile}`);

        if (options.format === 'txt' || options.format === 'both') {
            const textFile = path.join(outputDir, `${filename}_${timestamp}.txt`);
            fs.writeFileSync(textFile, formatText(results.output));
            console.log(`📄 Text: ${textFile}`);
        }

        console.log('\n═══════════════════════════════════════════');
        console.log('  Pipeline Complete');
        console.log('═══════════════════════════════════════════');
        console.log(`  Duration:  ${(results.timing.total_ms / 1000).toFixed(1)}s`);
        console.log(`  Shots:     ${blueprint.chronological_shots.length}`);
        console.log(`  Models:    ${Object.keys(prompts).length}`);
        console.log(`  Fallback:  ${fallback.isActive() ? 'YES ⚠️' : 'NO'}`);

        if (fallback.isActive()) {
            console.log(`  Reason:    ${fallback.getReason()}`);
        }

        console.log('═══════════════════════════════════════════\n');

        return results.output;

    } catch (err) {
        results.timing.total_ms = Date.now() - startTime;
        results.error = err.message;
        results.errors.push({ step: 'pipeline', error: err.message });

        error('pipeline', `Pipeline failed after ${(results.timing.total_ms / 1000).toFixed(1)}s`);
        error('pipeline', `Error: ${err.message}`);

        if (err.message.includes('peepshow')) {
            console.error('\n   Fix: npm i -g peepshow  (requires Node 22+)');
        } else if (err.message.includes('GEMINI_API_KEY')) {
            console.error('\n   Fix: Add GEMINI_API_KEY to .env file');
        } else if (err.message.includes('not found')) {
            console.error('\n   Fix: Check the video path is correct and accessible');
        }

        throw err;
    }
}

const args = process.argv.slice(2);

if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    process.exit(0);
}

if (args.length === 0 || !args[0] || args[0].startsWith('-')) {
    console.error('Usage: node pipeline.js <video_path_or_url> [options]');
    console.error('       node pipeline.js --help  for all options');
    process.exit(1);
}

const options = parseCLIArgs(args);

if (options.verbose) setLogLevel('debug');
if (options.quiet) setLogLevel('quiet');
if (options.logLevel) setLogLevel(options.logLevel);

runPipeline(options)
    .then((output) => {
        if (options.logLevel !== 'quiet') {
            console.log(JSON.stringify(output, null, 2));
        }
        process.exit(0);
    })
    .catch((err) => {
        process.exit(1);
    });

export { runPipeline, normalizePath };