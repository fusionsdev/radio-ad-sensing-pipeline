#!/usr/bin/env node
/**
 * Generate batch-*.json graph files from extract-structure output.
 * Heuristic summaries for /understand when LLM subagents are unavailable.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, basename, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const PROJECT_ROOT = process.argv[2];
const SKILL_DIR = process.argv[3];
if (!PROJECT_ROOT || !SKILL_DIR) {
  console.error('Usage: node generate-all-batches.mjs <projectRoot> <skillDir>');
  process.exit(1);
}

const batchesPath = join(PROJECT_ROOT, '.understand-anything/intermediate/batches.json');
const batches = JSON.parse(readFileSync(batchesPath, 'utf8'));

function nodeTypeForCategory(cat, path) {
  if (cat === 'config') return 'config';
  if (cat === 'docs') return 'document';
  if (cat === 'infra') {
    if (/\.github\/workflows|\.gitlab-ci|Jenkinsfile/i.test(path)) return 'pipeline';
    if (/\.tf$|terraform/i.test(path)) return 'resource';
    return 'service';
  }
  if (cat === 'data') {
    if (/\.sql$/i.test(path)) return 'table';
    if (/\.(graphql|proto|prisma)$/i.test(path)) return 'schema';
    return 'schema';
  }
  return 'file';
}

function prefixForType(type) {
  const map = {
    file: 'file', config: 'config', document: 'document', service: 'service',
    pipeline: 'pipeline', resource: 'resource', table: 'table', schema: 'schema',
    function: 'function', class: 'class',
  };
  return map[type] || 'file';
}

function tagsFor(path, cat, isTest) {
  const tags = [];
  if (isTest || /test_|_test\.|\.test\.|tests\//i.test(path)) tags.push('test');
  if (cat === 'docs') tags.push('documentation');
  if (cat === 'config') tags.push('configuration');
  if (cat === 'infra') tags.push('infrastructure');
  if (/Dockerfile/i.test(path)) tags.push('containerization');
  if (/docker-compose/i.test(path)) tags.push('orchestration');
  if (path === 'README.md' || path === 'AGENTS.md' || path === 'PLAN.md') tags.push('entry-point', 'overview');
  if (/shared\//.test(path)) tags.push('shared', 'utility');
  if (/ingestor\//.test(path)) tags.push('ingestor', 'service');
  if (/worker\//.test(path)) tags.push('worker', 'service');
  if (/dashboard\//.test(path)) tags.push('dashboard', 'api-handler');
  if (/alerter\//.test(path)) tags.push('alerter', 'service');
  if (/monitoring\//.test(path)) tags.push('monitoring');
  if (path.endsWith('__main__.py')) tags.push('entry-point');
  if (tags.length < 3) tags.push(cat === 'code' ? 'module' : cat);
  return [...new Set(tags)].slice(0, 5);
}

function summaryFor(path, cat, metrics = {}) {
  const name = basename(path);
  if (path === 'README.md') return 'Project overview describing the radio ad-sensing pipeline setup, dashboard, and database migration.';
  if (path === 'PLAN.md') return 'Canonical architecture document covering schema, phases, risks, and implementation decisions.';
  if (path === 'AGENTS.md') return 'Agent session memory with current phase status, work package reports, and operational checklist.';
  if (cat === 'docs') return `Documentation file (${name}) supporting project conventions, plans, or agent workflows.`;
  if (cat === 'config') return `Configuration (${name}) controlling runtime behavior, stations, or observability settings.`;
  if (cat === 'infra') return `Infrastructure definition (${name}) for container builds, compose orchestration, or CI.`;
  if (cat === 'markup') return `HTML template (${name}) for the FastAPI dashboard UI.`;
  if (isTestPath(path)) return `Pytest module exercising ${name.replace(/^test_/, '').replace(/\.py$/, '')} behavior.`;
  const fc = metrics.functionCount || 0;
  const cc = metrics.classCount || 0;
  if (fc || cc) return `Python module with ${fc} function(s) and ${cc} class(es) in the ${path.split('/')[0]} package.`;
  return `Project file ${path} in the radio ad-sensing pipeline codebase.`;
}

function isTestPath(path) {
  return /(^tests\/|test_|_test\.py$)/.test(path);
}

function complexityFrom(metrics, lines) {
  const n = metrics.nonEmptyLines || lines || 0;
  if (n > 200) return 'complex';
  if (n > 50) return 'moderate';
  return 'simple';
}

function buildGraph(batch, extractResults) {
  const nodes = [];
  const edges = [];
  const nodeIds = new Set();

  const addNode = (n) => {
    if (!nodeIds.has(n.id)) {
      nodeIds.add(n.id);
      nodes.push(n);
    }
  };

  for (const file of extractResults.results || []) {
    const { path, fileCategory, language, totalLines, nonEmptyLines, functions = [], classes = [], exports = [], metrics = {} } = file;
    const type = nodeTypeForType(fileCategory, path);
    const prefix = prefixForType(type);
    const id = `${prefix}:${path}`;
    const isTest = isTestPath(path);

    addNode({
      id,
      type,
      name: basename(path),
      filePath: path,
      summary: summaryFor(path, fileCategory, { ...metrics, functionCount: functions.length, classCount: classes.length }),
      tags: tagsFor(path, fileCategory, isTest),
      complexity: complexityFrom({ nonEmptyLines }, totalLines || nonEmptyLines),
    });

    for (const imp of batch.batchImportData[path] || []) {
      const impType = nodeTypeForCategory('code', imp);
      const impPrefix = prefixForType(impType);
      edges.push({
        source: id,
        target: `${impPrefix}:${imp}`,
        type: 'imports',
        direction: 'forward',
        weight: 0.7,
      });
    }

    for (const fn of functions) {
      if (!fn.name) continue;
      const lines = (fn.endLine || 0) - (fn.startLine || 0);
      const exported = exports.some((e) => e.name === fn.name);
      if (!exported && lines < 10) continue;
      const fnId = `function:${path}:${fn.name}`;
      addNode({
        id: fnId,
        type: 'function',
        name: fn.name,
        filePath: path,
        lineRange: [fn.startLine, fn.endLine],
        summary: `${fn.name} in ${basename(path)}.`,
        tags: tagsFor(path, fileCategory, isTest).slice(0, 3),
        complexity: lines > 50 ? 'moderate' : 'simple',
      });
      edges.push({ source: id, target: fnId, type: 'contains', direction: 'forward', weight: 1.0 });
      if (exported) {
        edges.push({ source: id, target: fnId, type: 'exports', direction: 'forward', weight: 0.8 });
      }
    }

    for (const cls of classes) {
      if (!cls.name) continue;
      const lines = (cls.endLine || 0) - (cls.startLine || 0);
      const exported = exports.some((e) => e.name === cls.name);
      if (!exported && (cls.methods?.length || 0) < 2 && lines < 20) continue;
      const clsId = `class:${path}:${cls.name}`;
      addNode({
        id: clsId,
        type: 'class',
        name: cls.name,
        filePath: path,
        lineRange: [cls.startLine, cls.endLine],
        summary: `${cls.name} class in ${basename(path)}.`,
        tags: tagsFor(path, fileCategory, isTest).slice(0, 3),
        complexity: lines > 100 ? 'complex' : lines > 30 ? 'moderate' : 'simple',
      });
      edges.push({ source: id, target: clsId, type: 'contains', direction: 'forward', weight: 1.0 });
      if (exported) {
        edges.push({ source: id, target: clsId, type: 'exports', direction: 'forward', weight: 0.8 });
      }
    }

    if (fileCategory === 'docs' && (path === 'README.md' || path === 'PLAN.md')) {
      edges.push({ source: id, target: 'file:shared/db.py', type: 'documents', direction: 'forward', weight: 0.5 });
    }
    if (/Dockerfile$/.test(path)) {
      const svc = path.replace('Dockerfile', '').replace(/\/$/, '') || '.';
      const main = svc === 'ingestor' ? 'ingestor/__main__.py'
        : svc === 'worker' ? 'worker/__main__.py'
        : svc === 'dashboard' ? 'dashboard/__main__.py'
        : svc === 'alerter' ? 'alerter/__main__.py'
        : 'shared/db.py';
      edges.push({ source: id, target: `file:${main}`, type: 'deploys', direction: 'forward', weight: 0.7 });
    }
  }

  return { nodes, edges };
}

function nodeTypeForType(cat, path) {
  return nodeTypeForCategory(cat, path);
}

for (const batch of batches.batches) {
  const idx = batch.batchIndex;
  const inputPath = join(PROJECT_ROOT, `.understand-anything/tmp/ua-file-analyzer-input-${idx}.json`);
  const extractPath = join(PROJECT_ROOT, `.understand-anything/tmp/ua-file-extract-results-${idx}.json`);
  const outputPath = join(PROJECT_ROOT, `.understand-anything/intermediate/batch-${idx}.json`);

  const input = {
    projectRoot: PROJECT_ROOT,
    batchFiles: batch.files,
    batchImportData: batch.batchImportData,
  };
  writeFileSync(inputPath, JSON.stringify(input, null, 2));

  const r = spawnSync('node', [join(SKILL_DIR, 'extract-structure.mjs'), inputPath, extractPath], {
    encoding: 'utf8',
    timeout: 120000,
  });
  if (r.status !== 0) {
    console.error(`Batch ${idx} extract-structure failed:`, r.stderr);
    process.exit(1);
  }
  if (!existsSync(extractPath)) {
    console.error(`Batch ${idx}: missing extract output`);
    process.exit(1);
  }

  const extract = JSON.parse(readFileSync(extractPath, 'utf8'));
  const graph = buildGraph(batch, extract);
  writeFileSync(outputPath, JSON.stringify(graph, null, 2));
  console.log(`Batch ${idx}/${batches.totalBatches}: ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
}
