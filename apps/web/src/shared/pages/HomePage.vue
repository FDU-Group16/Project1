<script setup lang="ts">
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';

const services = [
  { number: '01', title: '座位预约', description: '按时段寻找适合自习的座位，集中查看个人安排。', to: '/m1', icon: 'seat', label: '查看座位页面' },
  { number: '02', title: '整室申请', description: '为集体活动寻找合适的房间，统一管理申请。', to: '/m2', icon: 'building', label: '查看模块介绍' },
  { number: '03', title: '报修服务', description: '让空间问题得到及时记录，让校园设施保持良好状态。', to: '/m3', icon: 'wrench', label: '查看模块介绍' },
];
</script>

<template>
  <section class="home-page" aria-labelledby="home-title">
    <div class="home-intro"><span class="ui-eyebrow">A place for every possibility</span><span class="intro-note"><AppIcon name="leaf" :size="15" />校园里的每一份可能</span></div>
    <div class="hero ui-panel">
      <div class="hero-copy">
        <span class="hero-label"><span></span>你的校园空间，从这里开始</span>
        <h1 id="home-title">给专注留一个位置，<br>让安排更从容。</h1>
        <p>自习、活动与日常服务，汇聚在一个入口。<br class="desktop-break">找到适合你的空间，把时间留给重要的事。</p>
        <div class="hero-actions"><RouterLink to="/m1" class="ui-button ui-button--primary">查找座位<AppIcon name="arrow-right" :size="18" /></RouterLink><RouterLink to="/m1/preview" class="ui-link">浏览界面示例<AppIcon name="chevron-right" :size="16" /></RouterLink></div>
        <small class="hero-status"><AppIcon name="info" :size="14" />预约功能需登录后使用，统一身份服务可用性以登录结果为准。</small>
      </div>
      <div class="hero-art" aria-hidden="true">
        <svg viewBox="0 0 320 300" fill="none" class="study-scene">
          <rect x="26" y="20" width="268" height="258" rx="132" fill="#e3eff0" />
          <path d="M82 162V64c0-8 6-14 14-14h130c8 0 14 6 14 14v98H82Z" fill="#fafdfe" stroke="#a9c5c9" stroke-width="2" />
          <path d="M160 50v112M82 112h158" stroke="#a9c5c9" stroke-width="2" />
          <circle cx="208" cy="82" r="13" fill="#e2cf95" />
          <path d="m83 142 40-27 37 24 39-11 41 19v15H83v-20Z" fill="#d3e5e7" />
          <path d="M57 183h209M76 185v79m170-79v79" stroke="#426d75" stroke-width="6" stroke-linecap="round" />
          <rect x="51" y="175" width="222" height="11" rx="4" fill="#769ba1" />
          <rect x="128" y="129" width="70" height="44" rx="4" fill="#bfd5d8" stroke="#5f8991" stroke-width="2" />
          <path d="M121 173h85" stroke="#5f8991" stroke-width="4" stroke-linecap="round" />
          <path d="m83 175 5-44h20l-6 44" fill="#f4e7be" stroke="#b6a574" stroke-width="2" />
          <path d="M92 131V95m0 0L76 115m16-20 18 13" stroke="#b6a574" stroke-width="3" stroke-linecap="round" />
          <path d="M137 243v31m50-31v31M133 219v20a7 7 0 0 0 7 7h46a7 7 0 0 0 7-7v-20" stroke="#426d75" stroke-width="5" stroke-linecap="round" />
          <rect x="132" y="195" width="62" height="38" rx="10" fill="#9dbbc0" stroke="#5f8991" stroke-width="2" />
          <path d="M229 175v-29" stroke="#5f8991" stroke-width="2" />
          <path d="M230 154c-15 0-20-15-17-23 13 1 19 11 17 23Zm0-9c-1-15 10-21 19-20 1 13-7 21-19 20Z" fill="#7ba889" />
          <path d="M218 161h23l-3 14h-17l-3-14Z" fill="#d7c6a8" />
          <path d="M44 276h233" stroke="#b9d0d3" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span class="art-caption">A LITTLE SPACE. A LOT OF FOCUS.</span>
      </div>
    </div>
    <div class="services-heading"><div><p class="ui-eyebrow">Campus services</p><h2>校园服务，一站抵达</h2></div><span>从需要的服务开始</span></div>
    <div class="service-grid">
      <article v-for="service in services" :key="service.to" class="service-card ui-panel">
        <div class="service-top"><span class="service-icon"><AppIcon :name="service.icon" :size="24" /></span><span class="service-number">{{ service.number }}</span></div>
        <h3>{{ service.title }}</h3><p>{{ service.description }}</p>
        <RouterLink :to="service.to" class="ui-link">{{ service.label }}<AppIcon name="arrow-right" :size="16" /></RouterLink>
      </article>
    </div>
    <div class="home-note"><AppIcon name="shield" :size="19" /><p>界面示例使用合成数据，仅供浏览。实际预约通过后端校验身份、开放时间与座位冲突。</p></div>
  </section>
