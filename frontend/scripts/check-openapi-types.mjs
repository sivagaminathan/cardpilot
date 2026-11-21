import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const frontendDir = resolve(import.meta.dirname, '..');
const repoRoot = resolve(frontendDir, '..');
const openApiPath = join(repoRoot, 'docs', 'openapi.json');
const committedTypesPath = join(frontendDir, 'src', 'types', 'api.generated.ts');

const tempDir = mkdtempSync(join(tmpdir(), 'cardpilot-openapi-check-'));
const tempOutputPath = join(tempDir, 'api.generated.ts');

try {
  const cliBin = join(
    frontendDir,
    'node_modules',
    '.bin',
    process.platform === 'win32' ? 'openapi-typescript.cmd' : 'openapi-typescript',
  );
  execFileSync(cliBin, [openApiPath, '-o', tempOutputPath], {
    cwd: frontendDir,
    stdio: 'pipe',
    shell: process.platform === 'win32',
  });

  const generated = readFileSync(tempOutputPath, 'utf8').replaceAll('\r\n', '\n');
  let committed = '';
  try {
    committed = readFileSync(committedTypesPath, 'utf8').replaceAll('\r\n', '\n');
  } catch {
    console.error(`ERROR: Generated types file missing at ${committedTypesPath}`);
    process.exitCode = 1;
  }

  if (!process.exitCode && generated !== committed) {
    console.error(
      'ERROR: Generated TypeScript types in frontend/src/types/api.generated.ts are stale. Run "make openapi" to regenerate.',
    );
    process.exitCode = 1;
  } else if (!process.exitCode) {
    console.log('Generated TypeScript API types are up to date.');
  }
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
