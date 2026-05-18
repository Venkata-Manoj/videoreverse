import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import { getRoot } from './path-resolver.js';

const execAsync = promisify(exec);

const TEST_VIDEOS = [
    {
        name: 'test1.mp4',
        description: 'CGI/Animation',
        expectedType: 'cgi',
        required: true,
    },
    {
        name: 'test_drone.mp4',
        description: 'Aerial/Drone Footage',
        expectedType: 'drone',
        required: false,
    },
    {
        name: 'test_anime.mp4',
        description: '2D Animation/Anime',
        expectedType: 'animation',
        required: false,
    },
    {
        name: 'test_vlog.mp4',
        description: 'Handheld Multi-cut Vlog',
        expectedType: 'live-action',
        required: false,
    },
];

const PROJECT_ROOT = getRoot();
const RESULTS_DIR = path.join(PROJECT_ROOT, 'test_results');
const SUMMARY_FILE = path.join(RESULTS_DIR, 'test_summary.json');

function ensureResultsDir() {
    if (!fs.existsSync(RESULTS_DIR)) {
        fs.mkdirSync(RESULTS_DIR, { recursive: true });
    }
}

async function runPipeline(videoPath, options = {}) {
    const timestamp = Date.now();
    const args = [
        'node',
        'src/pipeline.js',
        videoPath,
        '--output-dir', RESULTS_DIR,
    ];

    if (options.dryRun) args.push('--dry-run');
    if (options.model) args.push('--model', options.model);
    if (options.verbose) args.push('--verbose');

    const cmd = args.join(' ');
    console.log(`\n  Running: ${cmd}\n`);

    try {
        const { stdout, stderr } = await execAsync(cmd, {
            cwd: PROJECT_ROOT,
            maxBuffer: 50 * 1024 * 1024,
            timeout: 300000,
        });

        return {
            success: true,
            stdout,
            stderr,
            timestamp,
        };
    } catch (error) {
        return {
            success: false,
            stdout: error.stdout || '',
            stderr: error.stderr || '',
            error: error.message,
            timestamp,
        };
    }
}

function validateOutput(filename) {
    try {
        const content = fs.readFileSync(filename, 'utf-8');
        const data = JSON.parse(content);

        const checks = {
            has_video_metadata: !!data.video_metadata,
            has_blueprint: !!data.blueprint,
            has_prompts: !!data.prompts,
            has_global_aesthetic: !!data.blueprint?.global_aesthetic,
            has_chronological_shots: Array.isArray(data.blueprint?.chronological_shots),
            has_model_outputs: Object.keys(data.prompts || {}).length > 0,
        };

        const passed = Object.values(checks).every(v => v === true);
        const score = (Object.values(checks).filter(v => v).length / Object.keys(checks).length) * 100;

        return { passed, score, checks, data };
    } catch (error) {
        return {
            passed: false,
            score: 0,
            error: error.message,
            checks: {},
        };
    }
}

async function runTests() {
    console.log('═══════════════════════════════════════════');
    console.log('  VideoReverse — Test Suite');
    console.log('═══════════════════════════════════════════\n');

    ensureResultsDir();

    const results = {
        timestamp: new Date().toISOString(),
        total: TEST_VIDEOS.length,
        passed: 0,
        failed: 0,
        tests: [],
    };

    for (const test of TEST_VIDEOS) {
        const videoPath = path.join(PROJECT_ROOT, test.name);
        const exists = fs.existsSync(videoPath);

        console.log(`\n┌─ Test: ${test.name}`);
        console.log(`│  Description: ${test.description}`);
        console.log(`│  Expected Type: ${test.expectedType}`);
        console.log(`│  Required: ${test.required ? 'YES' : 'NO'}`);

        if (!exists) {
            console.log(`│`);
            console.log(`└─ ⏭️  SKIPPED (file not found)`);
            results.tests.push({
                name: test.name,
                status: 'skipped',
                reason: 'file not found',
                required: test.required,
            });
            if (test.required) {
                results.failed++;
            }
            continue;
        }

        const startTime = Date.now();
        const result = await runPipeline(videoPath, { verbose: false });
        const duration = Date.now() - startTime;

        if (result.success) {
            const outputFiles = fs.readdirSync(RESULTS_DIR)
                .filter(f => f.startsWith(test.name.replace('.mp4', '')))
                .map(f => path.join(RESULTS_DIR, f));

            const jsonFile = outputFiles.find(f => f.endsWith('.json'));
            const txtFile = outputFiles.find(f => f.endsWith('.txt'));

            let validation = null;
            if (jsonFile) {
                validation = validateOutput(jsonFile);
            }

            if (validation?.passed) {
                console.log(`│`);
                console.log(`└─ ✅ PASSED (${(duration / 1000).toFixed(1)}s, score: ${validation.score}%)`);
                results.passed++;
                results.tests.push({
                    name: test.name,
                    status: 'passed',
                    duration_ms: duration,
                    validation,
                    output_files: { json: jsonFile, txt: txtFile },
                });
            } else {
                console.log(`│`);
                console.log(`└─ ❌ FAILED (validation score: ${validation?.score || 0}%)`);
                results.failed++;
                results.tests.push({
                    name: test.name,
                    status: 'failed',
                    reason: validation?.error || 'validation failed',
                    duration_ms: duration,
                    validation,
                });
            }
        } else {
            console.log(`│`);
            console.log(`└─ ❌ FAILED (error: ${result.error})`);
            results.failed++;
            results.tests.push({
                name: test.name,
                status: 'failed',
                error: result.error,
                duration_ms: duration,
            });
        }
    }

    console.log('\n═══════════════════════════════════════════');
    console.log('  Test Summary');
    console.log('═══════════════════════════════════════════');
    console.log(`  Total:  ${results.total}`);
    console.log(`  Passed: ${results.passed} ✅`);
    console.log(`  Failed: ${results.failed} ❌`);
    console.log(`  Skipped: ${results.tests.filter(t => t.status === 'skipped').length}`);
    console.log('═══════════════════════════════════════════\n');

    fs.writeFileSync(SUMMARY_FILE, JSON.stringify(results, null, 2));
    console.log(`  Full report: ${SUMMARY_FILE}`);

    return results;
}

if (process.argv[1]?.includes('run_tests')) {
    runTests()
        .then((results) => {
            const exitCode = results.failed > 0 ? 1 : 0;
            process.exit(exitCode);
        })
        .catch((err) => {
            console.error('Test suite error:', err);
            process.exit(1);
        });
}

export { runTests, TEST_VIDEOS };