#!/usr/bin/env node
import * as fs from 'fs';
import * as path from 'path';
import { getRoot } from '../src/path-resolver.js';

const PROJECT_ROOT = getRoot();

const lintRules = [
    { pattern: /console\.(log|debug)\(/g, message: 'Remove console.log/debug statements' },
    { pattern: /TODO(?!:)/g, message: 'TODO must be followed by colon' },
    { pattern: /\/\/\s*DEBUG/g, message: 'Remove debug comments' },
];

const EXCLUDED_DIRS = ['node_modules', '.cache', 'output_blueprints', 'test_results'];

function lintFile(filepath) {
    const content = fs.readFileSync(filepath, 'utf-8');
    const issues = [];

    for (const rule of lintRules) {
        const matches = content.matchAll(rule.pattern);
        for (const match of matches) {
            const lineNum = content.substring(0, match.index).split('\n').length;
            issues.push({ file: filepath, line: lineNum, message: rule.message });
        }
    }

    return issues;
}

function findJsFiles(dir) {
    const files = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            if (!EXCLUDED_DIRS.includes(entry.name)) {
                files.push(...findJsFiles(fullPath));
            }
        } else if (entry.name.endsWith('.js')) {
            files.push(fullPath);
        }
    }

    return files;
}

console.log('═══════════════════════════════════════════');
console.log('  VideoReverse — Linter');
console.log('═══════════════════════════════════════════\n');

const jsFiles = findJsFiles(PROJECT_ROOT);
let totalIssues = 0;

for (const file of jsFiles) {
    const relativePath = path.relative(PROJECT_ROOT, file);
    const issues = lintFile(file);

    if (issues.length > 0) {
        console.log(`\n❌ ${relativePath}`);
        for (const issue of issues) {
            console.log(`   Line ${issue.line}: ${issue.message}`);
        }
        totalIssues += issues.length;
    }
}

console.log('\n═══════════════════════════════════════════');
if (totalIssues === 0) {
    console.log('  ✅ No issues found');
} else {
    console.log(`  ❌ ${totalIssues} issue(s) found`);
}
console.log('═══════════════════════════════════════════\n');

process.exit(totalIssues > 0 ? 1 : 0);