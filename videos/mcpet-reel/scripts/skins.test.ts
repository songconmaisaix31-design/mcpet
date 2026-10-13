import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {ffmpegPath} from './ffmpeg';
import {PNG} from 'pngjs';

function pixels(path: string, crop?: string) {
  const result = spawnSync(ffmpegPath(), ['-hide_banner', '-loglevel', 'error', '-nostdin', '-i', path, ...(crop ? ['-vf', crop] : []), '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', '-pix_fmt', 'rgba', '-'], {maxBuffer: 8 * 1024 * 1024});
  assert.equal(result.status, 0, result.stderr.toString());
  return PNG.sync.read(result.stdout).data;
}

test('两套角色提取保持源像素和透明通道，支持用户导入', () => {
  const imported = process.env.MCPET_REEL_SKIN_DIR;
  const assets = resolve('../../assets');
  const manifest = imported ? null : JSON.parse(readFileSync(join(assets, 'dsh-deepseek/manifest.json'), 'utf8'));
  const dragon = imported ? null : readFileSync(join(assets, 'longniang/spritesheet-runtime.png'));
  const deepseekExpected = imported ? pixels(join(imported, 'deepseek-idle.png')) : pixels(join(assets, 'dsh-deepseek', manifest.animations.idle.pages[0]), `crop=${manifest.cell_size}:${manifest.cell_size}:0:0`);
  const chatgptExpected = imported ? pixels(join(imported, 'chatgpt-idle.png')) : pixels(join(assets, 'longniang/spritesheet-runtime.png'), `crop=${dragon!.readUInt32BE(16) / 8}:${dragon!.readUInt32BE(20) / 11}:0:0`);
  for (const [name, expected] of [['deepseek', deepseekExpected], ['chatgpt', chatgptExpected]] as const) {
    const actual = pixels(`public/pet-skins/${name}-idle.png`);
    assert(actual.equals(expected), `${name} 不应改变源角色像素`);
    let transparent = false, visible = false;
    for (let i = 3; i < actual.length; i += 4) {transparent ||= actual[i] === 0; visible ||= actual[i] > 0;}
    assert(transparent && visible, `${name} 需要完整透明背景和可见角色`);
  }
});
