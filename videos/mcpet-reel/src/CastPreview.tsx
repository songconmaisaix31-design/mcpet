import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Pet, Dragon} from './actors/Pet';
import {startPose} from './behaviors/worry';
import {design} from './design';

// 选角静态预览不属于叙事行为，没有场景时长。
export const CastPreview: React.FC = () => <AbsoluteFill style={{backgroundColor: design.colors.night, color: design.colors.gold, fontFamily: design.fonts.dialogue}}>
  <div style={{position: 'absolute', left: 160, top: 200, fontSize: 70, lineHeight: 1.4}}>两只小搭子，<br/>来陪你上班。</div>
  <Pet pose={{...startPose, x: 355, y: 1025}} angle={0} />
  <Dragon pose={{...startPose, x: 725, y: 1025}} />
  <div style={{position: 'absolute', left: 160, top: 1280, width: 390, textAlign: 'center', fontSize: 44}}>DeepSeek 娘</div>
  <div style={{position: 'absolute', left: 540, top: 1280, width: 370, textAlign: 'center', fontSize: 44}}>ChatGPT 娘</div>
  <div style={{position: 'absolute', left: 160, top: 1380, fontSize: 28}}>余额有人盯，进度有人陪，干饭有人喊</div>
  <div style={{position: 'absolute', left: 160, top: 1450, fontSize: 24, opacity: 0.5}}>个人开源作品，与各公司官方无关</div>
</AbsoluteFill>;
