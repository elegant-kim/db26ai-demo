<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
</script>

<template>
  <!-- 메인 메뉴 간 전환 시 페이지 상태 유지 (KeepAlive) — 현 레거시의 v-show 경험을 보존 -->
  <AppShell>
    <RouterView v-slot="{ Component }">
      <KeepAlive>
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </AppShell>
</template>
