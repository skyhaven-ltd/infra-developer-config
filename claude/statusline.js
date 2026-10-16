const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

let raw = '';
process.stdin.on('data', d => (raw += d));
process.stdin.on('end', () => {
  const orca = path.join(os.homedir(), '.orca', 'agent-hooks', 'claude-statusline.cmd');
  if (fs.existsSync(orca)) spawnSync('cmd.exe', ['/d', '/c', orca], { input: raw, timeout: 2000, windowsHide: true });
});
