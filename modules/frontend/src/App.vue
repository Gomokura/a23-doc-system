<script setup lang="ts">
import { ref } from 'vue'
import Landing from '@/pages/Landing.vue'
import Header from '@/layout/Header.vue'
import Sidebar from '@/layout/Sidebar.vue'
import MainContent from '@/layout/MainContent.vue'

const showApp = ref(false)
const currentTab = ref(0)

function enterApp() {
  showApp.value = true
}
</script>

<template>
  <!-- 落地页 -->
  <Transition name="fade-slide">
    <Landing v-if="!showApp" @enter="enterApp" />
  </Transition>

  <!-- 工作台 -->
  <Transition name="fade-slide">
    <div v-if="showApp" class="min-h-screen bg-[#f0f4ff] flex flex-col">
      <Header @back="showApp = false" />
      <div class="flex flex-1 overflow-hidden" style="height: calc(100vh - 56px)">
        <Sidebar v-model="currentTab" />
        <MainContent :tab="currentTab" />
      </div>
    </div>
  </Transition>
</template>

<style>
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(16px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
