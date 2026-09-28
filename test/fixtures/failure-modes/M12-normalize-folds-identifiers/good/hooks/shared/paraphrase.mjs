// 规范化：去空白与句读，**保留**标识符字符（. - _ /）——笼统去标点会折叠标识符
const DROP_PUNCT = /[，。；：、“”‘’《》！？…—（）()【】\[\]{}<>,;:!?"'`|]/g;
export function normalize(s) {
  return s.replace(/\s+/g, '').replace(DROP_PUNCT, '');
}
