// Web Worker for VideoReverse — offloads heavy formatting/processing

self.onmessage = function (e) {
  const { type, data } = e.data;

  switch (type) {
    case "formatJson":
      self.postMessage({ type: "formattedJson", data: JSON.stringify(data, null, 2) });
      break;

    case "diffBlueprint":
      self.postMessage({ type: "diffResult", data: computeBlueprintDiff(data.left, data.right) });
      break;

    case "collectPrompts":
      self.postMessage({ type: "collectedPrompts", data: collectAllPrompts(data) });
      break;

    default:
      self.postMessage({ type: "error", data: "Unknown task" });
  }
};

function computeBlueprintDiff(left, right) {
  const diff = {};
  const leftAesthetic = left?.global_aesthetic || {};
  const rightAesthetic = right?.global_aesthetic || {};

  diff.aesthetic = {};
  for (const key of ["art_style", "color_grading", "lighting_setup"]) {
    if (leftAesthetic[key] !== rightAesthetic[key]) {
      diff.aesthetic[key] = { left: leftAesthetic[key], right: rightAesthetic[key] };
    }
  }

  const leftShots = left?.chronological_shots || [];
  const rightShots = right?.chronological_shots || [];
  diff.shotCountDiff = leftShots.length - rightShots.length;

  diff.shots = [];
  const maxShots = Math.max(leftShots.length, rightShots.length);
  for (let i = 0; i < maxShots; i++) {
    const ls = leftShots[i] || {};
    const rs = rightShots[i] || {};
    const shotDiff = {};
    for (const key of ["camera_direction", "framing_type", "action_and_motion", "environment_context", "duration_seconds"]) {
      if (ls[key] !== rs[key]) {
        shotDiff[key] = { left: ls[key], right: rs[key] };
      }
    }
    if (Object.keys(shotDiff).length > 0) {
      diff.shots.push({ index: i, changes: shotDiff });
    }
  }

  return diff;
}

function collectAllPrompts(prompts) {
  const result = {};
  for (const [modelId, model] of Object.entries(prompts || {})) {
    result[modelId] = {
      label: model.label,
      prompts: (model.shots || []).map((s) => s.prompt).filter(Boolean),
    };
  }
  return result;
}
