/**
 * review.js — `story.js review` 的实现模块（本地替身）。
 *
 * **它不是与 story.js 并列的第三个对接层入口。** 部署环境的脚本指令统一走 story.js，
 * 内部怎么组织是各自的事；本文件只是把 review 的实现从 story.js 主体里拆出来，
 * 便于替换时定位。CLI 契约见 story.js 的 docstring。
 *
 * 拉回评审人在需求系统上对归档件留下的反馈，**直接写入 AR/review.md**（先备份原件）。
 *
 * 为什么产出不是中间 JSON 而是直接写回 review.md：回流阶段模型的输入唯一就是
 * review.md——人可能在系统上批注，也可能直接改本地文件，**流程不关心来源**。
 * 多一层中间格式就多一套解析，而两套解析必然分叉。
 *
 * 本实现是替身：评审人的回稿就是系统上该单目录下的 `review-feedback.md`，
 * 有就整份拉回来覆盖本地，没有就什么都不改。替换时保持 story.js 声明的回执形状不变。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

/** 评审人在系统上留下回稿的位置（相对该单的目录）。 */
const FEEDBACK_FILE = 'review-feedback.md';

/**
 * @param {object} ctx
 * @param {string} ctx.ar          单号
 * @param {string} ctx.featureRoot feature 工作区绝对路径
 * @param {string} ctx.system      需求系统目录绝对路径
 * @param {Function} ctx.log       人类可读日志（走 stderr）
 * @param {Function} ctx.ts        时间戳串（备份文件名用）
 * @returns {object} 回执对象，由调用方 emit 成单行 JSON
 */
function fetchReview({ ar, featureRoot, system, log, ts }) {
  const reviewPath = path.join(featureRoot, 'AR', 'review.md');
  if (!fs.existsSync(reviewPath)) {
    return {
      mode: 'review', reqNo: ar, success: false,
      error: `AR/review.md 不存在：${reviewPath}——评审回稿要写回它，先跑 /spec 产出首版`,
    };
  }

  // 先备份：回稿覆盖的是人可能已经手工编辑过的文件，覆盖前必须留得住原样。
  const backupDir = path.join(featureRoot, 'AR', '.review-backup');
  fs.mkdirSync(backupDir, { recursive: true });
  const backupAbs = path.join(backupDir, `${ts()}-review.md`);
  fs.copyFileSync(reviewPath, backupAbs);
  log(`备份：${backupAbs}`);
  // 回执里给**相对 feature 根**的路径：绝对路径带着本机盘符，对端换个环境就没意义。
  // 人要点开的那份走 stderr 日志（上一行），两者各服务各的读者。
  const backupPath = path.relative(featureRoot, backupAbs).split(path.sep).join('/');

  const feedback = path.join(system, ar, FEEDBACK_FILE);
  let status = 'unchanged';
  if (fs.existsSync(feedback)) {
    fs.writeFileSync(reviewPath, fs.readFileSync(feedback, 'utf-8'), 'utf-8');
    status = 'confirmed';
    log(`已拉回评审回稿并覆盖：${reviewPath}`);
  } else {
    // **不伪造已填写的表态**——那会让本地跑出「评审已完成」的假象。
    log(`需求系统上 ${ar} 还没有评审回稿，AR/review.md 保持原样。`);
  }

  return {
    mode: 'review', reqNo: ar, fetched: true, target: 'AR/review.md',
    backupPath, status, success: true,
  };
}

module.exports = { fetchReview };
