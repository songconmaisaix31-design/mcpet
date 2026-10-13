import {Composition} from 'remotion';
import timeline from '../timeline.json';
import {measure} from './behavior';
import {worry} from './behaviors/worry';
import {design} from './design';
import {WorrySample} from './Worry';

export const MyComposition = () => <Composition
  id="WorrySample"
  component={WorrySample}
  durationInFrames={timeline.durationInFrames}
  fps={design.fps}
  width={design.width}
  height={design.height}
  calculateMetadata={() => ({durationInFrames: measure(worry, design.fps).durationInFrames})}
/>;
