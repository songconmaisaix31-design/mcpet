import {mkdirSync, writeFileSync} from 'node:fs';
import {readWav} from './wav';

const voice = readWav('public/audio/worry-voice-source.wav');
mkdirSync('src/generated', {recursive: true});
writeFileSync('src/generated/audio.json', JSON.stringify({sampleRate: voice.sampleRate, samples: voice.samples, model: 'cosyvoice-v3-flash', voice: 'longhua_v3'}, null, 2) + '\n');
console.log(`配音：${voice.samples} samples / ${voice.sampleRate} Hz`);
