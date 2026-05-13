'use strict';

/**
 * Reads build-profile.json5 and prints each module's srcPath in declaration order.
 * SSOT for install order: build-profile.json5 "modules" array only (no duplicated lists in PowerShell).
 * Does not use the json5 npm package (OpenHarmony ohpm registry may not ship it).
 * Handles // and /* *\/ comments, strings, and nested arrays inside "modules".
 */

const fs = require('fs');
const path = require('path');

function findModulesArrayText(fullText) {
  const key = '"modules"';
  const kpos = fullText.indexOf(key);
  if (kpos === -1) {
    throw new Error('build-profile.json5: no "modules" key');
  }
  let i = fullText.indexOf('[', kpos + key.length);
  if (i === -1) {
    throw new Error('build-profile.json5: no "[" after "modules"');
  }

  const start = i;
  let depth = 1;
  i += 1;
  let inString = false;
  let escape = false;
  let inLineComment = false;
  let inBlockComment = false;

  for (; i < fullText.length && depth > 0; i++) {
    const c = fullText[i];
    const c2 = fullText[i + 1];

    if (inLineComment) {
      if (c === '\n' || c === '\r') {
        inLineComment = false;
      }
      continue;
    }
    if (inBlockComment) {
      if (c === '*' && c2 === '/') {
        inBlockComment = false;
        i++;
      }
      continue;
    }

    if (escape) {
      escape = false;
      continue;
    }
    if (inString) {
      if (c === '\\') {
        escape = true;
      } else if (c === '"') {
        inString = false;
      }
      continue;
    }

    if (c === '/' && c2 === '/') {
      inLineComment = true;
      i++;
      continue;
    }
    if (c === '/' && c2 === '*') {
      inBlockComment = true;
      i++;
      continue;
    }

    if (c === '"') {
      inString = true;
      continue;
    }
    if (c === '[') {
      depth++;
    } else if (c === ']') {
      depth--;
    }
  }

  if (depth !== 0) {
    throw new Error('build-profile.json5: unclosed "modules" array');
  }

  return fullText.slice(start, i);
}

function extractSrcPaths(modulesSlice) {
  const re = /"srcPath"\s*:\s*"([^"]+)"/g;
  const out = [];
  let m;
  while ((m = re.exec(modulesSlice)) !== null) {
    out.push(m[1]);
  }
  if (out.length === 0) {
    throw new Error('build-profile.json5: no "srcPath" entries inside "modules"');
  }
  return out;
}

const profilePath = process.argv[2] || path.join(__dirname, '..', 'build-profile.json5');
const text = fs.readFileSync(profilePath, 'utf8');
const modulesSlice = findModulesArrayText(text);
const paths = extractSrcPaths(modulesSlice);
for (const p of paths) {
  console.log(p);
}
