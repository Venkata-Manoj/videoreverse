// Simple test framework for Node.js (no external dependencies)
export function describe(name, fn) {
    console.log(`  ${name}`);
    fn();
}

export function it(name, fn) {
    try {
        fn();
        console.log(`    ✅ ${name}`);
    } catch (err) {
        console.log(`    ❌ ${name}`);
        console.log(`       Error: ${err.message}`);
        throw err;
    }
}

export const expect = {
    toBe(actual, expected) {
        if (actual !== expected) {
            throw new Error(`Expected ${expected}, got ${actual}`);
        }
    },
    toBeGreaterThan(actual, expected) {
        if (actual <= expected) {
            throw new Error(`Expected > ${expected}, got ${actual}`);
        }
    },
    toBeLessThanOrEqual(actual, expected) {
        if (actual > expected) {
            throw new Error(`Expected <= ${expected}, got ${actual}`);
        }
    },
    toBeDefined(actual) {
        if (actual === undefined) {
            throw new Error(`Expected defined, got undefined`);
        }
    },
    toBeUndefined(actual) {
        if (actual !== undefined) {
            throw new Error(`Expected undefined, got ${actual}`);
        }
    },
    toBeTruthy(actual) {
        if (!actual) {
            throw new Error(`Expected truthy, got ${actual}`);
        }
    },
    toBeFalsy(actual) {
        if (actual) {
            throw new Error(`Expected falsy, got ${actual}`);
        }
    },
};