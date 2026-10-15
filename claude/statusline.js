const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

let raw = '';
process.stdin.on('data', d => (raw += d));
process.stdin.on('end', () => {
  const orca = path.join(os.homedir(), '.orca', 'agent-hooks', 'claude-statusline.cmd');
  if (fs.existsSync(orca)) spawnSync('cmd.exe', ['/d', '/c', orca], { input: raw, timeout: 2000, windowsHide: true });

  let j = {};
  try { j = JSON.parse(raw); } catch {}
  const cw = j.context_window || {};
  const k = n => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n || 0));
  const parts = [`in ${k(cw.total_input_tokens)}`, `out ${k(cw.total_output_tokens)}`];
  if (cw.used_percentage != null) parts.push(`ctx ${Math.round(cw.used_percentage)}%`);
  if (j.cost && j.cost.total_cost_usd != null) parts.push(`$${j.cost.total_cost_usd.toFixed(2)}`);
  process.stdout.write(parts.join(' | '));
});
