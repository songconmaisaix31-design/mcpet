import React from 'react';
import {Pose} from '../behavior';
import {Img, staticFile} from 'remotion';

export type CharacterId = 'deepseek' | 'chatgpt';
const names = {deepseek: 'DeepSeek 娘', chatgpt: 'ChatGPT 娘'};

// 使用现有透明待机帧；没有对应姿势的情绪由头顶气泡承担。
export const Character: React.FC<{character: CharacterId; pose: Pose; angle?: number}> = ({character, pose, angle = 0}) => {
  return <div data-character={character} style={{position: 'absolute', left: pose.x - 180, top: pose.y - 225, width: 360, height: 450, transformOrigin: '50% 90%', rotate: `${pose.rotation + angle}deg`, scale: pose.scale}}>
    <Img src={staticFile(`pet-skins/${character}-idle.png`)} alt={names[character]} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
  </div>;
};

export const Pet: React.FC<{pose: Pose; angle: number}> = props => <Character character="deepseek" {...props} />;
export const Dragon: React.FC<{pose: Pose; angle?: number}> = props => <Character character="chatgpt" {...props} />;