</template>

<style scoped>
.home-page { padding-top: 8px; }
.home-intro { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 24px; }
.intro-note { display: inline-flex; align-items: center; gap: 7px; color: var(--color-muted); font-size: 11px; }
.hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(240px, .85fr); gap: 10px; overflow: hidden; background: #eef6f6; border-color: #dce8e9; padding: 46px 42px 42px; }
.hero-label { display: inline-flex; align-items: center; gap: 7px; font-size: 11px; color: var(--color-brand); letter-spacing: .04em; margin-bottom: 22px; }
.hero-label > span { width: 5px; height: 5px; border-radius: 50%; background: #66999f; }
h1 { margin: 0 0 21px; font-size: clamp(1.8rem, 3.1vw, 2.65rem); font-weight: 600; line-height: 1.5; letter-spacing: -.04em; }
.hero-copy > p { color: var(--color-muted); font-size: 13px; line-height: 1.95; margin-bottom: 27px; }
.hero-actions { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.hero-actions .ui-link { font-size: 13px; }
.hero-status { display: flex; gap: 6px; align-items: flex-start; margin-top: 25px; color: var(--color-muted); font-size: 10px; }
.hero-status .app-icon { margin-top: 1px; }
.hero-art { display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 0; }
.study-scene { display: block; width: 100%; max-width: 320px; }
.art-caption { color: #789398; font-size: 7px; letter-spacing: .18em; margin-top: 7px; }
.services-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 15px; margin: 35px 0 18px; }
.services-heading .ui-eyebrow { margin-bottom: 7px; font-size: 9px; }
.services-heading h2 { margin: 0; font-size: 20px; }
.services-heading > span { color: var(--color-muted); font-size: 11px; }
.service-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 17px; }
.service-card { display: flex; flex-direction: column; padding: 25px; }
.service-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 25px; }
.service-icon { display: grid; place-items: center; color: var(--color-brand); background: #edf4f5; width: 45px; height: 45px; border-radius: 11px; }
.service-number { color: #b4c5c8; font-size: 12px; font-variant-numeric: tabular-nums; }
.service-card h3 { margin-bottom: 11px; font-size: 18px; }
.service-card p { flex: 1; margin-bottom: 24px; font-size: 12px; line-height: 1.9; color: var(--color-muted); }
.service-card .ui-link { align-self: flex-start; font-size: 12px; min-height: 30px; }
.home-note { display: flex; align-items: center; gap: 9px; margin-top: 24px; color: var(--color-muted); }
.home-note p { font-size: 11px; margin: 0; }
@media (max-width: 960px) { .hero { padding: 34px 30px; grid-template-columns: minmax(0, 1.3fr) minmax(190px, .7fr); } .service-card { padding: 20px; } }
@media (max-width: 640px) {
  .home-intro { margin-bottom: 19px; } .intro-note { display: none; }
  .hero { display: flex; flex-direction: column; padding: 27px 24px 20px; }
  h1 { font-size: 28px; } .hero-label { margin-bottom: 17px; }
  .hero-actions { gap: 17px; } .hero-status { margin-top: 21px; }
  .hero-art { margin-top: 18px; } .study-scene { max-width: 220px; } .art-caption { display: none; }
  .service-grid { grid-template-columns: 1fr; gap: 12px; }
  .service-card { padding: 24px; } .service-top { margin-bottom: 17px; }
  .service-card p { margin-bottom: 16px; } .services-heading > span { display: none; }
  .home-note { align-items: flex-start; } .home-note .app-icon { margin-top: 3px; }
}
@media (max-width: 360px) { .hero { padding-inline: 20px; } h1 { font-size: 25px; } .desktop-break { display: none; } .hero-actions { gap: 14px; } }
</style>
