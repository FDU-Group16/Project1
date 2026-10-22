import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

for (const name of readdirSync(join(process.cwd(), 'contracts')).filter(name => name.endsWith('.openapi.json'))) {
const filename = join(process.cwd(), 'contracts', name);
const document = JSON.parse(readFileSync(filename, 'utf8'));

function requireValue(condition, message) {
  if (!condition) throw new Error(message);
}

requireValue(/^3\.1\./.test(document.openapi ?? ''), 'Contract must use OpenAPI 3.1');
requireValue(document.info?.version, 'Contract needs an info.version');
requireValue(Object.keys(document.paths ?? {}).length > 0, 'Contract needs a path');

const operationIds = new Set();
for (const [path, methods] of Object.entries(document.paths)) {
  for (const [method, operation] of Object.entries(methods)) {
    if (!['get', 'put', 'post', 'patch', 'delete'].includes(method)) continue;
    requireValue(operation.operationId, `Missing operationId: ${method} ${path}`);
    requireValue(!operationIds.has(operation.operationId), `Duplicate operationId: ${operation.operationId}`);
    requireValue(Object.keys(operation.responses ?? {}).length > 0, `Missing responses: ${method} ${path}`);
    operationIds.add(operation.operationId);
  }
}

function visit(value) {
  if (!value || typeof value !== 'object') return;
  if (typeof value.$ref === 'string') {
    requireValue(value.$ref.startsWith('#/'), `External ref is not allowed: ${value.$ref}`);
    const parts = value.$ref.slice(2).split('/').map((part) => part.replaceAll('~1', '/').replaceAll('~0', '~'));
    let target = document;
    for (const part of parts) target = target?.[part];
    requireValue(target !== undefined, `Unresolved ref: ${value.$ref}`);
  }
  for (const child of Object.values(value)) visit(child);
}

visit(document);
console.log(`Checked ${operationIds.size} OpenAPI operations and local references.`);

}
