<script setup lang="ts">
import { RouterLink } from 'vue-router';
import PageState from '../components/PageState.vue';
import AppIcon from '../components/AppIcon.vue';
</script>
<template>
  <PageState code="403 · Access required" title="此页面需要相应访问权限" description="请确认你的身份与页面所需权限。统一身份服务接入后，可在登录入口验证身份。" icon="shield">
    <RouterLink to="/login" class="ui-button ui-button--primary">查看登录入口<AppIcon name="arrow-right" :size="17" /></RouterLink><RouterLink to="/" class="ui-button">返回首页</RouterLink>
  </PageState>
</template>
