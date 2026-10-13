import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {assertHandoff, measure} from '../src/behavior';
import {alarmCue, worry} from '../src/behaviors/worry';
import {design, rhythm} from '../src/design';

test('自然结束必须等数字、弹簧、打字和配音都完成', () => {
  const {states} = measure(worry, design.fps);
  assert(states.length > 1);
  assert(!worry.settleWhen(states.at(-2)!));
  const last = states.at(-1)!;
  assert(worry.settleWhen(last));
  assert.equal(last.balance, 4.37);
  assert.equal(last.spokenSamples, last.totalSamples);
  assert.equal(last.typedCharacters, last.totalCharacters);
  assert.equal(last.angle, 0);
  assertHandoff(last.pose, worry.exitPose);
});

test('测量和任意位置 seek 得到同一状态；生成的时间轴可复现', () => {
  const {states, durationInFrames} = measure(worry, design.fps);
  for (const frame of [0, alarmCue(design.fps), Math.floor(durationInFrames / 2), durationInFrames - 1]) {
    assert.deepEqual(worry.sample(frame, design.fps), states[frame]);
  }
  assert.deepEqual(measure(worry, design.fps).states, states);
  const timeline = JSON.parse(readFileSync('timeline.json', 'utf8'));
  assert.equal(timeline.durationInFrames, durationInFrames);
  assert.deepEqual(timeline.behaviors[0].exitPose, worry.exitPose);
});

test('抖动包络单调衰减，结束条件不读取帧数', () => {
  const {states} = measure(worry, design.fps);
  const alarmStates = states.filter(state => state.alarm);
  assert(alarmStates[0].shakeEnvelope > 0);
  alarmStates.slice(1).forEach((state, i) => assert(state.shakeEnvelope <= alarmStates[i].shakeEnvelope));
  assert(!/frame|duration|elapsed|seconds|time/.test(worry.settleWhen.toString()));
  const incomplete = {...states.at(-1)!, spokenSamples: 0};
  assert(!worry.settleWhen(incomplete));
});

test('余额单调滚落，不让弹簧冲过头造成金额反弹', () => {
  const {states} = measure(worry, design.fps);
  states.slice(1).forEach((state, i) => {
    assert(state.balance <= states[i].balance);
    assert(state.balance >= 4.37);
  });
});

test('全局打字速率影响自然时长，没有固定片段长度', () => {
  const original = rhythm.typingRate;
  const baseline = measure(worry, design.fps).durationInFrames;
  try {
    rhythm.typingRate = original / 4;
    assert(measure(worry, design.fps).durationInFrames > baseline);
  } finally {rhythm.typingRate = original;}
});

test('结束锚点可严格继承；不同朝向会拒绝接棒', () => {
  assertHandoff(worry.exitPose, {...worry.exitPose});
  assert.throws(() => assertHandoff(worry.exitPose, {...worry.exitPose, heading: 'right'}));
  assert(worry.exitPose.x + 180 < design.safe.right);
  assert(worry.exitPose.y + 225 < design.safe.bottom);
});
