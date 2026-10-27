<script setup lang="ts">
import { ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
// TEMPORARY-DEPENDENCY WEB-D01-IDENTITY：下方 auth.session.synthetic 横幅标识 Web M1/D-02 对 D-01（M2 组）的开发身份替身。
// 可在提供/消费组集成范围内修改或移除该横幅及专用样式；保留真实身份展示和公共布局，见 ../auth/docs/auth-integration.md。
import { auth } from '../auth';
type NavigationItem = { label: string; to: string; icon?: string };
withDefaults(defineProps<{
  navigation: NavigationItem[];
  sidebar?: NavigationItem[];
  sectionTitle?: string;
  sectionDescription?: string;
  compact?: boolean;
  preview?: boolean;
}>(), { sidebar: () => [], sectionTitle: '', sectionDescription: '', compact: false, preview: false });
const route = useRoute();
const menuOpen = ref(false);
const menuButton = ref<HTMLButtonElement | null>(null);
const isModuleActive = (to: string) => route.path === to || (to !== '/' && route.path.startsWith(`${to}/`));
const isSidebarActive = (to: string, items: NavigationItem[]) => {
  const matching = items.filter(item => route.path === item.to || route.path.startsWith(`${item.to}/`));
  return matching.sort((left, right) => right.to.length - left.to.length)[0]?.to === to;
};
watch(() => route.fullPath, () => { menuOpen.value = false; });
function closeMenu() {
  if (!menuOpen.value) return;
  menuOpen.value = false;
  menuButton.value?.focus();
}
</script>
<template>
  <div class="app-shell" :class="{ 'is-compact': compact }" @keydown.esc="closeMenu">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="app-header">
      <div class="header-inner">
        <RouterLink to="/" class="brand" aria-label="校园资源平台首页">
          <span class="brand-mark"><AppIcon name="book" :size="23" /></span>
          <span class="brand-text">校园资源<span class="brand-caption">CAMPUS RESOURCE</span></span>
        </RouterLink>
        <nav v-if="!compact" class="top-nav" aria-label="主导航">
          <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" class="top-link" :class="{ 'is-current': isModuleActive(item.to) }" :aria-current="isModuleActive(item.to) ? 'page' : undefined">{{ item.label }}</RouterLink>
        </nav>
        <RouterLink v-if="!compact" :to="{ path: '/login', query: { redirect: route.fullPath } }" class="account-link">
          <span class="account-icon"><AppIcon name="user" :size="17" /></span><span>{{ auth.session?.user.displayName || '登录' }}</span>
        </RouterLink>
        <RouterLink v-else to="/" class="return-home"><AppIcon name="arrow-left" :size="16" />返回首页</RouterLink>
      </div>
    </header>
    <div class="workspace" :class="{ 'has-sidebar': sidebar.length && !compact }">
      <template v-if="sidebar.length && !compact">
        <button ref="menuButton" type="button" class="mobile-menu-toggle" aria-controls="section-navigation" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">
          <AppIcon :name="menuOpen ? 'x' : 'menu'" :size="18" /><span>{{ sectionTitle || '模块菜单' }}</span><span class="menu-action">{{ menuOpen ? '收起菜单' : '展开菜单' }}</span>
        </button>
        <aside id="section-navigation" class="sidebar" :class="{ 'is-open': menuOpen }">
          <div class="sidebar-heading"><span class="sidebar-rule"></span>{{ sectionTitle || '功能导航' }}</div>
          <nav class="side-nav" :aria-label="`${sectionTitle || '模块'}菜单`">
            <RouterLink v-for="item in sidebar" :key="item.to" :to="item.to" class="side-link" :class="{ 'is-current': isSidebarActive(item.to, sidebar) }" :aria-current="isSidebarActive(item.to, sidebar) ? 'page' : undefined">
              <AppIcon v-if="item.icon" :name="item.icon" :size="18" /><span>{{ item.label }}</span><span v-if="isSidebarActive(item.to, sidebar)" class="active-dot"></span>
            </RouterLink>
          </nav>
          <div class="sidebar-note">
            <AppIcon :name="preview ? 'info' : 'leaf'" :size="21" />
            <p>{{ preview ? '正在浏览界面示例' : '让空间更好地服务学习' }}</p>
            <small>{{ preview ? '合成数据 · 仅供体验' : (sectionDescription || '找到适合你的校园空间。') }}</small>
          </div>
          <div class="sidebar-footer"><span class="connection-dot"></span>校园资源服务平台</div>
        </aside>
      </template>
      <div class="main-column">
        <main id="main-content" tabindex="-1" class="main-content" :class="{ 'main-content--compact': compact }">
          <div v-if="sectionTitle && !compact" class="breadcrumb" aria-label="当前位置"><RouterLink to="/">校园资源</RouterLink><AppIcon name="chevron-right" :size="13" /><span>{{ sectionTitle }}</span><span v-if="preview" class="breadcrumb-preview">界面示例</span></div>
          <div v-if="auth.session?.synthetic" class="development-banner" role="status">开发联调 · 合成身份：{{ auth.session.user.displayName }}。业务请求访问真实后端，身份验证尚未接入。</div>
          <div v-else-if="auth.session?.user.testAccount === true" class="test-account-banner" role="status">课程测试账号：{{ auth.session.user.displayName }}。仅用于功能体验，账号有有效期；请勿填写真实个人信息。</div>
          <slot />
        </main>
        <footer class="app-footer"><span>校园资源服务平台</span><span>让每一份校园资源，恰好被需要。</span></footer>
      </div>
    </div>
  </div>
</template>
<style scoped>
.development-banner { border: 1px solid #d4a251; background: #fff8e9; color: #82520f; border-radius: 8px; padding: 12px 15px; margin-bottom: 24px; font-size: 12px; line-height: 1.8; }
.test-account-banner { border: 1px solid #d6cee6; background: #f8f5fc; color: #66517c; border-radius: 8px; padding: 12px 15px; margin-bottom: 24px; font-size: 12px; line-height: 1.8; }
.app-shell { min-height: 100vh; }
.app-header { background: var(--color-surface); border-bottom: 1px solid var(--color-border); }
.header-inner { display: flex; align-items: center; gap: 48px; max-width: 1600px; min-height: 82px; margin: 0 auto; padding: 16px 40px; }
.brand { display: inline-flex; align-items: center; gap: 11px; color: var(--color-text); text-decoration: none; flex-shrink: 0; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px 12px 12px 3px; background: var(--color-brand); color: #fff; }
.brand-text { display: grid; font-size: 18px; font-weight: 650; line-height: 1.4; letter-spacing: .025em; }
.brand-caption { margin-top: 2px; color: var(--color-muted); font-size: 8px; font-weight: 500; letter-spacing: .16em; }
.top-nav { display: flex; align-items: center; gap: 8px; flex: 1; }
.top-link { display: flex; align-items: center; min-height: 42px; border-radius: 7px; padding: 8px 14px; font-size: 14px; color: var(--color-muted); text-decoration: none; white-space: nowrap; }
.top-link:hover { color: var(--color-brand); background: #f2f7f7; }
.top-link.is-current { background: var(--color-brand-soft); color: var(--color-brand); font-weight: 600; }
.account-link { display: flex; align-items: center; gap: 8px; color: var(--color-text); text-decoration: none; font-size: 13px; white-space: nowrap; min-height: 44px; }
.account-icon { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; color: var(--color-brand); background: #edf3f4; }
.return-home { margin-left: auto; display: flex; align-items: center; gap: 7px; font-size: 13px; text-decoration: none; min-height: 44px; }
.workspace { display: flex; max-width: 1600px; min-height: calc(100vh - 83px); margin: 0 auto; }
.has-sidebar { display: grid; grid-template-columns: 228px minmax(0, 1fr); }
.sidebar { display: flex; flex-direction: column; background: #fff; padding: 35px 18px 22px; border-right: 1px solid var(--color-border); }
.sidebar-heading { display: flex; gap: 8px; align-items: center; padding: 0 13px; margin-bottom: 20px; color: var(--color-muted); font-size: 11px; letter-spacing: .1em; }
.sidebar-rule { width: 3px; height: 12px; border-radius: 2px; background: #a0bfc2; }
.side-nav { display: grid; gap: 7px; }
.side-link { display: flex; align-items: center; gap: 11px; min-height: 47px; padding: 11px 14px; color: var(--color-muted); border-radius: 8px; text-decoration: none; font-size: 14px; }
.side-link:hover { background: #f3f7f7; color: var(--color-brand); }
.side-link.is-current { background: var(--color-brand-soft); color: var(--color-brand); font-weight: 600; }
.active-dot { margin-left: auto; width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.sidebar-note { margin: 38px 10px 28px; padding: 20px 0 0; border-top: 1px solid var(--color-border); color: var(--color-brand); }
.sidebar-note p { font-size: 12px; margin: 10px 0 6px; }
.sidebar-note small { display: block; color: var(--color-muted); font-size: 11px; line-height: 1.8; }
.sidebar-footer { display: flex; align-items: center; gap: 7px; margin-top: auto; padding: 0 13px; font-size: 10px; color: var(--color-muted); }
.connection-dot { width: 5px; height: 5px; border-radius: 50%; background: #8ea6ab; }
.main-column { min-width: 0; display: flex; flex-direction: column; flex: 1; }
.main-content { width: 100%; max-width: 1180px; padding: 32px 44px 40px; margin: 0 auto; flex: 1; outline: none; }
.main-content--compact { max-width: none; padding-top: 74px; }
.breadcrumb { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 28px; color: var(--color-muted); font-size: 11px; }
.breadcrumb a { color: var(--color-muted); text-decoration: none; }
.breadcrumb a:hover { color: var(--color-brand); text-decoration: underline; }
.breadcrumb-preview { margin-left: auto; color: var(--color-brand); background: var(--color-brand-soft); padding: 2px 7px; border-radius: 4px; }
.app-footer { display: flex; justify-content: space-between; gap: 10px; padding: 20px 44px; color: #718186; font-size: 10px; border-top: 1px solid #e7edee; }
.skip-link { position: fixed; top: 12px; left: 12px; z-index: 100; padding: 12px 16px; border-radius: 8px; transform: translateY(calc(-100% - 24px)); color: var(--color-brand); background: #fff; box-shadow: 0 4px 20px #17372b20; }
.skip-link:focus { transform: translateY(0); }
.mobile-menu-toggle { display: none; }
@media (min-width: 1601px) { .workspace { border-left: 1px solid var(--color-border); border-right: 1px solid var(--color-border); } }
@media (max-width: 1100px) { .header-inner { gap: 30px; padding-inline: 28px; } .has-sidebar { grid-template-columns: 200px minmax(0, 1fr); } .main-content { padding-inline: 28px; } .app-footer { padding-inline: 28px; } .sidebar { padding-inline: 12px; } .top-link { padding-inline: 10px; } }
@media (max-width: 760px) {
  .header-inner { flex-wrap: wrap; justify-content: space-between; gap: 15px; min-height: auto; padding: 17px 20px 12px; }
  .brand-mark { width: 36px; height: 36px; }
  .brand-text { font-size: 16px; }
  .brand-caption { font-size: 7px; }
  .top-nav { order: 3; flex-basis: 100%; gap: 6px; justify-content: space-between; }
  .top-link { flex: 1; justify-content: center; padding: 8px 6px; font-size: 13px; }
  .account-link { margin-left: auto; }
  .has-sidebar { display: block; }
  .mobile-menu-toggle { display: flex; align-items: center; gap: 9px; width: 100%; background: #fff; padding: 13px 20px; border: 0; border-bottom: 1px solid var(--color-border); color: var(--color-brand); font-size: 13px; }
  .menu-action { margin-left: auto; color: var(--color-muted); font-size: 11px; }
  .sidebar { display: none; border-right: 0; border-bottom: 1px solid var(--color-border); padding: 14px 20px; }
  .sidebar.is-open { display: block; }
  .sidebar-heading, .sidebar-note, .sidebar-footer { display: none; }
  .main-content { padding: 25px 20px 32px; }
  .main-content--compact { padding-top: 42px; }
  .breadcrumb { margin-bottom: 23px; }
  .app-footer { padding: 18px 20px; flex-wrap: wrap; }
  .workspace { min-height: calc(100vh - 129px); }
  .is-compact .workspace { min-height: calc(100vh - 78px); }
}
@media (max-width: 380px) { .header-inner { padding-inline: 16px; } .main-content { padding-inline: 16px; } .app-footer { padding-inline: 16px; } .top-link { font-size: 12px; } }
</style>
