import {copyFileSync, existsSync, mkdirSync} from 'node:fs';
import {resolve, join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {cetapetActions, cetapetSource} from '../src/actors/cetapet';

export function cetapetDirectory() {
  const explicit = process.env.MCPET_CETAPET_SOURCE;
  if (explicit) return resolve(explicit);
  const earlyReference = resolve('../../.tmp-test-data/references/cetapet');
  if (existsSync(join(earlyReference, 'CetaPet/asset_library/move'))) return earlyReference;
  return resolve('../../.tmp-test-data/reel-v2-references/cetapet-actions');
}

function git(source: string, args: string[]) {
  const result = spawnSync('git', ['-C', source, ...args], {encoding: 'utf8'});
  if (result.status !== 0) throw new Error(result.stderr || result.error?.message || '参考仓库读取失败');
  return result.stdout.trim();
}

export function importCeTaPet() {
  const source = cetapetDirectory();
  if (!existsSync(source)) {
    mkdirSync(resolve('../../.tmp-test-data/reel-v2-references'), {recursive: true});
    const clone = spawnSync('git', ['clone', '--depth', '1', '--filter=blob:none', '--no-checkout', cetapetSource.repository + '.git', source], {encoding: 'utf8'});
    if (clone.status !== 0) throw new Error(clone.stderr || clone.error?.message || '早期参考仓库下载失败');
  }
  const revision = git(source, ['rev-parse', 'HEAD']);
  if (revision !== cetapetSource.commit) throw new Error('参考仓库版本不符，请提供早期固定版本；不会覆盖已有参考目录');
  if (!existsSync(join(source, 'CetaPet/asset_library/move'))) git(source, ['checkout', '--detach', cetapetSource.commit]);

  const required = [
    ...cetapetActions.map(action => [`CetaPet/asset_library/${action.file}`, `asset_library/${action.file}`]),
    ['LICENSE', 'LICENSE'], ['README.md', 'UPSTREAM-README.md'],
  ];
  for (const [relative] of required) if (!existsSync(join(source, relative))) throw new Error(`早期参考缺少素材：${relative}`);
  for (const [relative, destination] of required) {
    const output = resolve('public/pet-skins/cetapet', destination);
    mkdirSync(resolve(output, '..'), {recursive: true});
    copyFileSync(join(source, relative), output);
    const repositoryOutput = resolve('../../assets/cetapet/original', destination);
    mkdirSync(resolve(repositoryOutput, '..'), {recursive: true});
    copyFileSync(join(source, relative), repositoryOutput);
  }
  console.log(`早期 CeTaPet：${cetapetActions.length} 张原始姿态已复制，版本 ${cetapetSource.commit.slice(0, 7)}`);
}
