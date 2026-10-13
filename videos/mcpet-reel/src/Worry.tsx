import React from 'react';
import {Audio} from '@remotion/media';
import {loadFont} from '@remotion/fonts';
import {AbsoluteFill, cancelRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Pet} from './actors/Pet';
import {dialogue, worry} from './behaviors/worry';
import {design} from './design';

void Promise.all([
  loadFont({family: design.fonts.dialogue, url: staticFile('fonts/HarmonyOS_Sans_SC_Regular.ttf'), weight: '400'}),
  loadFont({family: design.fonts.data, url: staticFile('fonts/JetBrainsMono-Regular.ttf'), weight: '400'}),
]).catch(cancelRender);

export const WorrySample: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const state = worry.sample(frame, fps);
  const {gold, alarm, night} = design.colors;
  const typed = Array.from(dialogue).slice(0, state.typedCharacters).join('');
  const bubble = Math.max(0, Math.min(1, state.bubble));
  return <AbsoluteFill style={{backgroundColor: night, fontFamily: design.fonts.dialogue, color: gold}}>
    <Audio src={staticFile('audio/worry-mix.wav')} />
    <svg width={1080} height={1920} style={{position: 'absolute'}} aria-hidden="true">
      <defs><pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0 H0 V80" fill="none" stroke={gold} strokeOpacity="0.06" /></pattern></defs>
      <rect width="1080" height="1920" fill="url(#grid)" />
      <circle cx="745" cy="1230" r="340" fill={gold} fillOpacity="0.018" />
      <circle cx="745" cy="1230" r="255" fill="none" stroke={gold} strokeOpacity="0.07" />
      <path d="M160 793 H650 Q710 793 710 840 V1015" fill="none" stroke={gold} strokeOpacity="0.2" strokeWidth="3" />
    </svg>
    <div style={{position: 'absolute', left: 160, top: 165, fontFamily: design.fonts.data, fontSize: 28, letterSpacing: 4, opacity: 0.6}}>McPet / <span style={{fontFamily: design.fonts.dialogue}}>麦麦搭子</span></div>
    <div style={{position: 'absolute', left: 160, top: 238, fontSize: 76, lineHeight: 1.25}}>小钱包，<br/>我帮你看着。</div>
    <div style={{position: 'absolute', left: 160, top: 505, width: 760, height: 292, boxSizing: 'border-box', border: `2px solid ${state.alarm ? alarm : gold}`, borderRadius: 34, backgroundColor: night, padding: '34px 36px'}}>
      <div style={{fontSize: 32, opacity: 0.75}}>鲸鲸的小钱包</div>
      <div style={{fontFamily: design.fonts.data, fontSize: 126, letterSpacing: -6, lineHeight: 1.15, color: state.alarm ? alarm : gold, marginTop: 14}}>¥{state.balance.toFixed(2)}</div>
      <div style={{fontSize: 27, opacity: 0.68, marginTop: 10}}>演示余额 · 低于 ¥5 提醒</div>
    </div>
    <Pet pose={state.pose} angle={state.angle} />
    <div style={{position: 'absolute', left: 148, top: 857, width: 784, minHeight: 197, boxSizing: 'border-box', borderRadius: '32px 32px 8px 32px', border: `2px solid ${gold}`, backgroundColor: night, padding: '25px 32px', fontSize: 44, lineHeight: 1.65, whiteSpace: 'pre-line', opacity: bubble, scale: 0.94 + 0.06 * state.bubble, transformOrigin: '85% 100%'}}>
      {typed}<span style={{opacity: state.typedCharacters < state.totalCharacters ? 0.55 : 0}}>▍</span>
    </div>
    <div style={{position: 'absolute', left: 160, top: 1358, width: 370, fontSize: 30, opacity: 0.65}}>余额有人盯，<br/>小钱包也有小搭子。</div>
    <div style={{position: 'absolute', left: 160, top: 1450, fontSize: 24, opacity: 0.5}}>个人开源作品，与各公司官方无关</div>
  </AbsoluteFill>;
};
