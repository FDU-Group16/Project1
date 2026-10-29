<script setup lang="ts">
import { RouterLink } from 'vue-router';
</script>

<template>
  <div class="m2-home">
    <header class="m2-hero ui-panel">
      <p class="ui-eyebrow">M2 · 整室申请</p>
      <h1>为集体活动准备合适的空间</h1>
      <p class="m2-lead">先核对房间、时间、人数和用途。当前可使用本地草稿预览；正式提交与审批服务仍在接入中。</p>
      <RouterLink to="/m2/apply" class="ui-button ui-button--primary">准备申请草稿 <span aria-hidden="true">→</span></RouterLink>
      <p class="m2-notice" role="status">草稿只在当前页面预览，不会保存、提交或占用教室。</p>
    </header>

    <section aria-labelledby="m2-steps-title">
      <div class="m2-section-heading">
        <p class="ui-eyebrow">申请流程</p>
        <h2 id="m2-steps-title">从准备到审批</h2>
      </div>
      <div class="m2-steps">
        <article class="ui-panel m2-step">
          <span class="m2-number" aria-hidden="true">01</span>
          <h3>准备申请</h3>
          <p>填写五项申请信息，先在本机检查格式和时间顺序。房间资格与容量仍需服务端核对。</p>
          <span class="ui-badge">本地预览可用</span>
        </article>
        <article class="ui-panel m2-step">
          <span class="m2-number" aria-hidden="true">02</span>
          <h3>提交与查询</h3>
          <p>申请保存、本人列表和状态查询需要 M2 公开接口及真实身份服务。</p>
          <span class="m2-pending">等待后端接入</span>
        </article>
        <article class="ui-panel m2-step">
          <span class="m2-number" aria-hidden="true">03</span>
          <h3>审批与占用</h3>
          <p>审批权限、截止处理和 M1 教室占用由后端完成，页面不会自行模拟审批结果。</p>
          <span class="m2-pending">等待联调验收</span>
        </article>
      </div>
    </section>

    <section class="ui-panel m2-boundary" aria-labelledby="m2-boundary-title">
      <h2 id="m2-boundary-title">目前可以做什么？</h2>
      <p>你可以准备并检查申请草稿。提交、查询、撤回和审批尚未开放；本页不会显示虚构的申请或待办。服务上线后，这些操作会以真实接口和权限校验接入。</p>
    </section>
  </div>
</template>

<style scoped>
.m2-home { max-width: 1120px; margin: 0 auto; padding-bottom: 36px; }
.m2-hero { padding: clamp(24px, 5vw, 54px); margin-bottom: 36px; background: linear-gradient(135deg, var(--color-surface), var(--color-brand-soft)); }
.m2-hero h1 { max-width: 680px; margin: 8px 0 16px; }
.m2-lead { max-width: 620px; color: var(--color-muted); line-height: 1.85; margin-bottom: 24px; }
.m2-notice { color: var(--color-muted); font-size: 13px; margin: 18px 0 0; }
.m2-section-heading { margin-bottom: 18px; }
.m2-section-heading h2 { margin: 5px 0; }
.m2-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.m2-step { padding: 24px; display: flex; flex-direction: column; align-items: flex-start; }
.m2-number { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; color: var(--color-brand); background: var(--color-brand-soft); font-weight: 700; margin-bottom: 18px; }
.m2-step h3 { margin: 0 0 10px; }
.m2-step p { color: var(--color-muted); line-height: 1.8; font-size: 14px; flex: 1; }
.m2-pending { color: var(--color-muted); background: var(--color-page); border-radius: 5px; padding: 3px 9px; font-size: 12px; }
.m2-boundary { padding: 24px; margin-top: 20px; }
.m2-boundary h2 { margin-bottom: 9px; }
.m2-boundary p { color: var(--color-muted); line-height: 1.8; margin-bottom: 0; }
@media (max-width: 760px) { .m2-steps { grid-template-columns: 1fr; } .m2-step { padding: 20px; } .m2-hero { margin-bottom: 28px; } }
@media (max-width: 380px) { .m2-hero .ui-button { width: 100%; } }
</style>
