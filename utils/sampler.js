import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export const SAMPLE_MODES = ['full', 'first-n', 'highlights'];

export const COST_ESTIMATE = {
  gemini_2_5_flash_per_second: 0.001,
  note: 'Gemini 2.5 Flash ~$0.001/second of video. A 60s video costs ~$0.06.',
};

export function estimateCost(durationSeconds) {
  return {
    duration_seconds: durationSeconds,
    estimated_cost_usd: +(durationSeconds * COST_ESTIMATE.gemini_2_5_flash_per_second).toFixed(4),
    savings_vs_full: null,
  };
}

function getVideoDuration(videoPath) {
  try {
    const output = execSync(
      `ffprobe -v error -show_entries format=duration -of csv="p=0" "${videoPath}"`,
      { encoding: 'utf8' }
    );
    const duration = parseFloat(output.trim());
    if (isNaN(duration) || duration <= 0) {
      throw new Error(`ffprobe returned invalid duration: ${output.trim()}`);
    }
    return duration;
  } catch (err) {
    if (err.message?.includes('ffprobe')) {
      throw new Error('ffprobe not found. Install ffmpeg to use smart sampling.');
    }
    throw err;
  }
}

function clipFirstN(videoPath, durationSeconds) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'vidrev-clip-'));
  const ext = path.extname(videoPath) || '.mp4';
  const clippedPath = path.join(tempDir, `clipped${ext}`);

  console.log(`   ✂️  Clipping first ${durationSeconds}s of video...`);

  execSync(
    `ffmpeg -i "${videoPath}" -t ${durationSeconds} -c copy -avoid_negative_ts make_zero "${clippedPath}" 2>/dev/null`,
    { encoding: 'utf8' }
  );

  if (!fs.existsSync(clippedPath) || fs.statSync(clippedPath).size === 0) {
    execSync(
      `ffmpeg -i "${videoPath}" -t ${durationSeconds} -y "${clippedPath}" 2>/dev/null`,
      { encoding: 'utf8' }
    );
  }

  if (!fs.existsSync(clippedPath)) {
    throw new Error('ffmpeg clipping failed — output file not created');
  }

  const originalSize = fs.statSync(videoPath).size;
  const clippedSize = fs.statSync(clippedPath).size;
  const sizeReduction = ((1 - clippedSize / originalSize) * 100).toFixed(1);

  console.log(`   → Clipped: ${(clippedSize / 1024 / 1024).toFixed(1)} MB (${sizeReduction}% smaller)`);

  return {
    path: clippedPath,
    tempDir,
    mode: 'first-n',
    duration: durationSeconds,
    size_bytes: clippedSize,
  };
}

