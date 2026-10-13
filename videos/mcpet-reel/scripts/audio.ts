import {spawnSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';
import {measure} from '../src/behavior';
import {alarmCue, worry} from '../src/behaviors/worry';
import {design} from '../src/design';
import {readWav, writeWav} from './wav';
import {ffmpegPath} from './ffmpeg';

const ffmpeg = ffmpegPath();
const voice = readWav('public/audio/worry-voice-source.wav');
const frames = measure(worry, design.fps).durationInFrames;
const cue = alarmCue(design.fps);
const startSample = Math.round(cue * voice.sampleRate / design.fps);
const mix = new Float64Array(Math.ceil(frames * voice.sampleRate / design.fps));
for (let i = 0; i < voice.samples; i++) mix[startSample + i] = voice.pcm.readInt16LE(i * 2) / 32768;

// 警觉时的小敲击：指数包络降到听觉阈值后自然结束，未指定音效时长。
for (let i = 0; startSample + i < mix.length; i++) {
  const t = i / voice.sampleRate;
  const envelope = Math.exp(-32 * t);
  if (envelope < 0.0001) break;
  mix[startSample + i] += 0.14 * envelope * Math.sin(2 * Math.PI * 210 * t) + 0.05 * envelope * Math.sin(2 * Math.PI * 840 * t);
}
writeWav('public/audio/worry-mix-raw.wav', mix, voice.sampleRate);

function run(args: string[]) {
  const result = spawnSync(ffmpeg, ['-hide_banner', '-nostdin', ...args], {encoding: 'utf8'});
  if (result.status !== 0) throw new Error(result.stderr || result.error?.message || 'FFmpeg 未完成');
  return result.stderr;
}
function stats(log: string): Record<string, string> {
  const match = log.match(/\{\s*"input_i"[\s\S]*?\}/);
  if (!match) throw new Error('未得到响度测量值');
  return JSON.parse(match[0]);
}
const first = stats(run(['-i', 'public/audio/worry-mix-raw.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']));
const normalize = `loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=${first.input_i}:measured_TP=${first.input_tp}:measured_LRA=${first.input_lra}:measured_thresh=${first.input_thresh}:offset=${first.target_offset}:linear=true:print_format=json`;
run(['-y', '-i', 'public/audio/worry-mix-raw.wav', '-af', normalize, '-ar', String(voice.sampleRate), '-ac', '1', '-c:a', 'pcm_s16le', 'public/audio/worry-mix.wav']);
const verified = stats(run(['-i', 'public/audio/worry-mix.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']));
writeFileSync('public/audio/loudness.json', JSON.stringify({scope: 'worry-sample-mix', source: first, verified}, null, 2) + '\n');
if (Math.abs(Number(verified.input_i) + 14) > 0.3) throw new Error(`样板混音响度偏离目标：${verified.input_i}`);
console.log(`样板混音：${verified.input_i} LUFS；true peak ${verified.input_tp} dBTP；音效触发点 ${cue}`);
