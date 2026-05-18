#!/usr/bin/env node
import * as fs from 'fs';
import { getRoot } from '../src/path-resolver.js';
import { validateBlueprint } from '../utils/validation.js';

const PROJECT_ROOT = getRoot();

function validateFile(filepath) {
    try {
        const content = fs.readFileSync(filepath, 'utf-8');
        const data = JSON.parse(content);

        if (data.blueprint) {
            validateBlueprint(data.blueprint);
            return { valid: true, message: 'Blueprint valid' };
        }

        return { valid: true, message: 'No blueprint to validate' };
    } catch (err) {
        return { valid: false, message: err.message };
    }
}

console.log('═══════════════════════════════════════════');
console.log('  VideoReverse — Validator');
console.log('═══════════════════════════════════════════\n');

const outputDir = fs.readdirSync(path.join(PROJECT_ROOT, 'output_blueprints'));
const jsonFiles = outputDir.filter(f => f.endsWith('.json'));

let allValid = true;

for (const file of jsonFiles) {
    const filepath = path.join(PROJECT_ROOT, 'output_blueprints', file);
    const result = validateFile(filepath);

    const icon = result.valid ? '✅' : '❌';
    console.log(`${icon} ${file}: ${result.message}`);

    if (!result.valid) allValid = false;
}

console.log('\n═══════════════════════════════════════════');
console.log(`  ${allValid ? '✅ All outputs valid' : '❌ Some outputs invalid'}`);
console.log('═══════════════════════════════════════════\n');

process.exit(allValid ? 0 : 1);

import * as path from 'path';