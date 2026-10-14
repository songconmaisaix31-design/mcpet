import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {cetapetActions, cetapetImage} from './actors/cetapet';
import {design} from './design';

export const CeTaPetPreview: React.FC = () => <AbsoluteFill style={{backgroundColor: design.colors.night, color: design.colors.gold, fontFamily: design.fonts.dialogue}}>
  <div style={{position: 'absolute', left: 145, top: 145, fontSize: 64}}>鲸鲸的九种小姿态</div>
  <div style={{position: 'absolute', left: 145, top: 245, fontSize: 28, opacity: 0.65}}>早期 CeTaPet · 原始姿态图</div>
  <div style={{position: 'absolute', left: 145, top: 345, width: 790, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '32px 15px'}}>
    {cetapetActions.map(action => <div key={action.id} style={{height: 295, textAlign: 'center', padding: 8, boxSizing: 'border-box', border: `1px solid ${design.colors.gold}`, borderRadius: 20}}>
      <Img src={staticFile(cetapetImage(action.id))} alt={action.label} data-action={action.id} style={{width: '100%', height: 215, objectFit: 'contain'}} />
      <div style={{fontSize: 30, marginTop: 13}}>{action.label}</div>
    </div>)}
  </div>
  <div style={{position: 'absolute', left: 145, top: 1390, fontSize: 28}}>没有对应动作时，就让我冒个小气泡。</div>
  <div style={{position: 'absolute', left: 145, top: 1450, fontSize: 24, opacity: 0.5}}>个人开源作品，与各公司官方无关</div>
</AbsoluteFill>;
