import * as fs from 'fs';
import * as path from 'path';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const COMPARE_DIR = path.join(__dirname, '..', 'test_results');

export function comparePrompts(oldData, newData) {
    const results = {
        timestamp: new Date().toISOString(),
        models: {},
    };

    const oldPrompts = oldData?.prompts || {};
    const newPrompts = newData?.prompts || {};

    const allModels = new Set([...Object.keys(oldPrompts), ...Object.keys(newPrompts)]);

    for (const model of allModels) {
        const oldModel = oldPrompts[model];
        const newModel = newPrompts[model];

        if (!oldModel) {
            results.models[model] = { status: 'new', change: 'added' };
            continue;
        }
        if (!newModel) {
            results.models[model] = { status: 'removed', change: 'removed' };
            continue;
        }

        const oldShots = oldModel.shots || [];
        const newShots = newModel.shots || [];

        const promptChanges = [];
        for (let i = 0; i < Math.max(oldShots.length, newShots.length); i++) {
            const oldPrompt = oldShots[i]?.prompt || '';
            const newPrompt = newShots[i]?.prompt || '';

            if (oldPrompt !== newPrompt) {
                const levenshtein = getLevenshteinSimilarity(oldPrompt, newPrompt);
                promptChanges.push({
                    shot_index: i,
                    similarity: Math.round(levenshtein * 100),
                    old_length: oldPrompt.length,
                    new_length: newPrompt.length,
                });
            }
        }

        const avgSimilarity = promptChanges.length > 0
            ? promptChanges.reduce((sum, c) => sum + c.similarity, 0) / promptChanges.length
            : 100;

        results.models[model] = {
            status: avgSimilarity === 100 ? 'unchanged' : 'modified',
            similarity: Math.round(avgSimilarity),
            changes: promptChanges,
            shots_count: newShots.length,
        };
    }

    return results;
}

export function saveComparison(baselinePath, newPath, outputPath = null) {
    try {
        const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'));
        const newData = JSON.parse(fs.readFileSync(newPath, 'utf-8'));

        const comparison = comparePrompts(baseline, newData);

        if (outputPath) {
            fs.writeFileSync(outputPath, JSON.stringify(comparison, null, 2));
        }

        return comparison;
    } catch (err) {
        console.error(`Compare failed: ${err.message}`);
        return null;
    }
}

export function printComparison(compareResult) {
    if (!compareResult) {
        console.log('No comparison data available.');
        return;
    }

    console.log('\n═══════════════════════════════════════════');
    console.log('  Prompt Comparison Report');
    console.log('═══════════════════════════════════════════');
    console.log(`  Generated: ${compareResult.timestamp}\n`);

    for (const [model, result] of Object.entries(compareResult.models)) {
        const statusIcon = result.status === 'unchanged' ? '✓' 
            : result.status === 'new' ? '+' 
            : result.status === 'removed' ? '-' 
            : '~';

        console.log(`  ${statusIcon} ${model}`);
        console.log(`     Status: ${result.status}`);
        console.log(`     Similarity: ${result.similarity || 0}%`);
        if (result.shots_count !== undefined) {
            console.log(`     Shots: ${result.shots_count}`);
        }
        if (result.changes?.length > 0) {
            console.log(`     Changed shots: ${result.changes.length}`);
        }
        console.log();
    }

    console.log('═══════════════════════════════════════════\n');
}

function getLevenshteinSimilarity(str1, str2) {
    const len1 = str1.length;
    const len2 = str2.length;
    
    const matrix = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(null));
    
    for (let i = 0; i <= len1; i++) matrix[i][0] = i;
    for (let j = 0; j <= len2; j++) matrix[0][j] = j;
    
    for (let i = 1; i <= len1; i++) {
        for (let j = 1; j <= len2; j++) {
            const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
            matrix[i][j] = Math.min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost
            );
        }
    }
    
    const maxLen = Math.max(len1, len2);
    if (maxLen === 0) return 1;
    
    return 1 - (matrix[len1][len2] / maxLen);
}

if (process.argv[1]?.includes('compare_prompts')) {
    const args = process.argv.slice(2);
    
    if (args.length < 2) {
        console.log('Usage: node compare_prompts.js <baseline.json> <new.json> [output.json]');
        process.exit(1);
    }
    
    const result = saveComparison(args[0], args[1], args[2]);
    printComparison(result);
}