function extractHighlights(videoPath, targetDuration = 30) {
  const fullDuration = getVideoDuration(videoPath);

  if (fullDuration <= targetDuration) {
    console.log(`   → Video is ${fullDuration.toFixed(1)}s (≤ ${targetDuration}s target) — using full video`);
    return {
      path: videoPath,
      tempDir: null,
      mode: 'full',
      duration: fullDuration,
      size_bytes: fs.statSync(videoPath).size,
    };
  }

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'vidrev-highlights-'));
  const ext = path.extname(videoPath) || '.mp4';
  const highlightsPath = path.join(tempDir, `highlights${ext}`);

  console.log(`   🎬 Extracting ${targetDuration}s highlight reel from ${fullDuration.toFixed(1)}s video...`);
  console.log(`   → Analyzing motion to find best segments...`);

  const segmentDuration = 5;
  const segmentCount = Math.ceil(targetDuration / segmentDuration);
  const totalSegments = Math.ceil(fullDuration / segmentDuration);

  const motionScores = [];
  for (let i = 0; i < totalSegments; i++) {
    const start = i * segmentDuration;
    const actualDuration = Math.min(segmentDuration, fullDuration - start);

    try {
      const output = execSync(
        `ffmpeg -i "${videoPath}" -ss ${start} -t ${actualDuration} ` +
        `-vf "select='gt(scene,0.1)',metadata=print:file=/dev/stdout" ` +
        `-f null - 2>&1 | grep -c "lavfi" || true`,
        { encoding: 'utf8', shell: '/bin/bash' }
      );
      const score = parseInt(output.trim()) || 1;
      motionScores.push({ start, duration: actualDuration, score });
    } catch {
      motionScores.push({ start, duration: actualDuration, score: 1 });
    }
  }

  const topSegments = motionScores
    .sort((a, b) => b.score - a.score)
    .slice(0, segmentCount)
    .sort((a, b) => a.start - b.start);

  const filterComplex = topSegments
    .map((seg, i) => `[0:v]trim=start=${seg.start}:duration=${seg.duration},setpts=PTS-STARTPTS[v${i}]`)
    .join(';');

  const concatInputs = topSegments.map((_, i) => `[v${i}]`).join('');

  execSync(
    `ffmpeg -i "${videoPath}" -filter_complex "${filterComplex};${concatInputs}concat=n=${topSegments.length}:v=1[outv]" ` +
    `-map "[outv]" -c:v libx264 -preset fast -crf 23 -an -y "${highlightsPath}" 2>/dev/null`,
    { encoding: 'utf8' }
  );

  if (!fs.existsSync(highlightsPath) || fs.statSync(highlightsPath).size === 0) {
    console.log(`   → Motion-based extraction failed, falling back to first-${targetDuration}s...`);
    return clipFirstN(videoPath, targetDuration);
  }

  const originalSize = fs.statSync(videoPath).size;
  const highlightsSize = fs.statSync(highlightsPath).size;
  const sizeReduction = ((1 - highlightsSize / originalSize) * 100).toFixed(1);

  console.log(`   → Highlight reel: ${(highlightsSize / 1024 / 1024).toFixed(1)} MB (${sizeReduction}% smaller)`);
  console.log(`   → Top segments: ${topSegments.map(s => `${s.start.toFixed(0)}s`).join(', ')}`);

  return {
    path: highlightsPath,
    tempDir,
    mode: 'highlights',
    duration: targetDuration,
    size_bytes: highlightsSize,
    segments: topSegments,
  };
}

export function sampleVideo(videoPath, options = {}) {
  const {
    sampleMode = 'full',
    maxDuration = null,
  } = options;

  const fullDuration = getVideoDuration(videoPath);
  const originalSize = fs.statSync(videoPath).size;

  console.log(`\n── Smart Frame Sampling ──`);
  console.log(`   Original: ${fullDuration.toFixed(1)}s, ${(originalSize / 1024 / 1024).toFixed(1)} MB`);
  console.log(`   Mode: ${sampleMode}`);

  if (sampleMode === 'full') {
    console.log(`   → Using full video (no sampling)`);
    return {
      path: videoPath,
      tempDir: null,
      mode: 'full',
      duration: fullDuration,
      size_bytes: originalSize,
      original_duration: fullDuration,
    };
  }

  if (sampleMode === 'first-n') {
    const clipDuration = maxDuration || 30;
    if (clipDuration >= fullDuration) {
      console.log(`   → Requested ${clipDuration}s ≥ video duration ${fullDuration.toFixed(1)}s — using full video`);
      return {
        path: videoPath,
        tempDir: null,
        mode: 'full',
        duration: fullDuration,
        size_bytes: originalSize,
        original_duration: fullDuration,
      };
    }
    return clipFirstN(videoPath, clipDuration);
  }

  if (sampleMode === 'highlights') {
    const targetDuration = maxDuration || 30;
    return extractHighlights(videoPath, targetDuration);
  }

  throw new Error(`Unknown sample mode: ${sampleMode}. Use: ${SAMPLE_MODES.join(', ')}`);
}

export function cleanupSample(sampleResult) {
  if (sampleResult?.tempDir && fs.existsSync(sampleResult.tempDir)) {
    try {
      fs.rmSync(sampleResult.tempDir, { recursive: true, force: true });
      console.log(`   → Cleaned up temporary sample files`);
    } catch (e) {
      console.log(`   → Cleanup warning: ${e.message}`);
    }
  }
}
