export type Pose = Readonly<{
  x: number;
  y: number;
  heading: 'left' | 'right' | 'front';
  expression: 'curious' | 'worry' | 'focus';
  scale: number;
  rotation: number;
}>;

export type Behavior<State> = {
  actor: 'Pet' | 'Dragon';
  verb: string;
  target: object;
  intent: string;
  enterPose: Pose;
  sample: (frame: number, fps: number) => State;
  settleWhen: (state: State) => boolean;
  exitPose: Pose;
  sfx?: 'click' | 'whoosh' | 'thud' | 'sparkle';
};

export function assertHandoff(previous: Pose, next: Pose) {
  for (const key of Object.keys(previous) as (keyof Pose)[]) {
    if (previous[key] !== next[key]) throw new Error(`姿态衔接不一致：${key}`);
  }
}

export function measure<State>(behavior: Behavior<State>, fps: number) {
  const states: State[] = [];
  // 编译器防止失控的护栏；它不会决定行为的结束时间。
  const watchdog = fps * 600;
  for (let frame = 0; frame < watchdog; frame++) {
    const state = behavior.sample(frame, fps);
    states.push(state);
    if (behavior.settleWhen(state)) return {durationInFrames: states.length, states};
  }
  throw new Error(`${behavior.verb} 未自然完成；拒绝生成时间轴`);
}
