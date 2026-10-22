<script setup lang="ts">
import { RouterLink } from 'vue-router';

defineProps<{
  navigation: { label: string; to: string }[];
}>();
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header>
      <nav aria-label="主导航">
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          exact-active-class="is-current"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </header>
    <main id="main-content" tabindex="-1">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  max-width: 784px;
  margin: min(12vh, 112px) auto 0;
  padding: 24px 32px 48px;
}

nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 24px;
  border-bottom: 1px solid #cbd5dc;
}

.nav-link {
  padding: 10px 14px;
  border-radius: 6px;
  color: #172b3a;
  text-decoration: none;
}

.nav-link:hover,
.is-current {
  background: #dce9eb;
  color: #12555f;
}

.nav-link:focus-visible,
.skip-link:focus-visible {
  outline: 3px solid #166b76;
  outline-offset: 3px;
}

.skip-link {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 1;
  padding: 12px;
  transform: translateY(calc(-100% - 24px));
  background: #ffffff;
  color: #12555f;
}

.skip-link:focus {
  transform: translateY(0);
}

main {
  padding-top: 32px;
}

@media (max-width: 480px) {
  .app-shell {
    padding-right: 20px;
    padding-left: 20px;
  }

  .nav-link {
    padding-right: 10px;
    padding-left: 10px;
  }
}
</style>
