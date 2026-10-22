<script setup lang="ts">
import { RouterLink } from 'vue-router';
import PageState from '../components/PageState.vue';
import AppIcon from '../components/AppIcon.vue';
</script>
<template>
  <PageState code="404 · Page not found" title="这个页面暂时找不到" description="链接可能已更新，或输入的地址有误。回到首页，继续寻找你需要的校园服务。" icon="search">
    <RouterLink to="/" class="ui-button ui-button--primary">返回首页<AppIcon name="arrow-right" :size="17" /></RouterLink><RouterLink to="/m1" class="ui-button">查找座位</RouterLink>
  </PageState>
</template>
