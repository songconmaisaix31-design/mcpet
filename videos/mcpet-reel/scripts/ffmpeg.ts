import {createRequire} from 'node:module';
import {dirname, join} from 'node:path';

export function ffmpegPath() {
  const require = createRequire(join(process.cwd(), 'package.json'));
  const packages: Record<string, string> = {
    'win32-x64': 'compositor-win32-x64-msvc',
    'darwin-arm64': 'compositor-darwin-arm64',
    'darwin-x64': 'compositor-darwin-x64',
    'linux-x64': 'compositor-linux-x64-gnu',
    'linux-arm64': 'compositor-linux-arm64-gnu',
  };
  const name = packages[`${process.platform}-${process.arch}`];
  if (!name) throw new Error('当前平台需要安装可用的 FFmpeg');
  return join(dirname(require.resolve(`@remotion/${name}`)), process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg');
}
