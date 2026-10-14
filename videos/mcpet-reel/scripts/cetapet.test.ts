import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {PNG} from 'pngjs';
import {cetapetDirectory} from './import-cetapet';
import {cetapetActions, cetapetImage, cetapetSource} from '../src/actors/cetapet';

test('导入清单覆盖早期仓库全部姿态 PNG，没有遗漏或混入后期素材', () => {
  const source = cetapetDirectory();
  const revision = spawnSync('git', ['-C', source, 'rev-parse', 'HEAD'], {encoding: 'utf8'});
  assert.equal(revision.status, 0);
  assert.equal(revision.stdout.trim(), cetapetSource.commit);
  const tree = spawnSync('git', ['-C', source, 'ls-tree', '-r', 'HEAD', '--name-only', '--', 'CetaPet/asset_library/move'], {encoding: 'utf8'});
  assert.equal(tree.status, 0);
  const upstream = tree.stdout.trim().split('\n').filter(name => name.endsWith('.png')).sort();
  const imported = cetapetActions.map(action => `CetaPet/asset_library/${action.file}`).sort();
  assert.equal(upstream.length, 9);
  assert.deepEqual(imported, upstream);
});

test('九张姿态图与源文件逐字节相同，透明图可解码且保留来源文件', () => {
  const source = cetapetDirectory();
  for (const action of cetapetActions) {
    const original = readFileSync(join(source, 'CetaPet/asset_library', action.file));
    const copy = readFileSync(join('public', cetapetImage(action.id)));
    assert(copy.equals(original), `${action.id} 应原样复制`);
    const image = PNG.sync.read(copy);
    assert(image.width > 0 && image.height > 0);
    let visible = false, transparent = false;
    for (let i = 3; i < image.data.length; i += 4) {visible ||= image.data[i] > 0; transparent ||= image.data[i] === 0;}
    assert(visible && transparent, `${action.id} 需要可见角色和透明背景`);
  }
  assert(readFileSync('public/pet-skins/cetapet/LICENSE').equals(readFileSync(join(source, 'LICENSE'))));
  assert(readFileSync('public/pet-skins/cetapet/UPSTREAM-README.md').equals(readFileSync(join(source, 'README.md'))));
});
