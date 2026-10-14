import {copyFileSync, existsSync, mkdirSync, readFileSync} from 'node:fs';
import {resolve, join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {ffmpegPath} from './ffmpeg';
import {importCeTaPet} from './import-cetapet';

importCeTaPet();

const output = resolve('public/pet-skins');
mkdirSync(output, {recursive: true});
const imported = process.env.MCPET_REEL_SKIN_DIR;

if (imported) {
  // 用户导入的本地皮肤包仅留在忽略目录，路径不写入产物。
  for (const name of ['chatgpt-idle.png']) {
    const source = join(resolve(imported), name);
    if (!existsSync(source)) throw new Error(`导入皮肤包缺少 ${name}`);
    copyFileSync(source, join(output, name));
  }
} else {
  const assets = resolve('../../assets');
  const dragonDir = join(assets, 'longniang');
  const dragon = join(dragonDir, 'spritesheet-runtime.png');
  if (!existsSync(dragon)) throw new Error('缺少 ChatGPT 娘素材，请使用 MCPET_REEL_SKIN_DIR 导入皮肤包');
  const meta = JSON.parse(readFileSync(join(dragonDir, 'pet.json'), 'utf8'));
  const rows = JSON.parse(readFileSync(join(dragonDir, 'sprite-rows.json'), 'utf8')).rows as {state: string; row: number}[];
  const idle = rows.find(row => row.state === 'idle');
  if (!idle) throw new Error('ChatGPT 娘素材缺少待机行');
  const header = readFileSync(dragon).subarray(0, 24);
  const width = header.readUInt32BE(16), height = header.readUInt32BE(20);
  const cellWidth = meta.cell_width || width / (meta.columns || 8);
  const cellHeight = meta.cell_height || height / (meta.rows || 11);
  if (!Number.isInteger(cellWidth) || !Number.isInteger(cellHeight)) throw new Error('ChatGPT 娘图集网格不一致');
  function extract(source: string, crop: string, name: string) {
    const result = spawnSync(ffmpegPath(), ['-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', source, '-vf', crop, '-frames:v', '1', '-c:v', 'png', join(output, name)], {encoding: 'utf8'});
    if (result.status !== 0) throw new Error(result.stderr || result.error?.message || '角色素材提取失败');
  }
  extract(dragon, `crop=${cellWidth}:${cellHeight}:0:${idle.row * cellHeight}`, 'chatgpt-idle.png');
}
console.log('早期 DeepSeek 娘九种姿态 / ChatGPT 娘：本地素材已准备（未上传皮肤）');
