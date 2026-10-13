import React from 'react';
import {Pose} from '../behavior';
import {design} from '../design';

// 原创几何形象：鲸尾发梢、半月鲸帽和小围裙，不使用外部角色素材。
export const Pet: React.FC<{pose: Pose; angle: number}> = ({pose, angle}) => {
  const {night, gold} = design.colors;
  const worried = pose.expression === 'worry';
  const eye = pose.heading === 'left' ? -4 : 4;
  return <div style={{position: 'absolute', left: pose.x - 180, top: pose.y - 225, width: 360, height: 450, transformOrigin: '50% 90%', rotate: `${pose.rotation + angle}deg`, scale: pose.scale}}>
    <svg viewBox="0 0 360 450" width="360" height="450" aria-label="原创鲸鲸">
      <ellipse cx="180" cy="419" rx="118" ry="12" fill={gold} opacity="0.1" />
      <path d="M110 310 Q70 360 62 318 Q20 316 24 269 Q58 278 82 291 Q77 251 102 245 Q116 266 110 310" fill={night} stroke={gold} strokeWidth="5" />
      <path d="M248 309 Q281 321 277 369 Q290 377 314 365 Q307 406 264 395" fill={night} stroke={gold} strokeWidth="5" />
      <path d="M145 359 L132 412 Q150 427 166 413 L179 363 M198 363 L201 412 Q218 427 232 410 L220 358" fill={night} stroke={gold} strokeWidth="5" />
      <path d="M130 270 Q180 247 235 272 L252 374 Q180 405 115 373 Z" fill={gold} fillOpacity="0.16" stroke={gold} strokeWidth="5" />
      <path d="M136 282 L228 282 L224 359 Q179 377 139 358 Z" fill={night} stroke={gold} strokeWidth="4" />
      <path d="M150 291 L147 318 M215 291 L218 318 M150 337 Q178 356 211 337" fill="none" stroke={gold} strokeWidth="4" strokeLinecap="round" />
      <path d="M124 294 Q87 310 100 334 L144 322 M230 293 Q272 315 256 338 L218 320" fill={night} stroke={gold} strokeWidth="5" strokeLinejoin="round" />
      <path d="M82 211 Q56 238 83 292 Q87 267 109 270 L123 211 M260 211 Q283 245 260 286 Q258 258 238 269 L236 211" fill={gold} fillOpacity="0.15" stroke={gold} strokeWidth="5" />
      <ellipse cx="180" cy="198" rx="91" ry="91" fill={night} stroke={gold} strokeWidth="5" />
      <path d="M92 192 Q68 106 115 69 Q155 41 205 64 Q260 53 275 128 L259 199 Q232 169 223 144 Q190 170 153 134 Q143 171 92 192 Z" fill={gold} fillOpacity="0.24" stroke={gold} strokeWidth="5" strokeLinejoin="round" />
      <path d="M107 91 Q144 24 217 63 Q241 53 250 33 Q273 69 246 91 Q252 101 270 103 Q247 126 220 103 Q162 127 107 91" fill={night} stroke={gold} strokeWidth="5" />
      <path d="M130 86 Q170 58 212 82" fill="none" stroke={gold} strokeWidth="4" strokeLinecap="round" />
      <circle cx="219" cy="83" r="5" fill={gold} />
      <path d={worried ? 'M119 182 L145 174 M208 174 L234 182' : 'M119 177 Q132 169 145 176 M208 176 Q220 168 234 175'} stroke={gold} strokeWidth="5" fill="none" strokeLinecap="round" />
      <ellipse cx={133 + eye} cy="201" rx="7" ry={worried ? 13 : 11} fill={gold} />
      <ellipse cx={220 + eye} cy="201" rx="7" ry={worried ? 13 : 11} fill={gold} />
      <path d={worried ? 'M168 239 Q179 228 190 239' : 'M168 232 Q180 244 192 232'} stroke={gold} strokeWidth="4" fill="none" strokeLinecap="round" />
      <path d="M106 226 L121 228 M237 228 L251 226" stroke={gold} opacity="0.45" strokeWidth="5" strokeLinecap="round" />
      <circle cx="180" cy="321" r="14" fill={gold} fillOpacity="0.15" stroke={gold} strokeWidth="3" />
      <path d="M172 322 Q180 328 187 317" fill="none" stroke={gold} strokeWidth="3" strokeLinecap="round" />
    </svg>
  </div>;
};
