import {writeFileSync} from 'node:fs';
import {measure} from '../src/behavior';
import {alarmCue, worry} from '../src/behaviors/worry';
import {design, rhythm} from '../src/design';

const measured = measure(worry, design.fps);
const timeline = {
  schema: 1, stage: 'worry-sample', fps: design.fps, width: design.width, height: design.height, rhythm,
  durationInFrames: measured.durationInFrames,
  behaviors: [{actor: worry.actor, verb: worry.verb, start: 0, durationInFrames: measured.durationInFrames, enterPose: worry.enterPose, exitPose: worry.exitPose, events: {alarm: alarmCue(design.fps)}}],
};
writeFileSync('timeline.json', JSON.stringify(timeline, null, 2) + '\n');
console.log(`${worry.actor}.${worry.verb} 自然完成：${measured.durationInFrames} frames (${(measured.durationInFrames / design.fps).toFixed(3)}s)`);
