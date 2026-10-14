import catalog from '../../../../assets/cetapet/actions.json';
export const cetapetSource = {repository: catalog.repository, commit: catalog.commit};

// 早期 main.py 的 IMAGE_RELS 完整九项；PNG 是姿态图，不是序列动画。
export type CeTaPetAction = 'nothing' | 'eat' | 'think' | 'pickup' | 'touch' | 'nomoney' | 'cheerup' | 'true' | 'wrong';
export const cetapetActions = catalog.actions as {id: CeTaPetAction; label: string; file: string}[];

export function cetapetImage(action: CeTaPetAction) {
  const entry = cetapetActions.find(item => item.id === action);
  if (!entry) throw new Error(`未知 DeepSeek 娘姿态：${action}`);
  return `pet-skins/cetapet/asset_library/${entry.file}`;
}
