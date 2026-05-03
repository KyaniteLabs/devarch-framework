#!/usr/bin/env node
/**
 * Archaeology HTML Validator
 *
 * Validates an archaeology.html file for common defects before committing.
 * Accepts optional --project-dir to load project-specific config.
 *
 * Usage: node validate_html.cjs <html-file-path> [--project-dir <path>]
 *
 * Exit codes:
 *   0 = All validations passed
 *   1 = One or more validations failed
 */

const fs = require('fs');
const path = require('path');

// Parse CLI arguments
const args = process.argv.slice(2);
if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
  console.log('Usage: node validate_html.cjs <html-file-path> [--project-dir <path>]');
  console.log('');
  console.log('Validates an archaeology HTML visualization for common defects.');
  console.log('Checks: [object Object] bugs, era colors, JSON data validity,');
  console.log('CSS variables, chart containers, placeholder text.');
  process.exit(args.includes('--help') || args.includes('-h') ? 0 : 1);
}

const htmlPath = path.resolve(args[0]);
const errors = [];
const warnings = [];

console.log(`Validating: ${htmlPath}\n`);

// Check file exists
if (!fs.existsSync(htmlPath)) {
  console.error(`File not found: ${htmlPath}`);
  process.exit(1);
}

const file = fs.readFileSync(htmlPath, 'utf8');

// Load project config if available
let projectConfig = {};
const projectDirIdx = args.indexOf('--project-dir');
if (projectDirIdx !== -1 && args[projectDirIdx + 1]) {
  const configPath = path.join(args[projectDirIdx + 1], 'project.json');
  if (fs.existsSync(configPath)) {
    try {
      projectConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch (e) {
      warnings.push(`Could not parse project.json: ${e.message}`);
    }
  }
}

const eraCount = projectConfig.overrides?.era_count || 0;
const agentNames = Object.keys(projectConfig.visualization?.agent_colors || {});

// ============================================================================
// CHECK 1: No [object Object] serialization bugs
// ============================================================================
if (file.includes('[object Object]')) {
  errors.push('Found "[object Object]" - data serialization bug');
} else {
  console.log('PASS: No [object Object] bugs found');
}

// ============================================================================
// CHECK 2: Era color variables defined
// ============================================================================
if (eraCount > 0) {
  let missingEraColors = [];
  for (let i = 1; i <= eraCount; i++) {
    if (!file.includes(`--era${i}:`)) {
      missingEraColors.push(i);
    }
  }

  if (missingEraColors.length > 0) {
    errors.push(`Missing era color variables: ${missingEraColors.map(i => `--era${i}`).join(', ')}`);
  } else {
    console.log(`PASS: All ${eraCount} era colors defined`);
  }
} else {
  // Count how many era colors exist and just verify there are some
  const eraColorMatches = file.match(/--era\d+:/g);
  if (eraColorMatches && eraColorMatches.length > 0) {
    console.log(`PASS: ${eraColorMatches.length} era colors found`);
  } else {
    warnings.push('No era color CSS variables found');
  }
}

// ============================================================================
// CHECK 3: JSON data validity
// ============================================================================
const jsonMatch = file.match(/window\.(\w+_DATA)\s*=\s*(\{[\s\S]*?\});\s*\n?\s*fetch/) ||
                  file.match(/window\.(\w+_DATA)\s*=\s*(\{[\s\S]*?\});/);
if (jsonMatch) {
  const varName = jsonMatch[1];
  try {
    // Try to find the end of the JSON object properly
    const dataStr = jsonMatch[2];
    // Basic structural checks without full parse (data may reference variables)
    const hasEras = dataStr.includes('"eras"') || dataStr.includes("'eras'");
    const hasCommits = dataStr.includes('commits') || dataStr.includes('commit');

    const hasFetch = file.includes('fetch("data.json")') || file.includes("fetch('data.json')");
    const hasEmbeddedDataScript = file.includes('data.js') || file.includes('__EMBEDDED_DATA');

    if (hasEras || hasCommits) {
      console.log(`PASS: Data object (${varName}) has expected structure`);
    } else if (dataStr.trim() === '{}' && (hasFetch || hasEmbeddedDataScript)) {
      console.log(`PASS: ${varName} fallback object paired with external data load`);
    } else {
      warnings.push(`Data object (${varName}) may be missing expected fields`);
    }
  } catch (e) {
    errors.push(`Invalid data object: ${e.message}`);
  }
} else {
  // Check if data is loaded via fetch (modern template pattern)
  const hasFetch = file.includes('fetch("data.json")') || file.includes("fetch('data.json')");
  const hasEmbeddedDataScript = file.includes('data.js') || file.includes('__EMBEDDED_DATA');
  if (hasFetch && hasEmbeddedDataScript) {
    console.log('PASS: Data loaded via data.js with fetch fallback');
  } else if (hasFetch) {
    console.log('PASS: Data loaded via fetch (external JSON)');
  } else if (hasEmbeddedDataScript) {
    console.log('PASS: Data loaded via data.js embedded-data script');
  } else {
    warnings.push('Could not find data object or fetch pattern');
  }
}

// ============================================================================
// CHECK 4: CSS variables present
// ============================================================================
const requiredVars = ['--bg', '--surface', '--text', '--text2'];
const missingVars = requiredVars.filter(v => !file.includes(`${v}:`));

if (missingVars.length > 0) {
  errors.push(`Missing CSS variables: ${missingVars.join(', ')}`);
} else {
  console.log('PASS: Core CSS variables present');
}

// Check agent color variables if configured
if (agentNames.length > 0) {
  const agentVars = agentNames.map(name => `--${name.toLowerCase()}`);
  const missingAgentVars = agentVars.filter(v => !file.includes(`${v}:`));
  if (missingAgentVars.length > 0) {
    warnings.push(`Missing agent CSS variables: ${missingAgentVars.join(', ')}`);
  } else {
    console.log('PASS: All agent CSS variables present');
  }
}

// ============================================================================
// CHECK 5: Chart container IDs present
// ============================================================================
const requiredCharts = [
  'chart-commit-timeline',
  'chart-era-map',
  'chart-heatmap',
];

const missingCharts = requiredCharts.filter(id => !file.includes(`id="${id}"`));

if (missingCharts.length > 0) {
  errors.push(`Missing core chart containers: ${missingCharts.join(', ')}`);
} else {
  console.log('PASS: Core chart containers present');
}

// ============================================================================
// CHECK 6: No placeholder text
// ============================================================================
const placeholders = ['TODO', 'FIXME', 'XXX', 'HACK'];
const foundPlaceholders = placeholders.filter(p =>
  file.includes(p)
);

if (foundPlaceholders.length > 0) {
  warnings.push(`Found placeholder markers: ${foundPlaceholders.join(', ')}`);
}

// ============================================================================
// REPORT
// ============================================================================
console.log('\n' + '='.repeat(60));

if (errors.length === 0 && warnings.length === 0) {
  console.log('ALL VALIDATIONS PASSED');
  console.log('='.repeat(60));
  process.exit(0);
} else {
  if (errors.length > 0) {
    console.log(`${errors.length} ERROR(S) FOUND:`);
    errors.forEach(e => console.log(`   - ${e}`));
  }

  if (warnings.length > 0) {
    console.log(`\n${warnings.length} WARNING(S):`);
    warnings.forEach(w => console.log(`   - ${w}`));
  }

  console.log('='.repeat(60));
  process.exit(errors.length > 0 ? 1 : 0);
}
