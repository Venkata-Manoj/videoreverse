import { parseCLIArgs, printHelp, detectEnvironment } from '../utils/cli.js';
import { setLogLevel, info, error, warn } from '../utils/logger.js';
import { runPipeline } from './pipeline.js';
import { normalizeForEnv } from './path-resolver.js';

function parseArgs() {
    const args = process.argv.slice(2);
    
    if (args.includes('--help') || args.includes('-h')) {
        printHelp();
        process.exit(0);
    }

    if (args.length === 0 || !args[0] || args[0].startsWith('-')) {
        console.error('Usage: node src/main.js <video_path_or_url> [options]');
        console.error('       node src/main.js --help  for all options');
        console.error('');
        console.error('Examples:');
        console.error('  node src/main.js ./video.mp4');
        console.error('  node src/main.js E:\\vidrev\\video.mp4');
        console.error('  node src/main.js https://example.com/video.mp4');
        process.exit(1);
    }

    return parseCLIArgs(args);
}

async function main() {
    const args = parseArgs();

    if (args.verbose) setLogLevel('debug');
    if (args.quiet) setLogLevel('quiet');
    if (args.logLevel) setLogLevel(args.logLevel);

    info('main', `VideoReverse starting...`);
    info('main', `Environment: ${detectEnvironment()}`);
    info('main', `Video path: ${args.videoPath}`);

    try {
        const output = await runPipeline(args);

        if (args.dryRun) {
            console.log('\n═══════════════════════════════════════════');
            console.log('  DRY RUN — No files saved');
            console.log('═══════════════════════════════════════════\n');
        }

        if (args.logLevel !== 'quiet') {
            console.log(JSON.stringify(output, null, 2));
        }

        process.exit(0);
    } catch (err) {
        error('main', `Fatal error: ${err.message}`);
        process.exit(1);
    }
}

main();