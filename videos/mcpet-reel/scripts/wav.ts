import {readFileSync, writeFileSync} from 'node:fs';

export function readWav(path: string) {
  const buffer = readFileSync(path);
  if (buffer.toString('ascii', 0, 4) !== 'RIFF' || buffer.toString('ascii', 8, 12) !== 'WAVE') throw new Error('需要 RIFF WAV 配音');
  let channels = 0, sampleRate = 0, bits = 0, format = 0;
  let pcm = Buffer.alloc(0);
  for (let offset = 12; offset + 8 <= buffer.length;) {
    const id = buffer.toString('ascii', offset, offset + 4);
    const length = buffer.readUInt32LE(offset + 4);
    if (id === 'fmt ') {
      format = buffer.readUInt16LE(offset + 8);
      channels = buffer.readUInt16LE(offset + 10);
      sampleRate = buffer.readUInt32LE(offset + 12);
      bits = buffer.readUInt16LE(offset + 22);
    }
    if (id === 'data') pcm = buffer.subarray(offset + 8, offset + 8 + length);
    offset += 8 + length + (length % 2);
  }
  if (format !== 1 || channels !== 1 || bits !== 16 || pcm.length === 0) throw new Error('需要 16-bit 单声道 PCM WAV');
  return {sampleRate, samples: pcm.length / 2, pcm};
}

export function writeWav(path: string, data: Float64Array, sampleRate: number) {
  const buffer = Buffer.alloc(44 + data.length * 2);
  buffer.write('RIFF', 0); buffer.writeUInt32LE(buffer.length - 8, 4); buffer.write('WAVEfmt ', 8);
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24); buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write('data', 36); buffer.writeUInt32LE(data.length * 2, 40);
  data.forEach((value, index) => buffer.writeInt16LE(Math.round(Math.max(-1, Math.min(1, value)) * 32767), 44 + index * 2));
  writeFileSync(path, buffer);
}
