import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { resolveProjectRoot } from '../context.mjs';

const LIVE_TOKEN_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const IMPECCABLE_DIR = '.impeccable';
export const LIVE_DIR = 'live';
export const CRITIQUE_DIR = 'critique';

export function getImpeccableDir(cwd = process.cwd(), options = {}) {
  return path.join(resolveProjectRoot(cwd, options), IMPECCABLE_DIR);
}

export function getDesignSidecarPath(cwd = process.cwd(), options = {}) {
  return path.join(getImpeccableDir(cwd, options), 'design.json');
}

export function getDesignSidecarCandidates(cwd = process.cwd(), contextDir = cwd, options = {}) {
  const projectRoot = resolveProjectRoot(cwd, options);
  const candidates = [
    getDesignSidecarPath(cwd, options),
    path.join(projectRoot, 'DESIGN.json'),
  ];
  const contextLegacy = path.join(contextDir, 'DESIGN.json');
  if (!candidates.includes(contextLegacy)) candidates.push(contextLegacy);
  return candidates;
}

export function resolveDesignSidecarPath(cwd = process.cwd(), contextDir = cwd, options = {}) {
  return firstExisting(getDesignSidecarCandidates(cwd, contextDir, options));
}

export function getLiveDir(cwd = process.cwd(), options = {}) {
  return path.join(getImpeccableDir(cwd, options), LIVE_DIR);
}

export function getLiveConfigPath(cwd = process.cwd(), options = {}) {
  return path.join(getLiveDir(cwd, options), 'config.json');
}

export function getLegacyLiveConfigPath(scriptsDir) {
  return path.join(scriptsDir, 'config.json');
}

export function resolveLiveConfigPath({ cwd = process.cwd(), scriptsDir, env = process.env, targetPath } = {}) {
  if (env.IMPECCABLE_LIVE_CONFIG && env.IMPECCABLE_LIVE_CONFIG.trim()) {
    const configured = env.IMPECCABLE_LIVE_CONFIG.trim();
    return path.isAbsolute(configured) ? configured : path.resolve(cwd, configured);
  }
  const primary = getLiveConfigPath(cwd, { targetPath });
  if (fs.existsSync(primary)) return primary;
  if (scriptsDir) {
    const legacy = getLegacyLiveConfigPath(scriptsDir);
    if (fs.existsSync(legacy)) return legacy;
  }
  return primary;
}

export function getLiveServerPath(cwd = process.cwd(), options = {}) {
  return path.join(getLiveDir(cwd, options), 'server.json');
}

export function getLiveTokenPath(cwd = process.cwd(), options = {}) {
  const projectRoot = resolveProjectRoot(cwd, options);
  const scope = createHash('sha256').update(projectRoot).digest('hex').slice(0, 24);
  const base = process.env.IMPECCABLE_LOCAL_STATE_DIR
    || path.join(os.homedir() || os.tmpdir(), '.impeccable', 'live-tokens');
  return path.join(base, scope, 'token.json');
}

export function getLegacyLiveServerPath(cwd = process.cwd(), options = {}) {
  return path.join(resolveProjectRoot(cwd, options), '.impeccable-live.json');
}

export function readLiveServerInfo(cwd = process.cwd(), options = {}) {
  for (const filePath of [getLiveServerPath(cwd, options), getLegacyLiveServerPath(cwd, options)]) {
    try {
      const info = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      if (info && typeof info.pid === 'number' && !isLiveServerPidReachable(info.pid)) {
        try { fs.unlinkSync(filePath); } catch {}
        continue;
      }
      const localToken = readLiveToken(cwd, options);
      if (!localToken || info?.token !== localToken) {
        try { fs.unlinkSync(filePath); } catch {}
        continue;
      }
      return { info, path: filePath };
    } catch {
      /* try next */
    }
  }
  return null;
}

export function isLiveServerPidReachable(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    // ESRCH means "no such process". EPERM means the process exists but this
    // user cannot signal it, so the live server info is still valid.
    return err?.code !== 'ESRCH';
  }
}

export function writeLiveServerInfo(cwd = process.cwd(), info, options = {}) {
  const filePath = getLiveServerPath(cwd, options);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(info));
  return filePath;
}

export function readLiveToken(cwd = process.cwd(), options = {}) {
  const filePath = getLiveTokenPath(cwd, options);
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    if (typeof data?.token === 'string' && LIVE_TOKEN_RE.test(data.token)) {
      return data.token;
    }
    try { fs.unlinkSync(filePath); } catch {}
    return null;
  } catch {
    return null;
  }
}

export function writeLiveToken(cwd = process.cwd(), token, options = {}) {
  if (!LIVE_TOKEN_RE.test(String(token || ''))) {
    throw new Error('Invalid live token format');
  }
  const filePath = getLiveTokenPath(cwd, options);
  fs.mkdirSync(path.dirname(filePath), { recursive: true, mode: 0o700 });
  fs.writeFileSync(filePath, JSON.stringify({ token }), { mode: 0o600 });
  return filePath;
}

export function removeLiveToken(cwd = process.cwd(), options = {}) {
  try { fs.unlinkSync(getLiveTokenPath(cwd, options)); } catch {}
}

export function removeLiveServerInfo(cwd = process.cwd(), options = {}) {
  for (const filePath of [getLiveServerPath(cwd, options), getLegacyLiveServerPath(cwd, options)]) {
    try { fs.unlinkSync(filePath); } catch {}
  }
}

export function getLiveSessionsDir(cwd = process.cwd(), options = {}) {
  return path.join(getLiveDir(cwd, options), 'sessions');
}

export function getLegacyLiveSessionsDir(cwd = process.cwd(), options = {}) {
  return path.join(resolveProjectRoot(cwd, options), '.impeccable-live', 'sessions');
}

export function getLiveAnnotationsDir(cwd = process.cwd(), options = {}) {
  return path.join(getLiveDir(cwd, options), 'annotations');
}

export function getCritiqueDir(cwd = process.cwd(), options = {}) {
  return path.join(getImpeccableDir(cwd, options), CRITIQUE_DIR);
}

export function getLegacyLiveAnnotationsDir(cwd = process.cwd(), options = {}) {
  return path.join(resolveProjectRoot(cwd, options), '.impeccable-live', 'annotations');
}

function firstExisting(paths) {
  return paths.find((filePath) => fs.existsSync(filePath)) || null;
}
