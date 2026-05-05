import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function main() {
  const cwd = join(__dirname, '..');
  try {
    const output = execSync(
      'npx eslint src/ --format json --no-cache',
      { cwd, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const results = JSON.parse(output);
    report(results);
  } catch (err) {
    if (err.stdout) {
      try {
        const results = JSON.parse(err.stdout);
        report(results);
        return;
      } catch {
        // fall through
      }
    }
    console.error('Failed to run i18n check:', err.stderr || err.message);
    process.exit(1);
  }
}

function report(results) {
  let violations = 0;
  for (const result of results) {
    const fileViolations = result.messages.filter(
      (m) => m.ruleId === 'local/no-inline-user-strings'
    );
    if (fileViolations.length > 0) {
      violations += fileViolations.length;
      const relativePath = result.filePath.replace(process.cwd() + '/', '');
      console.log(`${relativePath}:`);
      for (const v of fileViolations) {
        console.log(`  line ${v.line}: ${v.message}`);
      }
    }
  }
  if (violations > 0) {
    console.error(`\n${violations} i18n violation(s) found.`);
    process.exit(1);
  }
  console.log('No i18n violations found.');
  process.exit(0);
}

main();
