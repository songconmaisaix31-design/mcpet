import {spring} from 'remotion';
import voice from '../generated/audio.json';
import {Behavior, Pose} from '../behavior';
import {design, rhythm} from '../design';

export const dialogue = '小钱包只剩四块三毛七啦。\n先别慌，我陪你盯着。';
export const startPose: Pose = {x: 745, y: 1240, heading: 'left', expression: 'curious', scale: 1, rotation: 0};
export const focusPose: Pose = {...startPose, x: 710, expression: 'focus'};
const startingBalance = 12.80;
const finalBalance = 4.37;

export type WorryState = {
  balance: number;
  balanceError: number;
  balanceVelocity: number;
  pose: Pose;
  angle: number;
  shakeEnvelope: number;
  driftError: number;
  driftVelocity: number;
  bubble: number;
  bubbleError: number;
  bubbleVelocity: number;
  typedCharacters: number;
  totalCharacters: number;
  spokenSamples: number;
  totalSamples: number;
  alarm: boolean;
};

const motion = (frame: number, fps: number) => spring({frame: Math.max(0, frame), fps, config: {stiffness: rhythm.stiffness, damping: rhythm.damping}});

// 金额的消耗只向前走；弹簧的冲过头留给有重量的角色与气泡。
const consumed = (frame: number, fps: number) => {
  let value = 0;
  for (let step = 0; step <= frame; step++) value = Math.max(value, Math.min(1, motion(step, fps)));
  return value;
};

export function alarmCue(fps: number) {
  let frame = 0;
  while (startingBalance + (finalBalance - startingBalance) * motion(frame, fps) >= 5) frame++;
  return frame;
}

export const worry: Behavior<WorryState> = {
  actor: 'Pet', verb: 'worry', target: {balance: finalBalance},
  intent: '小钱包告急，有个小搭子陪你一起看着。',
  enterPose: startPose, exitPose: focusPose, sfx: 'thud',
  sample(frame, fps) {
    const cue = alarmCue(fps);
    const local = frame - cue;
    const elapsed = Math.max(0, local / fps);
    const alarm = local >= 0;
    const value = consumed(frame, fps);
    const before = consumed(frame - 1, fps);
    const balance = startingBalance + (finalBalance - startingBalance) * value;
    const drift = alarm ? motion(local, fps) : 0;
    const driftBefore = alarm ? motion(local - 1, fps) : 0;
    const shakeEnvelope = alarm ? 7 * Math.exp(-rhythm.damping * elapsed / 2) : 0;
    const angle = shakeEnvelope * Math.sin(Math.sqrt(rhythm.stiffness) * elapsed);
    const spokenSamples = Math.min(voice.samples, Math.floor(elapsed * voice.sampleRate));
    const totalCharacters = Array.from(dialogue).length;
    const typedCharacters = alarm ? Math.min(totalCharacters, Math.floor(elapsed * rhythm.typingRate)) : 0;
    const calm = alarm && spokenSamples === voice.samples && shakeEnvelope < 0.001;
    return {
      balance: Math.abs(balance - finalBalance) < 0.001 ? finalBalance : balance,
      balanceError: Math.abs(balance - finalBalance),
      balanceVelocity: Math.abs((value - before) * (finalBalance - startingBalance) * fps),
      pose: calm ? focusPose : {...startPose, x: startPose.x + (focusPose.x - startPose.x) * drift, expression: alarm ? 'worry' : 'curious'},
      angle: calm ? 0 : angle, shakeEnvelope,
      driftError: Math.abs(1 - drift), driftVelocity: Math.abs(drift - driftBefore) * fps,
      bubble: drift, bubbleError: Math.abs(1 - drift), bubbleVelocity: Math.abs(drift - driftBefore) * fps,
      typedCharacters, totalCharacters, spokenSamples, totalSamples: voice.samples, alarm,
    };
  },
  settleWhen: (state) => state.alarm && state.balanceError < 0.001 && state.balanceVelocity < 0.001 && state.shakeEnvelope < 0.001 && state.driftError < 0.0001 && state.driftVelocity < 0.001 && state.bubbleError < 0.0001 && state.bubbleVelocity < 0.001 && state.typedCharacters === state.totalCharacters && state.spokenSamples === state.totalSamples,
};

export const measureOptions = {fps: design.fps};
