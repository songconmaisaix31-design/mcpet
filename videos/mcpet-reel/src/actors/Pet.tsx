import React from 'react';
import {Pose} from '../behavior';
import {Img, staticFile} from 'remotion';
import {CeTaPetAction, cetapetImage} from './cetapet';

export type CharacterId = 'deepseek' | 'chatgpt';
const names = {deepseek: 'DeepSeek 娘', chatgpt: 'ChatGPT 娘'};

// 使用现有透明待机帧；没有对应姿势的情绪由头顶气泡承担。
export const Character: React.FC<{character: CharacterId; pose: Pose; angle?: number; action?: CeTaPetAction}> = ({character, pose, angle = 0, action = 'nothing'}) => {
  const source = character === 'deepseek' ? cetapetImage(action) : 'pet-skins/chatgpt-idle.png';
  return <div data-character={character} data-action={action} style={{position: 'absolute', left: pose.x - 180, top: pose.y - 225, width: 360, height: 450, transformOrigin: '50% 90%', rotate: `${pose.rotation + angle}deg`, scale: pose.scale}}>
    <Img src={staticFile(source)} alt={names[character]} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
  </div>;
};

export const Pet: React.FC<{pose: Pose; angle: number; action?: CeTaPetAction}> = props => <Character character="deepseek" {...props} />;
export const Dragon: React.FC<{pose: Pose; angle?: number}> = props => <Character character="chatgpt" {...props} />;
